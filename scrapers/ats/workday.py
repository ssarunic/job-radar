"""Workday ATS adapter — Rung 1 JSON `cxs` API (SPEC §4.1).

Workday's search is a POST to a tenant/site-specific `cxs` endpoint derived from
the company's careers URL (`https://{tenant}.wdN.myworkdayjobs.com/{site}`).
Uses `searchText=product` as a server-side prefilter, **plus a discovered UK
location facet** so big tenants (NVIDIA: 2000 product hits, Barclays: 837) collapse
to their UK roles (NVIDIA 42) — under the page cap, and a trustworthy "0 kept".
The classifier does the precise filtering. Listing has no description; detail()
adds description + the real startDate + employment type (SPEC b). `limit` is
hard-capped at 20 by Workday, so depth = page count only.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from scrapers.htmltext import html_to_markdown
from scrapers.result import EMPTY, OK, ListingResult

_JSON_HEADERS = {"Accept": "application/json"}

# A facet value's descriptor is UK-ish. Country terms are preferred (broadest);
# bare "uk" is intentionally excluded (matches Ukraine, Dukinfield, ...).
_UK_RX = re.compile(r"united kingdom|great britain|\bengland\b|scotland|wales|"
                    r"northern ireland|\blondon\b", re.I)
_UK_COUNTRY_RX = re.compile(r"united kingdom|great britain|^\s*england\s*$", re.I)


def _pick_uk_facet(facets: list) -> tuple:
    """Walk Workday's (nested, tenant-specific) facet tree and pick ONE
    facetParameter + value ids to constrain the search to the UK. Returns
    (param, [ids]) or (None, None) if no UK facet is present. Prefers a
    country-level value (e.g. 'United Kingdom') over city/site values, and uses a
    single param so values OR together (avoids AND over-constraining)."""
    matches = []  # (param, id, count, is_country)

    def walk(nodes, parent_param):
        for n in nodes:
            param = n.get("facetParameter") or parent_param
            desc = n.get("descriptor") or ""
            if n.get("id") and param and _UK_RX.search(desc):
                matches.append((param, n["id"], n.get("count") or 0,
                                bool(_UK_COUNTRY_RX.search(desc))))
            walk(n.get("values") or [], param)

    for f in facets:
        walk(f.get("values") or [], f.get("facetParameter"))
    if not matches:
        return None, None

    pool = [m for m in matches if m[3]] or matches      # country-level if any
    by_param: dict = {}
    for param, vid, count, _ in pool:
        slot = by_param.setdefault(param, {"ids": [], "count": 0})
        if vid not in slot["ids"]:
            slot["ids"].append(vid)
            slot["count"] += count
    best = max(by_param.items(), key=lambda kv: kv[1]["count"])  # broadest coverage
    return best[0], best[1]["ids"]


class WorkdayFetcher:
    needs_detail = True
    live_listing = True   # ATS board lists only currently-open roles
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

        # Discover a UK location facet (1 cheap call) to constrain the search
        # server-side; falls back to no facet (today's behaviour) if none found.
        facets = self.http.post_json(
            self.cxs + "/jobs", headers=_JSON_HEADERS,
            json={"appliedFacets": {}, "limit": 1, "offset": 0,
                  "searchText": self.query}).get("facets", [])
        param, ids = _pick_uk_facet(facets)
        applied = {param: ids} if param else {}
        if applied:
            print(f"   … Workday: UK facet {param} ({len(ids)} value(s)) applied")

        out, offset, total, pages = [], 0, None, 0
        while True:
            data = self.http.post_json(
                self.cxs + "/jobs", headers=_JSON_HEADERS,
                json={"appliedFacets": applied, "limit": 20, "offset": offset,
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
        return header + html_to_markdown(jpi.get("jobDescription", ""))
