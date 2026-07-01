"""Oracle Recruiting Cloud (ORC) adapter — Rung 1 JSON REST API (SPEC: oracle-adapter.md).

Oracle Fusion HCM "Candidate Experience" (`*.fa.*.oraclecloud.com/hcmUI/
CandidateExperience/.../sites/{SITE}/jobs`) is a JS SPA over a public REST endpoint
the page itself calls (no auth). List = `recruitingCEJobRequisitions`; detail =
`recruitingCEJobRequisitionDetails`. Big tenants are huge (JP Morgan: 7005 reqs), so
we discover a **UK location facet** (preferring the country-level node) and constrain
the search server-side before the classifier does the precise senior-PM filtering.
Listing carries only a short description; detail() adds the full body.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from scrapers.htmltext import html_to_markdown
from scrapers.result import EMPTY, OK, ListingResult

_JSON_HEADERS = {"Accept": "application/json"}

_UK_RX = re.compile(r"united kingdom|great britain|\bengland\b|scotland|wales|"
                    r"northern ireland|\blondon\b", re.I)
_UK_COUNTRY_RX = re.compile(r"^\s*united kingdom\s*$|great britain|^\s*england\s*$", re.I)


def _pick_uk_location(locations_facet) -> tuple | None:
    """Oracle's `locationsFacet` is a flat list of `{Name, Id}` nodes (the US→NY→NYC
    hierarchy is flattened). Pick ONE UK facet id, preferring the country-level
    'United Kingdom' node over city-level ones. Returns (id, name) or None."""
    matches = []  # (id, is_country, name)
    for n in (locations_facet or []):
        name = n.get("Name") or ""
        if n.get("Id") and _UK_RX.search(name):
            matches.append((str(n["Id"]), bool(_UK_COUNTRY_RX.search(name)), name))
    if not matches:
        return None
    country = [m for m in matches if m[1]]
    pick = (country or matches)[0]
    return pick[0], pick[2]


def _emp(j: dict) -> str:
    """Best-effort employment string — the pipeline's classifier + body-scan refine it."""
    return (j.get("JobSchedule") or j.get("JobType") or j.get("ContractType") or "").strip()


class OracleFetcher:
    needs_detail = True
    check_robots = False  # documented public JSON API
    rung_name = "oracle"

    def __init__(self, company, http, query=None):
        self.company, self.http = company, http
        p = urlsplit(company["careers_url"])
        self.host = p.netloc
        self.base = f"https://{self.host}"
        self.api = f"{self.base}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        self.detail_api = (f"{self.base}/hcmRestApi/resources/latest/"
                           "recruitingCEJobRequisitionDetails")
        m = re.search(r"/sites/([^/]+)", p.path or "")
        self.site = m.group(1) if m else "CX_1001"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _reqs(self, finder: str, expand: str | None = None) -> dict:
        params = "onlyData=true" + (f"&expand={expand}" if expand else "")
        url = f"{self.api}?{params}&finder=findReqs;{finder}"
        return self.http.get_json(url, headers=_JSON_HEADERS)

    def listing(self) -> ListingResult:
        max_pages = self.http.settings.get("ats_max_pages", 25)

        # 1 cheap call: discover a UK location facet to constrain the search server-side.
        fd = self._reqs(f"siteNumber={self.site},facetsList=LOCATIONS,limit=1")
        loc = _pick_uk_location((fd.get("items") or [{}])[0].get("locationsFacet"))
        loc_clause = f",selectedLocationsFacet={loc[0]}" if loc else ""
        if loc:
            print(f"   … Oracle: UK location facet '{loc[1]}' applied")

        out, offset, total, pages = [], 0, None, 0
        while True:
            fin = (f"siteNumber={self.site}{loc_clause},limit=100,offset={offset},"
                   "sortBy=POSTING_DATES_DESC")
            it = (self._reqs(fin, expand="requisitionList").get("items") or [{}])[0]
            total = it.get("TotalJobsCount", 0) if total is None else total
            reqs = it.get("requisitionList") or []
            for j in reqs:
                rid = str(j.get("Id") or "")
                out.append({
                    "title": (j.get("Title") or "").strip(),
                    "location": (j.get("PrimaryLocation") or "").strip(),
                    "url": (f"{self.base}/hcmUI/CandidateExperience/en/sites/"
                            f"{self.site}/job/{rid}"),
                    "posted_date": j.get("PostedDate") or None,
                    "description": (j.get("ShortDescriptionStr") or "").strip(),
                    "employment_type": _emp(j),
                    "salary_text": "",
                    "source_type": "ATS",
                    "source_detail": "Oracle",
                })
            offset += len(reqs)
            pages += 1
            if not reqs or offset >= (total or 0):
                break
            if pages >= max_pages:
                print(f"   … Oracle page cap hit ({max_pages} pages, {offset}/{total}); "
                      "raise ats_max_pages to fetch all")
                break
        return ListingResult(OK if out else EMPTY, out, self.rung_name)

    def detail(self, url) -> str:
        m = re.search(r"/job/(\d+)", url or "")
        if not m:
            return ""
        fin = f'ById;Id="{m.group(1)}",siteNumber={self.site}'
        data = self.http.get_json(
            f"{self.detail_api}?onlyData=true&expand=all&finder={fin}", headers=_JSON_HEADERS)
        j = (data.get("items") or [{}])[0]
        header = (f"Employment type: {_emp(j)}\n"
                  f"Date posted: {j.get('PostedDate', '')}\n"
                  f"Location: {j.get('PrimaryLocation', '')}\n\n")
        body = j.get("ExternalDescriptionStr") or j.get("ShortDescriptionStr") or ""
        return header + html_to_markdown(body)
