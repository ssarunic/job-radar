"""Talemetry (Jobvite/Radancy) ATS adapter — e.g. NatWest.

The site is Cloudflare-protected, so the JSON search API can't be hit with
plain requests. Instead we warm a Playwright browser context (clears the
managed challenge) and call the `jobs.json` endpoint via in-page `fetch()`,
which rides the context's clearance. Detail pages enforce a stronger challenge
that headless can't clear, so this adapter is listing-only (descriptions stay
empty; the job URL is still emitted for the user to open in a real browser).

Every target PM title contains the word "product", so `q=product` is an
effective server-side prefilter; the title classifier does the precise work.
"""
from __future__ import annotations

from urllib.parse import urlsplit, quote_plus

from scrapers.playwright_scraper import PlaywrightSession
from scrapers.result import ListingResult, OK, EMPTY, BLOCKED


def _origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def _location_str(loc) -> str:
    if not isinstance(loc, dict):
        return str(loc or "")
    name = loc.get("name")
    if name:
        return name.replace(",", ", ")
    bits = [loc.get("locality"), loc.get("region_full"), loc.get("country")]
    return ", ".join(b for b in bits if b)


class TalemetryFetcher:
    # Detail pages clear Cloudflare when settings.stealth is on; without stealth
    # they get challenged and detail() returns "" (graceful).
    needs_detail = True
    check_robots = True
    rung_name = "talemetry"

    def __init__(self, company, http, query="product", per_page=100):
        self.company, self.http = company, http
        self.settings = http.settings
        self.query = query
        self.per_page = per_page
        self.origin = _origin(company["careers_url"])
        self.session = None

    def __enter__(self):
        self.session = PlaywrightSession(self.settings).__enter__()
        return self

    def __exit__(self, *exc):
        if self.session:
            self.session.__exit__(*exc)
        return False

    def listing(self) -> ListingResult:
        self.http.wait(self.origin)
        if not self.session.warm(self.origin + "/"):
            return ListingResult(BLOCKED, [], self.rung_name, "Cloudflare challenge")

        api = (self.origin + "/search/jobs.json?search_type=talemetry"
               f"&q={quote_plus(self.query)}&per_page={self.per_page}")
        first = self.session.fetch_json(api + "&page=1")
        if first is None:
            return ListingResult(BLOCKED, [], self.rung_name, "jobs.json blocked")

        total = int(first.get("total_entries", 0))
        per = int(first.get("per_page", self.per_page)) or self.per_page
        entries = list(first.get("entries", []))
        pages = (total + per - 1) // per if total else 1
        for page_no in range(2, pages + 1):
            self.http.wait(self.origin)
            data = self.session.fetch_json(f"{api}&page={page_no}")
            if not data:
                break
            entries.extend(data.get("entries", []))

        out = []
        for e in entries:
            pid = e.get("id") or e.get("talemetry_job_id")
            perma = e.get("permalink", "")
            out.append({
                "title": (e.get("title") or "").strip(),
                "location": _location_str(e.get("location")),
                "url": f"{self.origin}/jobs/{pid}-{perma}" if pid else self.origin,
                "posted_date": None,
                "description": "",
                "employment_type": "",
                "salary_text": "",
                "source_type": "CompanySite",
                "source_detail": "Talemetry",
            })
        return ListingResult(OK if out else EMPTY, out, self.rung_name)

    def detail(self, url):
        if not url or url == self.origin:
            return ""
        self.http.wait(self.origin)
        return self.session.detail(url)
