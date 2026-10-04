"""SmartRecruiters ATS adapter — Rung 1 JSON API (SPEC §4.1). Listing-only.

Uses the API's `q=product` prefilter (every PM title contains "product"); the
title classifier does the precise filtering. Descriptions need a per-posting
detail call, deferred for now (job URL is emitted for the user).
"""
from __future__ import annotations

from urllib.parse import urlsplit

from scrapers.htmltext import html_to_markdown

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


def fetch_listing(ats_slug: str, http) -> list[dict]:
    out, offset, total = [], 0, None
    while True:
        data = http.get_json(API.format(slug=ats_slug),
                             params={"q": "product", "limit": 100, "offset": offset})
        total = data.get("totalFound", 0) if total is None else total
        content = data.get("content", [])
        for j in content:
            emp = (j.get("typeOfEmployment") or {}).get("label", "")
            loc = j.get("location") if isinstance(j.get("location"), dict) else {}
            out.append({
                "title": (j.get("name") or "").strip(),
                "location": _location(j.get("location")),
                "url": f"https://jobs.smartrecruiters.com/{ats_slug}/{j.get('id')}",
                "posted_date": j.get("releasedDate"),
                "freshness_date": j.get("releasedDate"),
                "description": "",
                "employment_type": EMP.get(emp.lower(),
                                           emp.replace("-", " ").title() if emp else ""),
                # only the flags that are set say anything: both false = not stated
                "workplace": ("hybrid" if loc.get("hybrid")
                              else "remote" if loc.get("remote") else ""),
                "salary_text": "",
                "source_type": "ATS",
                "source_detail": "SmartRecruiters",
            })
        offset += len(content)
        if not content or offset >= total:
            break
    return out


def fetch_detail(url: str, http) -> str:
    """Fetch the posting's description sections (SPEC §4.4 / b)."""
    parts = urlsplit(url).path.strip("/").split("/")
    if len(parts) < 2:
        return ""
    slug, pid = parts[-2], parts[-1]
    data = http.get_json(f"{API.format(slug=slug)}/{pid}")
    secs = (data.get("jobAd") or {}).get("sections") or {}

    def md(key):
        return html_to_markdown((secs.get(key) or {}).get("text", ""))

    chunks = [md("companyDescription"), md("jobDescription")]
    quals = md("qualifications")
    if quals:                                   # labelled so requirements extraction finds it
        chunks.append("## Requirements\n\n" + quals)
    chunks.append(md("additionalInformation"))
    return "\n\n".join(c for c in chunks if c)
