"""The scraping ladder (SPEC §4, #1): an ordered attempt loop with structured
results. Each rung's listing() returns a ListingResult; the ladder falls through
to the next rung on `error`/`blocked` (and on `empty` for discovery rungs), and
stops on `ok`. A specific-ATS rung treats `empty` as terminal (trust the API);
`custom`/`auto` companies fall Playwright -> static.
"""
from __future__ import annotations

from contextlib import contextmanager

from scrapers import static_scraper
from scrapers.ats import ashby, greenhouse, lever, smartrecruiters
from scrapers.ats.talemetry import TalemetryFetcher
from scrapers.ats.workday import WorkdayFetcher
from scrapers.playwright_scraper import PlaywrightSession
from scrapers.result import ListingResult, OK, EMPTY, BLOCKED, ERROR

_API_MODULES = {"greenhouse": greenhouse, "ashby": ashby,
                "lever": lever, "smartrecruiters": smartrecruiters}


def detect_ats(company: dict, http) -> str:
    """Resolve ats_type 'auto' to a concrete rung (SPEC §4.1)."""
    url = company.get("careers_url", "")
    markers = (("greenhouse", "greenhouse"), ("lever.co", "lever"),
               ("ashbyhq", "ashby"), ("smartrecruiters", "smartrecruiters"),
               ("myworkdayjobs", "workday"), ("talemetry", "talemetry"))
    low = url.lower()
    for needle, ats in markers:
        if needle in low:
            return ats
    try:
        body = http.get(url).text.lower()
        for needle, ats in markers:
            if needle in body:
                return ats
    except Exception:
        pass
    return "custom"  # default to Playwright — handles JS + Cloudflare


# --- fetcher wrappers (each exposes listing()->ListingResult, detail(), etc.) ---

class _ApiFetcher:
    """JSON-API adapters. Greenhouse/Ashby/Lever ship descriptions in the listing;
    SmartRecruiters exposes module-level fetch_detail + NEEDS_DETAIL."""
    check_robots = False

    def __init__(self, company, http, module, rung):
        self.company, self.http, self.module, self.rung_name = company, http, module, rung
        self.needs_detail = getattr(module, "NEEDS_DETAIL", False)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self) -> ListingResult:
        slug = self.company.get("ats_slug") or self.company["slug"]
        raw = self.module.fetch_listing(slug, self.http)
        return ListingResult(OK if raw else EMPTY, raw, self.rung_name)

    def detail(self, url):
        fn = getattr(self.module, "fetch_detail", None)
        if fn and url:
            try:
                return fn(url, self.http) or ""
            except Exception:
                return ""
        return ""


class _PlaywrightFetcher:
    needs_detail = True
    check_robots = True
    rung_name = "playwright"

    def __init__(self, company, http, selectors, wait_for):
        self.company, self.http = company, http
        self.settings = http.settings
        self.careers_url = company["careers_url"]
        self.selectors, self.wait_for = selectors, wait_for
        self.session = None

    def __enter__(self):
        self.session = PlaywrightSession(self.settings).__enter__()
        return self

    def __exit__(self, *exc):
        if self.session:
            self.session.__exit__(*exc)
        return False

    def listing(self) -> ListingResult:
        if not self.selectors.get("job_card"):
            return ListingResult(EMPTY, [], self.rung_name, "no selectors configured")
        self.http.wait(self.careers_url)
        raw, status = self.session.listing(self.careers_url, self.selectors, self.wait_for)
        st = {"ok": OK, "blocked": BLOCKED}.get(status, EMPTY)
        return ListingResult(st, raw, self.rung_name)

    def detail(self, url):
        if not url:
            return ""
        self.http.wait(url)
        return self.session.detail(url)


class _StaticFetcher:
    needs_detail = True
    check_robots = True
    rung_name = "static"

    def __init__(self, company, http, selectors):
        self.company, self.http, self.selectors = company, http, selectors
        self.careers_url = company["careers_url"]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self) -> ListingResult:
        if not self.selectors.get("job_card"):
            return ListingResult(EMPTY, [], self.rung_name, "no selectors configured")
        raw, status = static_scraper.listing(self.careers_url, self.selectors, self.http)
        return ListingResult(OK if status == "ok" else EMPTY, raw, self.rung_name)

    def detail(self, url):
        if not url:
            return ""
        return static_scraper.detail(url, self.http)


# --- rung planning + attempt loop ----------------------------------------------

def _build_rungs(company, profile, http):
    """Return ordered list of (terminal_on_empty, factory). The first rung is the
    primary (ATS API or, for custom/auto, Playwright); discovery fallbacks follow."""
    ats = (company.get("ats_type") or "auto").lower()
    if ats == "auto":
        ats = detect_ats(company, http)

    selectors = profile.get("selectors", {})
    wait_for = profile.get("wait_for")
    query = profile.get("ats_query", "product")
    playwright = (False, lambda: _PlaywrightFetcher(company, http, selectors, wait_for))
    static = (False, lambda: _StaticFetcher(company, http, selectors))

    if ats in _API_MODULES:
        module = _API_MODULES[ats]
        primary = (True, lambda: _ApiFetcher(company, http, module, ats))
        return [primary, playwright, static]   # fall back only on error/blocked
    if ats == "workday":
        return [(True, lambda: WorkdayFetcher(company, http, query)), playwright, static]
    if ats == "talemetry":
        return [(True, lambda: TalemetryFetcher(company, http, query)), static]
    # custom / unresolved -> discovery rungs only
    return [playwright, static]


def _attempt(http, rungs) -> tuple[object, ListingResult]:
    """Try rungs in order. Return (open_fetcher, result) on OK (fetcher stays open
    for detail), else (None, last_result)."""
    last = ListingResult(ERROR, [], "none", "no rungs configured")
    for terminal_on_empty, factory in rungs:
        fetcher = factory()
        fetcher.__enter__()
        try:
            if getattr(fetcher, "check_robots", False) and \
                    not http.allowed(getattr(fetcher, "careers_url", "")):
                res = ListingResult(BLOCKED, [], fetcher.rung_name, "robots.txt disallowed")
            else:
                res = fetcher.listing()
        except Exception as e:  # noqa: BLE001 — convert to structured error (#1)
            res = ListingResult(ERROR, [], getattr(fetcher, "rung_name", "?"), str(e)[:200])
        if res.ok:
            return fetcher, res
        fetcher.__exit__(None, None, None)
        last = res
        if res.status == EMPTY and terminal_on_empty:
            break   # trust an ATS API that genuinely returned nothing
    return None, last


@contextmanager
def open_company(company: dict, profile: dict, http):
    """Run the ladder for one company; yield (fetcher_or_None, ListingResult)."""
    rungs = _build_rungs(company, profile, http)
    fetcher, result = _attempt(http, rungs)
    try:
        yield fetcher, result
    finally:
        if fetcher is not None:
            fetcher.__exit__(None, None, None)
