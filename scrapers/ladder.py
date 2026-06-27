"""The scraping ladder (SPEC §4): ATS JSON API -> Playwright -> static HTML.

`make_fetcher(company, ...)` returns a context-managed fetcher for one company.
Greenhouse/Lever deliver descriptions in the listing call, so `needs_detail` is
False and no per-job page fetch happens. Playwright/static need a detail fetch
per surviving posting.
"""
from __future__ import annotations

from contextlib import contextmanager

import requests

from scrapers import static_scraper
from scrapers.ats import ashby, greenhouse, lever, smartrecruiters
from scrapers.ats.talemetry import TalemetryFetcher
from scrapers.ats.workday import WorkdayFetcher
from scrapers.playwright_scraper import PlaywrightSession
from scrapers.rate_limiter import RateLimiter


def detect_ats(company: dict, settings: dict) -> str:
    """Resolve ats_type 'auto' to a concrete rung (SPEC §4.1)."""
    url = company.get("careers_url", "")
    low = url.lower()
    markers = (("greenhouse", "greenhouse"), ("lever.co", "lever"),
               ("ashbyhq", "ashby"), ("smartrecruiters", "smartrecruiters"),
               ("myworkdayjobs", "workday"), ("talemetry", "talemetry"))
    for needle, ats in markers:
        if needle in low:
            return ats
    try:
        r = requests.get(url, headers={"User-Agent": settings.get("user_agent", "JSA")},
                         timeout=settings.get("request_timeout", 20))
        body = r.text.lower()
        for needle, ats in markers:
            if needle in body:
                return ats
    except Exception:
        pass
    return "custom"  # default to Playwright — handles JS + Cloudflare


class _ApiFetcher:
    """JSON-API adapters. Greenhouse/Ashby/Lever ship descriptions in the listing
    (needs_detail False); SmartRecruiters exposes module-level fetch_detail +
    NEEDS_DETAIL for a per-posting detail fetch."""

    def __init__(self, company, settings, limiter, module):
        self.company, self.settings, self.limiter, self.module = \
            company, settings, limiter, module
        self.needs_detail = getattr(module, "NEEDS_DETAIL", False)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self):
        self.limiter.wait(self.company["careers_url"])
        slug = self.company.get("ats_slug") or self.company["slug"]
        raw = self.module.fetch_listing(slug, self.settings)
        return raw, ("ok" if raw else "empty"), self.module.__name__.split(".")[-1]

    def detail(self, url):
        fn = getattr(self.module, "fetch_detail", None)
        if fn and url:
            self.limiter.wait(url)
            try:
                return fn(url, self.settings) or ""
            except Exception:
                return ""
        return ""


class _PlaywrightFetcher:
    needs_detail = True

    def __init__(self, company, settings, limiter, selectors, wait_for):
        self.company, self.settings, self.limiter = company, settings, limiter
        self.selectors, self.wait_for = selectors, wait_for
        self.session = None

    def __enter__(self):
        self.session = PlaywrightSession(self.settings).__enter__()
        return self

    def __exit__(self, *exc):
        if self.session:
            self.session.__exit__(*exc)
        return False

    def listing(self):
        self.limiter.wait(self.company["careers_url"])
        raw, status = self.session.listing(
            self.company["careers_url"], self.selectors, self.wait_for)
        return raw, status, "playwright"

    def detail(self, url):
        if not url:
            return ""
        self.limiter.wait(url)
        return self.session.detail(url)


class _StaticFetcher:
    needs_detail = True

    def __init__(self, company, settings, limiter, selectors):
        self.company, self.settings, self.limiter = company, settings, limiter
        self.selectors = selectors

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self):
        self.limiter.wait(self.company["careers_url"])
        raw, status = static_scraper.listing(
            self.company["careers_url"], self.selectors, self.settings)
        return raw, status, "static"

    def detail(self, url):
        if not url:
            return ""
        self.limiter.wait(url)
        return static_scraper.detail(url, self.settings)


@contextmanager
def make_fetcher(company: dict, profile: dict, settings: dict, limiter: RateLimiter):
    ats = (company.get("ats_type") or "auto").lower()
    if ats == "auto":
        ats = detect_ats(company, settings)

    if ats == "greenhouse":
        f = _ApiFetcher(company, settings, limiter, greenhouse)
    elif ats == "lever":
        f = _ApiFetcher(company, settings, limiter, lever)
    elif ats == "ashby":
        f = _ApiFetcher(company, settings, limiter, ashby)
    elif ats == "smartrecruiters":
        f = _ApiFetcher(company, settings, limiter, smartrecruiters)
    elif ats == "talemetry":
        f = TalemetryFetcher(company, settings, limiter,
                             query=profile.get("ats_query", "product"))
    elif ats == "workday":
        f = WorkdayFetcher(company, settings, limiter,
                           query=profile.get("ats_query", "product"))
    elif ats == "static":
        f = _StaticFetcher(company, settings, limiter, profile.get("selectors", {}))
    else:  # custom / unknown -> Playwright
        f = _PlaywrightFetcher(company, settings, limiter,
                               profile.get("selectors", {}),
                               profile.get("wait_for"))
    with f as fetcher:
        yield fetcher
