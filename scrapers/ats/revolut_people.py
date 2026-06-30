"""Revolut People ATS adapter — Rung 1 JSON API (e.g. Cleo).

`revolutpeople.com` is Revolut's white-label hiring platform; each company is a
tenant in the path. Public JSON API (no Cloudflare on the API itself):
`https://revolutpeople.com/api/{tenant}/external/v3/postings?page=N` → {pages, count,
results:[{id,title,locations:[{name,type,country:{name}}],function}]}. Listing-only
(no description in the feed); structured locations feed the UK filter directly.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from scrapers.htmltext import html_to_markdown
from scrapers.result import EMPTY, OK, ListingResult

API = "https://revolutpeople.com/api/{tenant}/external/v3/postings"
_HEADERS = {"Accept": "application/json"}


def _location(job) -> str:
    parts = []
    for loc in job.get("locations") or []:
        name = loc.get("name") or (loc.get("country") or {}).get("name") or ""
        if not name:
            continue
        if loc.get("type") == "remote" and "remote" not in name.lower():
            name += " (remote)"
        parts.append(name)
    return "; ".join(dict.fromkeys(parts))   # de-dupe, preserve order


class RevolutPeopleFetcher:
    needs_detail = True           # description comes from the per-posting detail call
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
