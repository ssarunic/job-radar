"""Talemetry (Jobvite/Radancy) ATS adapter — e.g. NatWest.

Cloudflare-protected, but the wall is fingerprint-based (passive), so curl_cffi
impersonating Safari's TLS fingerprint gets through with **no browser** — both the
`jobs.json` listing API and the detail pages. Detail bodies come from the page's
schema.org `JobPosting` JSON-LD, which gives clean Markdown plus structured
employmentType + datePosted (richer than the old rendered-text scrape).

Every target PM title contains "product", so `q=product` is an effective
server-side prefilter; the title classifier does the precise work.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote_plus, urlsplit

from bs4 import BeautifulSoup
from curl_cffi import requests as creq

from scrapers.htmltext import html_to_markdown
from scrapers.result import BLOCKED, EMPTY, ERROR, OK, ListingResult

_IMPERSONATE = "safari"   # Safari fingerprint clears NatWest's Cloudflare; chrome does not
_EMP = {"FULL_TIME": "Full time", "PART_TIME": "Part time",
        "CONTRACTOR": "Contract", "TEMPORARY": "Contract", "INTERN": "Contract"}


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


def jobposting_ld(html: str) -> dict | None:
    """Extract the schema.org JobPosting JSON-LD from a detail page (tolerant of
    trailing commas, which these blocks sometimes contain)."""
    soup = BeautifulSoup(html, "lxml")
    for s in soup.find_all("script", type="application/ld+json"):
        raw = s.string or ""
        try:
            obj = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
        except Exception:
            continue
        for o in (obj if isinstance(obj, list) else [obj]):
            if isinstance(o, dict) and "JobPosting" in str(o.get("@type", "")):
                return o
    return None


class TalemetryFetcher:
    needs_detail = True
    live_listing = True   # ATS board lists only currently-open roles
    check_robots = True
    rung_name = "talemetry"

    def __init__(self, company, http, query="product", per_page=100):
        self.company, self.http = company, http
        self.careers_url = company["careers_url"]
        self.origin = _origin(company["careers_url"])
        self.query = query
        self.per_page = per_page
        self.timeout = http.settings.get("request_timeout", 20)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _get(self, url):
        self.http.wait(self.origin)   # polite per-domain rate limit
        return creq.get(url, impersonate=_IMPERSONATE, timeout=self.timeout)

    def listing(self) -> ListingResult:
        api = (self.origin + "/search/jobs.json?search_type=talemetry"
               f"&q={quote_plus(self.query)}&per_page={self.per_page}")
        try:
            first = self._get(api + "&page=1")
        except Exception as e:
            return ListingResult(ERROR, [], self.rung_name, str(e)[:120])
        if first.status_code == 403:
            return ListingResult(BLOCKED, [], self.rung_name, "Cloudflare challenge")
        if first.status_code != 200:
            return ListingResult(ERROR, [], self.rung_name, f"HTTP {first.status_code}")
        data = first.json()
        total = int(data.get("total_entries", 0))
        per = int(data.get("per_page", self.per_page)) or self.per_page
        entries = list(data.get("entries", []))
        for page_no in range(2, (total + per - 1) // per + 1 if total else 1):
            try:
                entries.extend(self._get(f"{api}&page={page_no}").json().get("entries", []))
            except Exception:
                break

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
        """Clean Markdown ad from the JSON-LD JobPosting, prefixed with the
        structured employment type + posted date so the pipeline parses them."""
        if not url or url == self.origin:
            return ""
        try:
            html = self._get(url).text
        except Exception:
            return ""
        ld = jobposting_ld(html)
        if not ld:
            return ""
        header = (f"Employment type: {_EMP.get(ld.get('employmentType'), '')}\n"
                  f"Workplace type: {ld.get('jobLocationType') or ''}\n"
                  f"Date posted: {ld.get('datePosted', '')}\n\n")
        return header + html_to_markdown(ld.get("description", ""))
