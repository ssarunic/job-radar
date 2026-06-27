"""Title normalisation + seniority ranking (README §11). Hardcoded — no API."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# (regex, normalised title, seniority level, rank) — ordered by priority (README §11.3).
# Order matters: first match wins, so seniority descends and Principal precedes Group.
PATTERNS = [
    (r"\b(cpo|chief product officer)\b", "Chief Product Officer", "C Level", 9),
    (r"\b(?:svp|vp|vice president)\b,?\s+(?:of\s+)?product\b", "VP Product", "VP", 8),
    (r"\bdirector of product\b|\bproduct director\b|\bdirector\b,?\s+product management\b",
     "Director of Product", "Director", 7),
    (r"\bhead of product\b|\bhead\b,?\s+product\b", "Head of Product", "Head", 6),
    (r"\b(entrepreneur in residence|eir)\b", "Entrepreneur in Residence", "Head", 6),
    (r"\bprincipal\b.*\bproduct (?:manager|management|owner)\b",
     "Principal Product Manager", "Principal", 5),
    (r"\bgroup\b.*\bproduct manager\b", "Group Product Manager", "Group", 4),
    (r"\bsenior\b.*\bproduct manager\b|\bsr\.?\s+product manager\b",
     "Senior Product Manager", "Senior", 3),
    (r"\bproduct manager\b", "Product Manager", "Mid", 2),
    (r"\bproduct owner\b", "Product Owner", "Other", 2),
]


@dataclass
class Classification:
    normalised: str
    level: str
    rank: int
    kept: bool
    reason: str = ""


def _strip_brackets(t: str) -> str:
    return re.sub(r"[\(\)\[\]\{\}]", " ", t)


def classify(raw_title: str, profile: dict) -> Classification:
    """Return a Classification. `kept` reflects README §11 filter:
    rank >= seniority_min, OR Product Owner when include_product_owner."""
    t = _strip_brackets((raw_title or "").lower())
    t = re.sub(r"\s+", " ", t).strip()

    excl = [e.lower() for e in profile.get("exclude_titles", [])]
    seniority_min = profile.get("seniority_min", 3)
    include_po = profile.get("include_product_owner", True)

    # README §11.5-6 — exclusions (marketing/brand/HR/talent/design-only/etc.).
    # Match at a word boundary so short terms don't hit substrings
    # (e.g. 'hr' must not match inside "Threat"). Start-boundary only, so stems
    # still match ('design' -> 'designer', 'recruit' -> 'recruiter').
    for term in excl:
        if term and re.search(r"\b" + re.escape(term), t):
            # 'design' only excludes when it isn't a clear PM title
            if term == "design" and ("product manager" in t or "product owner" in t):
                continue
            return Classification("", "", 0, False, f"excluded:{term}")

    for rx, norm, level, rank in PATTERNS:
        if re.search(rx, t):
            # Product Owner bumps to rank 3 if senior/lead (README §11.7)
            if norm == "Product Owner":
                if re.search(r"\b(senior|lead)\b", t):
                    rank, level = 3, "Senior"
                kept = include_po or rank >= seniority_min
                return Classification(norm, level, rank, kept,
                                      "" if kept else "product owner excluded")
            kept = rank >= seniority_min
            return Classification(norm, level, rank, kept,
                                  "" if kept else f"rank {rank} < {seniority_min}")

    return Classification("", "", 0, False, "not a product role")
