"""Ashby ATS adapter — Rung 1 JSON API (SPEC §4.1). Rich listing incl. descriptions."""
from __future__ import annotations

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"

EMP = {"FullTime": "Full time", "PartTime": "Part time",
       "Contract": "Contract", "Intern": "Contract", "Temporary": "Contract"}


def _locations(job) -> str:
    parts = [job.get("location") or ""]
    for sec in job.get("secondaryLocations") or []:
        if isinstance(sec, dict):
            parts.append(sec.get("location") or sec.get("locationName") or "")
        elif isinstance(sec, str):
            parts.append(sec)
    if job.get("isRemote") and "remote" not in " ".join(parts).lower():
        parts.append("Remote")
    return "; ".join(p for p in parts if p)


def fetch_listing(ats_slug: str, http) -> list[dict]:
    out = []
    for j in http.get_json(API.format(slug=ats_slug)).get("jobs", []):
        if not j.get("isListed", True):
            continue
        desc = j.get("descriptionPlain", "") or ""
        out.append({
            "title": (j.get("title") or "").strip(),
            "location": _locations(j),
            "url": j.get("jobUrl") or j.get("applyUrl", ""),
            "posted_date": j.get("publishedAt"),
            "freshness_date": j.get("publishedAt"),
            "description": desc,
            "employment_type": EMP.get(j.get("employmentType"), ""),
            "salary_text": desc,
            "source_type": "ATS",
            "source_detail": "Ashby",
        })
    return out
