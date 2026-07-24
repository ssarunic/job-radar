"""Exploratory mode — enrich a company from public data (product-spec §3.1, §9.1).

Pragmatic + honest: with public HTML only and no paid APIs, the reliably-available
signal is the company "About" blurb embedded in its job postings (Greenhouse/Ashby/
Lever ship descriptions) and the HQ inferred from posting locations. Industry /
funding / revenue / employees need either Claude (set use_claude) to parse the
About text or external sources — left blank with DataConfidence=Low otherwise.
"""
from __future__ import annotations

import re
from collections import Counter

from models.company import Company

_ABOUT_RX = re.compile(r"about\s+(us|the company|[A-Z][\w&.\- ]{1,30})", re.IGNORECASE)


def _longest_description(postings) -> str:
    descs = [p.get("description") or "" for p in postings]
    descs = [d for d in descs if d.strip()]
    return max(descs, key=len) if descs else ""


def _about_blurb(text: str, company_name: str) -> str:
    """Best-effort 1-2 sentence company summary from a job description body."""
    if not text:
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # find an "About <company>" heading and take the next substantive line
    for i, ln in enumerate(lines):
        if _ABOUT_RX.search(ln) and len(ln) < 60:
            for nxt in lines[i + 1:i + 4]:
                if len(nxt) > 40:
                    return _two_sentences(nxt)
    # else: first substantive paragraph that mentions the company or a mission verb
    for ln in lines:
        low = ln.lower()
        if len(ln) > 60 and (company_name.split()[0].lower() in low
                             or "we" in low or "mission" in low):
            return _two_sentences(ln)
    return ""


def _two_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:2]).strip()


def _hq_from_locations(postings) -> str:
    """Most common city across postings (an approximation — noted in Notes)."""
    cities = Counter()
    for p in postings:
        loc = (p.get("location") or "").strip()
        if not loc:
            continue
        city = re.split(r"[,;/|]", loc)[0].strip()
        if city and "remote" not in city.lower():
            cities[city] += 1
    return cities.most_common(1)[0][0] if cities else ""


def enrich(company: dict, postings: list, claude, now_iso: str) -> Company:
    c = Company(name=company["name"], slug=company["slug"],
                careers_url=company.get("careers_url", ""),
                ats_type=company.get("ats_type", ""),
                last_updated_utc=now_iso)

    text = _longest_description(postings)
    notes = []

    ai = claude.extract_company(text, c.name) if (claude and text) else None
    if ai:
        c.description = ai.get("description", "") or ""
        c.industry = ai.get("industry", "") or ""
        c.sub_industry = ai.get("sub_industry", "") or ""
        c.hq_location = ai.get("hq_location", "") or ""
        c.total_funding = ai.get("total_funding", "") or ""
        c.employee_count = ai.get("employee_count", "") or ""
        c.year_founded = str(ai.get("year_founded") or "")
        notes.append("AI-enriched from job description")
    else:
        c.description = _about_blurb(text, c.name)

    if not c.hq_location:
        hq = _hq_from_locations(postings)
        if hq:
            c.hq_location = hq
            notes.append("HQ approximated from posting locations")

    # confidence (product-spec §14): description + HQ from real signal -> Medium; AI -> High
    if ai and c.description:
        c.data_confidence = "High"
    elif c.description and c.hq_location:
        c.data_confidence = "Medium"
    else:
        c.data_confidence = "Low"
    if not text:
        notes.append("no job descriptions available from this ATS")
    c.notes = "; ".join(notes)
    return c
