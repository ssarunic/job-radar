"""Greenhouse ATS adapter — Rung 1 JSON API (SPEC §4.1). No browser needed."""
from __future__ import annotations

from scrapers.htmltext import html_to_text as _text

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


def fetch_listing(ats_slug: str, http) -> list[dict]:
    jobs = http.get_json(API.format(slug=ats_slug)).get("jobs", [])
    out = []
    for j in jobs:
        out.append({
            "title": j.get("title", "").strip(),
            "location": (j.get("location") or {}).get("name", "").strip(),
            "url": j.get("absolute_url", ""),
            "posted_date": j.get("first_published") or j.get("updated_at"),
            # recency tests freshness (live feed => still open), not first-publish
            "freshness_date": j.get("updated_at") or j.get("first_published"),
            "description": _text(j.get("content", "")),
            "employment_type": "",   # not in GH payload; inferred at normalisation
            "salary_text": _text(j.get("content", "")),  # salary parsed from body
            "source_type": "ATS",
            "source_detail": "Greenhouse",
        })
    return out
