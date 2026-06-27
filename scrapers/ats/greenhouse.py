"""Greenhouse ATS adapter — Rung 1 JSON API (SPEC §4.1). No browser needed."""
from __future__ import annotations

import html as _html

import requests
from bs4 import BeautifulSoup

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


def _text(content_html: str) -> str:
    if not content_html:
        return ""
    soup = BeautifulSoup(_html.unescape(content_html), "lxml")
    return soup.get_text("\n", strip=True)


def fetch_listing(ats_slug: str, settings: dict) -> list[dict]:
    url = API.format(slug=ats_slug)
    r = requests.get(
        url,
        headers={"User-Agent": settings.get("user_agent", "JobSeekAssistant")},
        timeout=settings.get("request_timeout", 20),
    )
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
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
