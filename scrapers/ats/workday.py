"""Workday ATS adapter — Rung 1 JSON `cxs` API (SPEC §4.1).

Workday's search is a POST to a tenant/site-specific `cxs` endpoint derived from
the company's careers URL (`https://{tenant}.wdN.myworkdayjobs.com/{site}`).
Uses `searchText=product` as a server-side prefilter; the classifier does the
precise filtering. Listing has no description; detail() adds description + the
real startDate + employment type (SPEC b).
"""
from __future__ import annotations

from urllib.parse import urlsplit

from scrapers.htmltext import html_to_text
from scrapers.result import ListingResult, OK, EMPTY

_JSON_HEADERS = {"Accept": "application/json"}


class WorkdayFetcher:
    needs_detail = True
    check_robots = False  # documented JSON API
    rung_name = "workday"

    def __init__(self, company, http, query="product"):
        self.company, self.http = company, http
        self.query = query
        p = urlsplit(company["careers_url"])
        self.host = p.netloc
        self.tenant = self.host.split(".")[0]
        self.site = p.path.strip("/").split("/")[-1]
        self.base = f"https://{self.host}"
        self.cxs = f"{self.base}/wday/cxs/{self.tenant}/{self.site}"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self) -> ListingResult:
        max_pages = self.http.settings.get("ats_max_pages", 25)  # Workday caps limit at 20
        out, offset, total, pages = [], 0, None, 0
        while True:
            data = self.http.post_json(
                self.cxs + "/jobs", headers=_JSON_HEADERS,
                json={"appliedFacets": {}, "limit": 20, "offset": offset,
                      "searchText": self.query})
            total = data.get("total", 0) if total is None else total
            posts = data.get("jobPostings", [])
            for j in posts:
                path = j.get("externalPath", "")
                out.append({
                    "title": (j.get("title") or "").strip(),
                    "location": (j.get("locationsText") or "").strip(),
                    "url": f"{self.base}/{self.site}{path}" if path else self.base,
                    "posted_date": None,  # postedOn is relative text, unparseable
                    "description": "",
                    "employment_type": "",
                    "salary_text": "",
                    "source_type": "ATS",
                    "source_detail": "Workday",
                })
            offset += len(posts)
            pages += 1
            if not posts or offset >= total:
                break
            if pages >= max_pages:
                print(f"   … Workday page cap hit ({max_pages} pages, "
                      f"{offset}/{total}); raise ats_max_pages to fetch all")
                break
        return ListingResult(OK if out else EMPTY, out, self.rung_name)

    def detail(self, url) -> str:
        """jobDescription + structured fields, embedded as text so the pipeline's
        generic date/employment parsers pick them up (SPEC b)."""
        if not url or url == self.base:
            return ""
        path = url.split(f"{self.base}/{self.site}", 1)[-1]
        jpi = self.http.get_json(self.cxs + path).get("jobPostingInfo", {}) or {}
        header = (f"Employment type: {jpi.get('timeType','')}\n"
                  f"Date posted: {jpi.get('startDate','')}\n"
                  f"Location: {jpi.get('location','')}\n\n")
        return header + html_to_text(jpi.get("jobDescription", ""))
