"""SmartRecruiters ATS adapter — Rung 1 JSON API (SPEC §4.1). Listing-only.

Uses the API's `q=product` prefilter (every PM title contains "product"); the
title classifier does the precise filtering. Descriptions need a per-posting
detail call, deferred for now (job URL is emitted for the user).
"""
from __future__ import annotations

from urllib.parse import urlsplit

import requests

from scrapers.htmltext import html_to_text

API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
NEEDS_DETAIL = True
EMP = {"full-time": "Full time", "part-time": "Part time",
       "contractor": "Contract", "temporary": "Contract", "intern": "Contract"}


def _location(loc: dict) -> str:
    if not isinstance(loc, dict):
        return str(loc or "")
    base = loc.get("fullLocation") or ", ".join(
        b for b in (loc.get("city"), loc.get("country")) if b)
    if loc.get("remote"):
        base += "; Remote"
    if loc.get("hybrid"):
        base += "; Hybrid"
    return base


def fetch_listing(ats_slug: str, settings: dict) -> list[dict]:
    headers = {"User-Agent": settings.get("user_agent", "JSA")}
    timeout = settings.get("request_timeout", 20)
    out, offset, total = [], 0, None
    while True:
        r = requests.get(API.format(slug=ats_slug),
                         params={"q": "product", "limit": 100, "offset": offset},
                         headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        total = data.get("totalFound", 0) if total is None else total
        content = data.get("content", [])
        for j in content:
            emp = (j.get("typeOfEmployment") or {}).get("label", "")
            out.append({
                "title": (j.get("name") or "").strip(),
                "location": _location(j.get("location")),
                "url": f"https://jobs.smartrecruiters.com/{ats_slug}/{j.get('id')}",
                "posted_date": j.get("releasedDate"),
                "freshness_date": j.get("releasedDate"),
                "description": "",
                "employment_type": EMP.get(emp.lower(), emp.replace("-", " ").title() if emp else ""),
                "salary_text": "",
                "source_type": "ATS",
                "source_detail": "SmartRecruiters",
            })
        offset += len(content)
        if not content or offset >= total:
            break
    return out


def fetch_detail(url: str, settings: dict) -> str:
    """Fetch the posting's description sections (SPEC §4.4 / b)."""
    parts = urlsplit(url).path.strip("/").split("/")
    if len(parts) < 2:
        return ""
    slug, pid = parts[-2], parts[-1]
    r = requests.get(f"{API.format(slug=slug)}/{pid}",
                     headers={"User-Agent": settings.get("user_agent", "JSA")},
                     timeout=settings.get("request_timeout", 20))
    r.raise_for_status()
    secs = (r.json().get("jobAd") or {}).get("sections") or {}

    def text(key):
        return html_to_text((secs.get(key) or {}).get("text", ""))

    chunks = [text("companyDescription"), text("jobDescription")]
    quals = text("qualifications")
    if quals:                                   # labelled so requirements extraction finds it
        chunks.append("Requirements\n" + quals)
    chunks.append(text("additionalInformation"))
    return "\n\n".join(c for c in chunks if c)
