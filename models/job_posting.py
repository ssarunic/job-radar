"""JobPosting dataclass — the unit of work (SPEC §6.1)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit, urlunsplit


def _slugify(text: str, maxlen: int = 60) -> str:
    out = []
    prev_dash = False
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")[:maxlen].strip("-") or "role"


def canonical_url(url: str) -> str:
    """Lowercase host, drop query/fragment, strip trailing slash (SPEC §6.2)."""
    if not url:
        return ""
    p = urlsplit(url.strip())
    host = p.netloc.lower()
    path = p.path.rstrip("/")
    return urlunsplit((p.scheme.lower() or "https", host, path, "", ""))


@dataclass
class Salary:
    min: Optional[int] = None
    max: Optional[int] = None
    currency: Optional[str] = None
    original_text: Optional[str] = None


@dataclass
class JobPosting:
    company: str = ""
    company_slug: str = ""
    title_raw: str = ""
    title_normalised: str = ""
    seniority_level: str = ""
    seniority_rank: int = 0
    employment_type: str = ""          # Full time | Part time | Contract | Unknown
    workplace_model: str = ""          # On site | Hybrid | Remote
    locations: list = field(default_factory=list)  # all accepted locations for this role
    remote_eligible_regions: str = ""
    salary: Salary = field(default_factory=Salary)
    compensation_type: str = "Not Stated"
    description: str = ""
    requirements: str = ""
    posted_date: Optional[str] = None  # ISO date string
    job_ad_url: str = ""
    source_type: str = ""              # CompanySite | ATS | Aggregator
    source_detail: str = ""            # e.g. Greenhouse / Playwright

    @property
    def id(self) -> str:
        """Stable key (SPEC §6.2, #3). URL-backed jobs key on the canonical URL
        ONLY — location-label changes must not mint a new id. Locations expand to
        rows at output time, not into the identity. No-URL jobs fall back to a
        composite (product-spec §15)."""
        base = canonical_url(self.job_ad_url)
        if not base:
            locs = ";".join(sorted(l.lower().strip() for l in self.locations))
            base = "|".join([
                self.company_slug,
                self.title_normalised.lower(),
                (self.description or "")[:120],
                locs,
            ])
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]

    @property
    def role_slug(self) -> str:
        return _slugify(self.title_raw or self.title_normalised)

    def to_frontmatter(self) -> dict:
        """Scraper-managed frontmatter fields (lifecycle/user fields added by reconciler)."""
        return {
            "id": self.id,
            "company": self.company,
            "company_slug": self.company_slug,
            "title_raw": self.title_raw,
            "title_normalised": self.title_normalised,
            "seniority_level": self.seniority_level,
            "seniority_rank": self.seniority_rank,
            "employment_type": self.employment_type,
            "workplace_model": self.workplace_model,
            "locations": list(self.locations),
            "remote_eligible_regions": self.remote_eligible_regions,
            "salary": {
                "min": self.salary.min,
                "max": self.salary.max,
                "currency": self.salary.currency,
                "original_text": self.salary.original_text,
            },
            "compensation_type": self.compensation_type,
            "posted_date": self.posted_date,
            "job_ad_url": self.job_ad_url,
            "source_type": self.source_type,
            "source_detail": self.source_detail,
        }
