"""Workday ATS adapter — Rung 1 JSON `cxs` API (SPEC §4.1).

Workday's search is a POST to a tenant/site-specific `cxs` endpoint derived from
the company's careers URL (`https://{tenant}.wdN.myworkdayjobs.com/{site}`).
Uses `searchText=product` as a server-side prefilter, **plus a discovered UK
location facet** so big tenants (NVIDIA: 2000 product hits, Barclays: 837) collapse
to their UK roles (NVIDIA 42) — under the page cap, and a trustworthy "0 kept".
The classifier does the precise filtering. Listing location comes from
`locationsText`, falling back to `bulletFields` for tenants that omit it
(`_listing_location`). Listing has no description; detail()
adds description + the real startDate + employment type (SPEC b). `limit` is
hard-capped at 20 by Workday, so depth = page count only.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from scrapers.htmltext import html_to_markdown
from scrapers.result import EMPTY, OK, ListingResult

_JSON_HEADERS = {"Accept": "application/json"}

# A facet value's descriptor is a UK *country* (site/city names are never used — see
# _pick_uk_facet). Bare "uk" is intentionally excluded (matches Ukraine, Dukinfield, ...).
_UK_COUNTRY_RX = re.compile(r"united kingdom|great britain|^\s*england\s*$", re.I)

# A bulletFields entry that is a job requisition id, not a location (e.g.
# 'JR0609782', 'R-12345', '2024-1234'): no spaces, contains a digit.
_REQ_ID_RX = re.compile(r"^[A-Za-z]*[-_]?\d[\w-]*$")


def _listing_location(j: dict) -> str:
    """Location for a listing row. Most tenants populate `locationsText`, but some
    (e.g. Worldpay) omit it entirely and carry the location in `bulletFields`
    (typically ['LONDON, , UNITED KINGDOM', 'JR0609782']). Without this fallback the
    row reaches the pipeline with an empty location and is dropped by the location
    filter — a board full of London roles silently keeps 0."""
    text = (j.get("locationsText") or "").strip()
    if text:
        return text
    for field in j.get("bulletFields") or []:
        field = (field or "").strip()
        if field and not _REQ_ID_RX.match(field):
            return field
    return ""


def _pick_uk_facet(facets: list) -> tuple:
    """Walk Workday's (nested, tenant-specific) facet tree and pick ONE
    facetParameter + value ids to constrain the search to the UK. Returns
    (param, [ids]) or (None, None) if the tenant exposes no **country-level** UK
    value (e.g. 'United Kingdom'). Uses a single param so values OR together
    (avoids AND over-constraining).

    Site/city values are deliberately never used. Tenants whose location facet is
    per-site (Barclays: 72 street addresses, no country node) name sites like
    'Canary Wharf, 1 Churchill Place' or 'Glasgow Campus', so a descriptor regex
    matches almost none of the UK sites — and does match street names such as
    'Lowestoft, London Road North'. Applying those ids collapsed Barclays'
    778-row 'product' search to 2 rows and silently hid every real UK role.
    Without a facet the caller pages the (newest-first) unfiltered listing and the
    location filter runs client-side, which is lossless."""
    matches = []  # (param, id, count)

    def walk(nodes, parent_param):
        for n in nodes:
            param = n.get("facetParameter") or parent_param
            desc = n.get("descriptor") or ""
            if n.get("id") and param and _UK_COUNTRY_RX.search(desc):
                matches.append((param, n["id"], n.get("count") or 0))
            walk(n.get("values") or [], param)

    for f in facets:
        walk(f.get("values") or [], f.get("facetParameter"))
    if not matches:
        return None, None

    by_param: dict = {}
    for param, vid, count in matches:
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
        max_pages = self.http.settings.get("ats_max_pages", 40)  # Workday caps limit at 20

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
        else:
            print("   … Workday: no country-level UK facet; paging the unfiltered "
                  "(newest-first) listing, filtering location client-side")

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
                    "location": _listing_location(j),
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

    def _job_info(self, url) -> dict:
        """The posting's `jobPostingInfo` record, fetched once per URL: both
        resolve_location() (Stage A) and detail() (Stage C) read it."""
        if not url or url == self.base:
            return {}
        cache = self.__dict__.setdefault("_jpi_cache", {})
        if url not in cache:
            path = url.split(f"{self.base}/{self.site}", 1)[-1]
            cache[url] = self.http.get_json(self.cxs + path).get("jobPostingInfo", {}) or {}
        return cache[url]

    def resolve_location(self, url) -> str:
        """Structured location for a row whose listing location the filter can't
        judge (pipeline Stage A hook). Listing rows only carry a site label —
        "2 Locations" for multi-site postings, or a bare street address such as
        "Canary Wharf, 1 Churchill Place" — but the detail record names the site's
        country, which is what the location filter keys on. Returns
        "<site>, <Country>; <additional site>; …" (additional sites carry no
        country in the record, so they are passed through as-is), or "" if the
        posting can't be read."""
        jpi = self._job_info(url)
        if not jpi:
            return ""
        primary = (jpi.get("location") or "").strip()
        country = ((jpi.get("jobRequisitionLocation") or {}).get("country")
                   or jpi.get("country") or {}).get("descriptor", "").strip()
        pieces = [", ".join(x for x in (primary, country) if x)]
        pieces += [str(a).strip() for a in (jpi.get("additionalLocations") or []) if str(a).strip()]
        return "; ".join(x for x in pieces if x)

    def detail(self, url) -> str:
        """jobDescription + structured fields, embedded as text so the pipeline's
        generic date/employment parsers pick them up (SPEC b)."""
        jpi = self._job_info(url)
        if not jpi:
            return ""
        header = (f"Employment type: {jpi.get('timeType','')}\n"
                  f"Date posted: {jpi.get('startDate','')}\n"
                  f"Location: {jpi.get('location','')}\n\n")
        return header + html_to_markdown(jpi.get("jobDescription", ""))
