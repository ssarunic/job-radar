"""Per-company processing pipeline (SPEC §7, README §9.2/§11-13).

Order is chosen to minimise detail fetches: cheap listing-level filters
(title, seniority, location, recency) and the per-company cap run first; only
the survivors get a detail-page fetch and salary/employment parsing.
"""
from __future__ import annotations

from datetime import date, datetime

from dateutil import parser as date_parser

from models.job_posting import JobPosting, Salary
from services import location_filter, salary_parser
from services.title_normalizer import classify


def normalize_date(val) -> str | None:
    if val in (None, ""):
        return None
    if isinstance(val, (int, float)):
        ts = val / 1000 if val > 1e11 else val
        try:
            return datetime.utcfromtimestamp(ts).date().isoformat()
        except (ValueError, OSError):
            return None
    try:
        return date_parser.parse(str(val), fuzzy=True).date().isoformat()
    except (ValueError, OverflowError, TypeError):
        return None


def _too_old(iso: str | None, recency_days: int, today: date) -> bool:
    if not iso:
        return False  # unknown date — keep (README §10)
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return False
    return (today - d).days > recency_days


def _extract_requirements(description: str) -> str:
    """Light heuristic: pull a requirements-ish section from the body."""
    if not description:
        return ""
    lines = description.splitlines()
    heads = ("requirements", "what you'll need", "what you will need",
             "about you", "you have", "what we're looking for", "skills")
    for i, ln in enumerate(lines):
        if any(h in ln.lower() for h in heads) and len(ln) < 80:
            chunk = [l for l in lines[i + 1:i + 25] if l.strip()]
            if chunk:
                return "\n".join(chunk)
    return ""


def process_company(company: dict, profile: dict, raw_listing: list[dict],
                    fetcher, settings: dict, claude, today: date) -> list[JobPosting]:
    recency_days = profile.get("recency_days", 45)
    max_roles = profile.get("max_roles_per_company", 10)

    # --- Stage A: listing-level filters + location expansion ------------------
    candidates: list[tuple[JobPosting, dict]] = []
    for raw in raw_listing:
        cls = classify(raw.get("title", ""), profile)
        if not cls.kept:
            continue
        posted = normalize_date(raw.get("posted_date"))
        # recency uses freshness (last-updated) when available: a live ATS feed
        # only returns currently-open roles, so an evergreen role that was first
        # published months ago but updated recently should still count.
        freshness = normalize_date(raw.get("freshness_date")) or posted
        if _too_old(freshness, recency_days, today):
            continue
        # One JobPosting per role, holding all accepted locations (#3). Locations
        # expand to rows at output time, not into the identity.
        locs = location_filter.expand(raw.get("location", ""), profile)
        if not locs:
            continue
        jp = JobPosting(
            company=company["name"],
            company_slug=company["slug"],
            title_raw=raw.get("title", ""),
            title_normalised=cls.normalised,
            seniority_level=cls.level,
            seniority_rank=cls.rank,
            locations=locs,
            description=raw.get("description", "") or "",
            posted_date=posted,
            job_ad_url=raw.get("url", ""),
            source_type=raw.get("source_type", ""),
            source_detail=raw.get("source_detail", ""),
        )
        candidates.append((jp, raw))

    # --- Stage B: dedup, rank, per-company cap (before detail fetch) ----------
    by_id: dict[str, tuple[JobPosting, dict]] = {}
    for jp, raw in candidates:
        by_id.setdefault(jp.id, (jp, raw))   # README §15 dedup by id
    # ties: more-senior first, then newer posted date, then alphabetical (README §9.2)
    ranked = sorted(by_id.values(),
                    key=lambda pr: (-pr[0].seniority_rank,
                                    _date_sort_key(pr[0].posted_date),
                                    pr[0].title_raw.lower()))

    # --- Stage C: detail fetch, then detail-derived filters, THEN cap (#2) ----
    # Detail brings the real date/employment/salary, so filtering must happen
    # before trimming to max_roles. Iterate the ranked pool (bounded), keep the
    # first `max_roles` survivors, and stop early to bound detail fetches.
    allowed = set(profile.get("employment", ["Full time", "Part time"]))
    pool = ranked[: max(max_roles * 3, max_roles)]
    kept: list[JobPosting] = []
    for jp, raw in pool:
        body = jp.description
        if fetcher.needs_detail:
            body = fetcher.detail(jp.job_ad_url) or jp.description
            jp.description = body
            if not jp.posted_date:
                jp.posted_date = normalize_date(_find_date(body))

        # final recency, now that detail may have supplied a real date (#2)
        fresh = normalize_date(raw.get("freshness_date")) or jp.posted_date
        if _too_old(fresh, recency_days, today):
            continue

        # employment: normalise structured value + body, enforce allowed set (#4)
        jp.employment_type = salary_parser.classify_employment(
            raw.get("employment_type"), body)
        if jp.employment_type not in allowed:
            continue

        salary_text = raw.get("salary_text") or body
        sal_dict = claude.extract_salary(salary_text) if claude else None
        if sal_dict:
            jp.salary = Salary(min=sal_dict.get("salary_min"),
                               max=sal_dict.get("salary_max"),
                               currency=sal_dict.get("currency"),
                               original_text=sal_dict.get("original_text"))
            jp.compensation_type = sal_dict.get("compensation_type", "Not Stated")
        else:
            jp.salary, jp.compensation_type = salary_parser.parse(salary_text)

        jp.workplace_model = location_filter.workplace_model(" ; ".join(jp.locations), body)
        jp.requirements = _extract_requirements(body)
        jp.description = _clean_body(body)   # full ad text (MD is the canonical record)
        kept.append(jp)
        if len(kept) >= max_roles:          # cap AFTER detail filtering (#2)
            break

    return kept


def _date_sort_key(iso: str | None):
    # newer first -> use negative ordinal; unknown dates sort last
    if not iso:
        return 0
    try:
        return -date.fromisoformat(iso).toordinal()
    except ValueError:
        return 0


def _find_date(body: str) -> str | None:
    import re
    m = re.search(r"(posted|date posted|posted on)[:\s]*([A-Za-z0-9,\s/-]{6,20})",
                  body or "", re.IGNORECASE)
    return m.group(2).strip() if m else None


def _clean_body(body: str, max_chars: int = 40000) -> str:
    """Store the full ad text. The cap is a safety valve against pathological page
    dumps (e.g. a whole rendered HTML body), not normal truncation — real ads are
    well under it."""
    body = (body or "").strip()
    return body if len(body) <= max_chars else body[:max_chars].rstrip() + "\n\n[truncated]"
