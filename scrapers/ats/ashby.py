"""Ashby ATS adapter — Rung 1 JSON API (SPEC §4.1). Rich listing incl. descriptions."""
from __future__ import annotations

from scrapers.htmltext import html_to_markdown

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


def _salary(job) -> dict | None:
    """Structured compensation from Ashby (authoritative; ?includeCompensation=true).
    Returns {min,max,currency,original_text,compensation_type} or None."""
    comp = job.get("compensation") or {}
    components = comp.get("summaryComponents") or []
    base = next((c for c in components
                 if c.get("compensationType") == "Salary" and c.get("minValue") is not None),
                None)
    if not base:
        return None
    types = {c.get("compensationType") for c in components}
    if "Bonus" in types:
        ctype = "Base+Bonus"
    elif types & {"Commission", "OTE"}:
        ctype = "OTE"
    else:
        ctype = "Base Only"
    return {
        "min": base.get("minValue"),
        "max": base.get("maxValue"),
        "currency": base.get("currencyCode"),
        "original_text": (comp.get("compensationTierSummary")
                          or comp.get("scrapeableCompensationSalarySummary")),
        "compensation_type": ctype,
    }


def fetch_listing(ats_slug: str, http) -> list[dict]:
    out = []
    for j in http.get_json(API.format(slug=ats_slug)).get("jobs", []):
        if not j.get("isListed", True):
            continue
        plain = j.get("descriptionPlain", "") or ""
        out.append({
            "title": (j.get("title") or "").strip(),
            "location": _locations(j),
            "url": j.get("jobUrl") or j.get("applyUrl", ""),
            "posted_date": j.get("publishedAt"),
            "freshness_date": j.get("publishedAt"),
            "description": html_to_markdown(j.get("descriptionHtml", "")) or plain,
            "employment_type": EMP.get(j.get("employmentType"), ""),
            "salary_text": plain,
            "salary": _salary(j),          # structured comp, preferred over regex
            "source_type": "ATS",
            "source_detail": "Ashby",
        })
    return out
