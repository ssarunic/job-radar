"""Workday ATS adapter — Rung 1 JSON `cxs` API (SPEC §4.1). Listing-only.

Workday's search is a POST to a tenant/site-specific `cxs` endpoint derived from
the company's careers URL (`https://{tenant}.wdN.myworkdayjobs.com/{site}`).
Uses `searchText=product` as a server-side prefilter; the classifier does the
precise filtering. `postedOn` is relative text ("Posted 30+ Days Ago"), so it's
left unparsed (recency keeps it). Descriptions need per-job calls — deferred.
"""
from __future__ import annotations

from urllib.parse import urlsplit

import requests

from scrapers.htmltext import html_to_text


class WorkdayFetcher:
    needs_detail = True  # detail call adds description + real date + employment type

    def __init__(self, company, settings, limiter, query="product"):
        self.company, self.settings, self.limiter = company, settings, limiter
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

    def listing(self):
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                   "Content-Type": "application/json"}
        timeout = self.settings.get("request_timeout", 20)
        max_pages = self.settings.get("ats_max_pages", 25)  # Workday caps limit at 20
        out, offset, total, pages = [], 0, None, 0
        while True:
            self.limiter.wait(self.base)
            r = requests.post(self.cxs + "/jobs", headers=headers, timeout=timeout,
                              json={"appliedFacets": {}, "limit": 20,
                                    "offset": offset, "searchText": self.query})
            r.raise_for_status()
            data = r.json()
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
        return out, ("ok" if out else "empty"), "workday"

    def detail(self, url):
        """Fetch jobDescription + structured fields. The date/employment lines are
        embedded as text so the pipeline's generic parsers pick them up (SPEC b)."""
        if not url or url == self.base:
            return ""
        path = url.split(f"{self.base}/{self.site}", 1)[-1]
        self.limiter.wait(self.base)
        r = requests.get(self.cxs + path,
                         headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                         timeout=self.settings.get("request_timeout", 20))
        r.raise_for_status()
        jpi = r.json().get("jobPostingInfo", {}) or {}
        header = (f"Employment type: {jpi.get('timeType','')}\n"
                  f"Date posted: {jpi.get('startDate','')}\n"
                  f"Location: {jpi.get('location','')}\n\n")
        return header + html_to_text(jpi.get("jobDescription", ""))
