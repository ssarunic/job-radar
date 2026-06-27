"""Lever ATS adapter — Rung 1 JSON API (SPEC §4.1)."""
from __future__ import annotations

API = "https://api.lever.co/v0/postings/{slug}?mode=json"


def fetch_listing(ats_slug: str, http) -> list[dict]:
    out = []
    for j in http.get_json(API.format(slug=ats_slug)):
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
