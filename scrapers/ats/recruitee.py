"""Recruitee ATS adapter — Rung 1 JSON API (SPEC: recruitee-adapter.md).

Recruitee boards (`{slug}.recruitee.com`, often on a custom domain like
`careers.hostaway.com`) expose a public, no-auth endpoint the page itself calls:
`GET {careers_origin}/api/offers/`. The custom domain **proxies** the API, so we use
the careers-URL origin directly — no need to resolve the Recruitee tenant slug (which
isn't even present on custom-domain pages). Everything ships inline — title, location,
HTML description + requirements, employment type — so there's no detail call.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from scrapers.htmltext import html_to_markdown
from scrapers.result import EMPTY, OK, ListingResult

_JSON_HEADERS = {"Accept": "application/json"}

_EMP = {
    "fulltime": "Full time", "fulltime_permanent": "Full time",
    "parttime": "Part time", "parttime_permanent": "Part time",
    "contract": "Contract", "temporary": "Contract",
    "internship": "Contract", "freelance": "Contract", "apprenticeship": "Contract",
}


def _employment(code: str) -> str:
    code = (code or "").lower()
    return _EMP.get(code, code.replace("_", " ").title())


def _location(o: dict) -> str:
    """Recruitee's `location` is often the generic 'Remote job'; compose a string the
    location filter can reason about — keep the country so UK/EU-remote is accepted
    and US-only remote is rejected."""
    country = (o.get("country") or "").strip()
    if o.get("remote"):
        return f"Remote — {country}" if country else "Remote"
    bits = [o.get("city"), o.get("state_name"), country]
    composed = ", ".join(dict.fromkeys(b.strip() for b in bits if b and b.strip()))
    return composed or (o.get("location") or "").strip()


def _salary_text(sal) -> str:
    """Recruitee's `salary` is a dict {min,max,period,currency} (often all null), not
    a string — coerce so the downstream salary parser gets text, never a dict."""
    if isinstance(sal, str):
        return sal
    if isinstance(sal, dict):
        lo, hi, cur = sal.get("min"), sal.get("max"), (sal.get("currency") or "")
        if lo or hi:
            rng = f"{lo}" if lo == hi else f"{lo}–{hi}"
            return f"{cur} {rng}".strip()
    return ""


def _markdown(o: dict) -> str:
    parts = [html_to_markdown(o.get("description", ""))]
    req = html_to_markdown(o.get("requirements", ""))
    if req:
        parts.append(f"## Requirements\n\n{req}")
    return "\n\n".join(p for p in parts if p).strip()


def _map(o: dict) -> dict:
    return {
        "title": (o.get("title") or "").strip(),
        "location": _location(o),
        "url": o.get("careers_url") or o.get("careers_apply_url") or "",
        "posted_date": o.get("published_at") or o.get("created_at"),
        "description": _markdown(o),
        "employment_type": _employment(o.get("employment_type_code")),
        "salary_text": _salary_text(o.get("salary")),
        "source_type": "ATS",
        "source_detail": "Recruitee",
    }


class RecruiteeFetcher:
    needs_detail = False       # descriptions ship inline in the listing
    live_listing = True   # ATS board lists only currently-open roles
    check_robots = False       # documented public JSON API
    rung_name = "recruitee"

    def __init__(self, company, http, query=None):
        self.company, self.http = company, http
        p = urlsplit(company["careers_url"])
        self.api = f"{p.scheme}://{p.netloc}/api/offers/"   # origin proxies the API

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self) -> ListingResult:
        offers = self.http.get_json(self.api, headers=_JSON_HEADERS).get("offers", [])
        out = [_map(o) for o in offers
               if (o.get("status") or "published").lower() == "published"]
        return ListingResult(OK if out else EMPTY, out, self.rung_name)

    def detail(self, url) -> str:
        return ""   # never called (needs_detail=False) — descriptions are inline
