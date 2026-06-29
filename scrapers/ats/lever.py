"""Lever ATS adapter — Rung 1 JSON API (SPEC §4.1)."""
from __future__ import annotations

from scrapers.htmltext import html_to_markdown

API = "https://api.lever.co/v0/postings/{slug}?mode=json"


def _markdown(j) -> str:
    """Assemble the full posting as Markdown: opening + each structured list
    (responsibilities, requirements…) + closing."""
    parts = [html_to_markdown(j.get("description", ""))]
    for lst in j.get("lists") or []:
        title = (lst.get("text") or "").strip()
        body = html_to_markdown(lst.get("content", ""))
        if not body:
            continue
        parts.append(f"## {title}\n\n{body}" if title else body)
    parts.append(html_to_markdown(j.get("additional", "")))
    return "\n\n".join(p for p in parts if p).strip()


def fetch_listing(ats_slug: str, http) -> list[dict]:
    out = []
    for j in http.get_json(API.format(slug=ats_slug)):
        cats = j.get("categories", {}) or {}
        plain = (j.get("descriptionPlain") or "")
        out.append({
            "title": (j.get("text") or "").strip(),
            "location": (cats.get("location") or "").strip(),
            "url": j.get("hostedUrl", ""),
            "posted_date": j.get("createdAt"),
            "description": _markdown(j) or plain.strip(),
            "employment_type": (cats.get("commitment") or "").strip(),
            "salary_text": plain + " " + (j.get("additionalPlain") or ""),
            "source_type": "ATS",
            "source_detail": "Lever",
        })
    return out
