"""Revolut People ATS adapter — Rung 1 JSON API (e.g. Cleo), plus a web variant
for Revolut's own site.

`revolutpeople.com` is Revolut's white-label hiring platform; each company is a
tenant in the path. Public JSON API (no Cloudflare on the API itself):
`https://revolutpeople.com/api/{tenant}/external/v3/postings?page=N` → {pages, count,
results:[{id,title,locations:[{name,type,country:{name}}],function}]}. Listing-only
(no description in the feed); structured locations feed the UK filter directly.

Revolut's own tenant 403s that API, so `RevolutWebFetcher` scrapes
`www.revolut.com/careers` instead: the pages are Next.js SSG with the full board
embedded in `__NEXT_DATA__`, behind a passive Cloudflare wall that curl_cffi
impersonation clears (as Talemetry). robots.txt disallows the `/_next/data/*.json`
routes but allows the HTML pages, so only pages are fetched.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from curl_cffi import requests as creq

from scrapers.htmltext import html_to_markdown
from scrapers.result import BLOCKED, EMPTY, ERROR, OK, ListingResult

API = "https://revolutpeople.com/api/{tenant}/external/v3/postings"
_HEADERS = {"Accept": "application/json"}
_IMPERSONATE = "chrome"
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def _location(job) -> str:
    parts = []
    for loc in job.get("locations") or []:
        country = loc.get("country")
        name = (loc.get("name")
                or (country.get("name") if isinstance(country, dict) else country) or "")
        if not name:
            continue
        if loc.get("type") == "remote" and "remote" not in name.lower():
            name += " (remote)"
        parts.append(name)
    return "; ".join(dict.fromkeys(parts))   # de-dupe, preserve order


def next_data(html: str) -> dict:
    """The pageProps dict from a Next.js page's __NEXT_DATA__ blob, or {}."""
    m = _NEXT_DATA_RE.search(html or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(1)).get("props", {}).get("pageProps", {}) or {}
    except Exception:
        return {}


def make_fetcher(company, http):
    """Pick the API tenant fetcher or the revolut.com web fetcher by careers host."""
    if "revolutpeople" in urlsplit(company.get("careers_url", "")).netloc.lower():
        return RevolutPeopleFetcher(company, http)
    return RevolutWebFetcher(company, http)


class RevolutPeopleFetcher:
    needs_detail = True           # description comes from the per-posting detail call
    live_listing = True   # ATS board lists only currently-open roles
    check_robots = False          # documented JSON API
    rung_name = "revolutpeople"

    def __init__(self, company, http, query=None):
        self.company, self.http = company, http
        self.tenant = (company.get("ats_slug")
                       or urlsplit(company["careers_url"]).path.strip("/").split("/")[0])
        self.base = "https://revolutpeople.com"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self) -> ListingResult:
        api = API.format(tenant=self.tenant)
        out, page, pages = [], 1, 1
        while page <= pages:
            data = self.http.get_json(f"{api}?page={page}", headers=_HEADERS)
            pages = int((data.get("pages") or {}).get("total") or 1)
            for j in data.get("results", []):
                jid = j.get("id")
                out.append({
                    "title": (j.get("title") or "").strip(),
                    "location": _location(j),
                    "url": f"{self.base}/{self.tenant}/public/careers/position/{jid}",
                    "posted_date": None,
                    "description": "",
                    "employment_type": "",
                    "salary_text": "",
                    "source_type": "ATS",
                    "source_detail": "RevolutPeople",
                })
            page += 1
        return ListingResult(OK if out else EMPTY, out, self.rung_name)

    def detail(self, url):
        """Fetch the posting's description (HTML) from the v2 detail endpoint and
        convert to Markdown. The v3 listing omits it; v2 by-id includes it."""
        if not url:
            return ""
        pid = urlsplit(url).path.rstrip("/").split("/")[-1]
        if not pid:
            return ""
        data = self.http.get_json(
            f"{self.base}/api/{self.tenant}/external/v2/postings/{pid}", headers=_HEADERS)
        return html_to_markdown(data.get("description", ""))


class RevolutWebFetcher:
    """Revolut's own board (www.revolut.com/careers) via __NEXT_DATA__ on the HTML
    pages. Listing (`pageProps.positions`) carries id/text/locations but no body;
    the position page (`pageProps.position`) has the description."""
    needs_detail = True
    live_listing = True   # careers site renders only currently-open roles
    check_robots = True   # HTML pages, not a documented API — honour robots.txt
    rung_name = "revolutweb"

    def __init__(self, company, http):
        self.company, self.http = company, http
        self.careers_url = company["careers_url"].rstrip("/")
        p = urlsplit(self.careers_url)
        self.origin = f"{p.scheme}://{p.netloc}"
        self.timeout = http.settings.get("request_timeout", 20)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _get(self, url):
        self.http.wait(self.origin)   # polite per-domain rate limit
        return creq.get(url, impersonate=_IMPERSONATE, timeout=self.timeout)

    def listing(self) -> ListingResult:
        try:
            resp = self._get(self.careers_url)
        except Exception as e:
            return ListingResult(ERROR, [], self.rung_name, str(e)[:120])
        if resp.status_code == 403:
            return ListingResult(BLOCKED, [], self.rung_name, "Cloudflare challenge")
        if resp.status_code != 200:
            return ListingResult(ERROR, [], self.rung_name, f"HTTP {resp.status_code}")
        positions = next_data(resp.text).get("positions") or []
        out = [{
            "title": (j.get("text") or "").strip(),
            "location": _location(j),
            "url": f"{self.origin}/careers/position/{j.get('id')}/",
            "posted_date": None,
            "description": "",
            "employment_type": "",
            "salary_text": "",
            "source_type": "CompanySite",
            "source_detail": "RevolutPeople",
        } for j in positions if j.get("id")]
        return ListingResult(OK if out else EMPTY, out, self.rung_name)

    def detail(self, url):
        if not url:
            return ""
        try:
            resp = self._get(url)
        except Exception:
            return ""
        if resp.status_code != 200:
            return ""
        position = next_data(resp.text).get("position") or {}
        return html_to_markdown(position.get("description", ""))
