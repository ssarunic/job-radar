"""Lever ATS adapter — Rung 1 JSON API (SPEC §4.1)."""
from __future__ import annotations

import requests

API = "https://api.lever.co/v0/postings/{slug}?mode=json"


def fetch_listing(ats_slug: str, settings: dict) -> list[dict]:
    url = API.format(slug=ats_slug)
    r = requests.get(
        url,
        headers={"User-Agent": settings.get("user_agent", "JobSeekAssistant")},
        timeout=settings.get("request_timeout", 20),
    )
    r.raise_for_status()
    out = []
    for j in r.json():
        cats = j.get("categories", {}) or {}
        out.append({
            "title": (j.get("text") or "").strip(),
            "location": (cats.get("location") or "").strip(),
            "url": j.get("hostedUrl", ""),
            "posted_date": j.get("createdAt"),  # epoch ms; normalised downstream
            "description": (j.get("descriptionPlain") or "").strip(),
            "employment_type": (cats.get("commitment") or "").strip(),
            "salary_text": (j.get("descriptionPlain") or ""),
            "source_type": "ATS",
            "source_detail": "Lever",
        })
    return out
