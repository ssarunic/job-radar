"""Title normalisation + seniority ranking (product-spec §11). Hardcoded — no API.

The bundled patterns are the **product-management pack** (plus the AI/Innovation
family). Other disciplines can replace them from `search_profile.yaml` without
touching code:

    custom_patterns:                # replaces the PM pack entirely when present
      - pattern: "\\bhead of design\\b"
        normalised: "Head of Design"
        level: "Head"
        rank: 6
      - pattern: "\\bsenior product designer\\b"
        normalised: "Senior Product Designer"
        level: "Senior"
        rank: 3

Order matters (first match wins — most senior first). With custom patterns
active, the PM-specific extras (Product Owner rank-bump, AI/Innovation family,
`include_product_owner`) don't apply; `exclude_titles` and `seniority_min`
still do.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Qualifier bridge: up to 4 words between the seniority word and "product", for
# titles that name the area first ("Head of International Platforms Product",
# "VP Digital Commerce Product"). Deliberately excludes commas, so bridging can't
# cross a segment boundary — "Head of Engineering, Product Platform" stays a
# non-PM role, while "Head of Product Marketing" is still caught by exclude_titles.
_QUAL = r"(?:[\w&/'’-]+\s+){0,4}"

# Corporate-grade titles (product-spec §11): banks and large enterprises name the
# function and the internal grade as two segments, in either order — "Product
# Manager - Director", "Product Owner, Vice President", "Director - Product
# Manager". The grade carries the seniority, so these rank on it; without this
# they fall through to bare "Product Manager" (rank 2) and are dropped below
# seniority_min. Brackets are blanked before matching, so a bare space is also a
# valid separator ("Product Manager (Director)", "Product Management Director").
# AVP / Assistant Vice President is deliberately absent: it has no rung on the
# product-spec ladder, so those titles keep their function-based rank.
_GRADE_SEP = r"(?:\s*[-–—,|:]\s*|\s+)"
_PM_ROLE = r"product (?:manager|management|owner|lead|leader)"
_VP_GRADE = r"(?:senior |executive )?vice president|svp|evp|vp"
_DIR_GRADE = r"(?:managing |executive )?director"


def _graded(grade: str) -> str:
    """`<pm role><sep><grade>` or `<grade><sep><pm role>`. The two must be
    adjacent, so a grade attached to another function doesn't leak across
    ("Director of Engineering, Product Manager" is not a Director product role)."""
    return (rf"\b{_PM_ROLE}\b{_GRADE_SEP}(?:{grade})\b"
            rf"|\b(?:{grade}){_GRADE_SEP}{_PM_ROLE}\b")


# (regex, normalised title, seniority level, rank) — ordered by priority (product-spec §11.3).
# Order matters: first match wins, so seniority descends and Principal precedes Group.
PATTERNS = [
    (r"\b(cpo|chief product officer)\b", "Chief Product Officer", "C Level", 9),
    (rf"\b(?:svp|vp|vice president)\b,?\s+(?:of\s+)?{_QUAL}product\b"
     r"|\b(?:svp|vp|vice president)\b.*\bproduct (?:lead|leader)\b"
     r"|\bproduct (?:lead|leader)\b.*\b(?:svp|vp|vice president)\b"
     rf"|{_graded(_VP_GRADE)}", "VP Product", "VP", 8),
    (rf"\bdirector of {_QUAL}product\b|\bproduct director\b"
     rf"|\bdirector\b,?\s+{_QUAL}product management\b"
     r"|\bdirector\b.*\bproduct (?:lead|leader)\b|\bproduct (?:lead|leader)\b.*\bdirector\b"
     rf"|{_graded(_DIR_GRADE)}",
     "Director of Product", "Director", 7),
    (rf"\bhead of {_QUAL}product\b|\bhead\b,?\s+{_QUAL}product\b",
     "Head of Product", "Head", 6),
    (r"\b(entrepreneur in residence|eir)\b", "Entrepreneur in Residence", "Head", 6),
    (r"\bprincipal\b.*\bproduct (?:manager|management|owner|lead|leader)\b",
     "Principal Product Manager", "Principal", 5),
    (r"\bstaff\b.*\bproduct (?:manager|lead|leader)\b", "Staff Product Manager", "Staff", 5),
    (r"\bgroup\b.*\bproduct manager\b", "Group Product Manager", "Group", 4),
    # "Product Lead(er)" — a senior area owner. Bare form ranks Group-tier (4); VP/
    # Director-prefixed forms are caught above even when the seniority word isn't
    # adjacent to "product" (e.g. "…Product Lead… Vice President").
    (r"\bproduct (?:lead|leader)\b", "Product Lead", "Lead", 4),
    (r"\bsenior\b.*\bproduct manager\b|\bsr\.?\s+product manager\b",
     "Senior Product Manager", "Senior", 3),
    (r"\bproduct manager\b", "Product Manager", "Mid", 2),
    (r"\bproduct owner\b", "Product Owner", "Other", 2),
]

# product-spec §11.9 — AI / Innovation leadership family (toggle: include_ai_innovation).
# Domain = AI / Artificial Intelligence / GenAI / Innovation, incl. conjoined forms
# ("AI & Innovation"); only conjunctions may join domain words, so "AI Engineer Lead"
# can't bridge. Leadership role-words only (no manager tier — an "Innovation Manager"
# falls through), and IC-track qualifiers after the domain ("Head of AI Research",
# "VP AI Engineering") are rejected by the lookahead. PM patterns match first, so
# "VP Product & AI" stays "VP Product".
_AI_DOM = r"(?:ai|artificial intelligence|gen\s?ai|innovation)"
_AI_LIST = rf"{_AI_DOM}(?:\s*(?:&|/|,|\band\b)\s*{_AI_DOM})*"
_AI_NOT_IC = r"(?!\s+(?:research|engineer|scien|architect|develop|academ)\w*)"
AI_PATTERNS = [
    (rf"\bchief {_AI_LIST} officer\b", "Chief AI Officer", "C Level", 9),
    (rf"\b(?:svp|vp|vice president)\b,?\s+(?:of\s+)?{_AI_LIST}\b{_AI_NOT_IC}",
     "VP AI/Innovation", "VP", 8),
    (rf"\bdirector of {_AI_LIST}\b{_AI_NOT_IC}|\b{_AI_LIST} director\b",
     "Director of AI/Innovation", "Director", 7),
    (rf"\bhead of {_AI_LIST}\b{_AI_NOT_IC}|\bhead\b,?\s+{_AI_LIST}\b{_AI_NOT_IC}",
     "Head of AI/Innovation", "Head", 6),
    (rf"\b{_AI_LIST} lead(?:er)?\b", "AI/Innovation Lead", "Lead", 4),
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


# Two distinct titles in one string ("X / Y", "X & Y", "X and Y").
_SEG_RX = re.compile(r"\s*(?:/|\||&|\band\b|\bor\b)\s*", re.IGNORECASE)


def _distinct_pm_segment(raw_title: str, excl: list, patterns: list) -> Optional[str]:
    """product-spec §11 exception: a marketing/brand title is kept if a *distinct*
    segment is itself a PM title. Returns that segment (normalised) — e.g. the
    'senior product manager' half of 'Product Marketing Manager / Senior Product
    Manager' — or None. The segment must contain none of the excluded terms."""
    for seg in _SEG_RX.split((raw_title or "").lower()):
        seg = re.sub(r"\s+", " ", _strip_brackets(seg)).strip()
        if not seg or any(e and re.search(r"\b" + re.escape(e), seg) for e in excl):
            continue
        if any(re.search(rx, seg) for rx, *_ in patterns):
            return seg
    return None


def _profile_patterns(profile: dict) -> tuple[list, bool]:
    """(patterns, is_product_pack). A non-empty `custom_patterns` list in the
    profile replaces the bundled PM pack; PM-specific extras only apply to the
    bundled pack."""
    custom = profile.get("custom_patterns") or []
    if custom:
        return ([(c["pattern"], c["normalised"], c.get("level", "Other"),
                  int(c["rank"])) for c in custom], False)
    return (PATTERNS + (AI_PATTERNS if profile.get("include_ai_innovation", True) else []),
            True)


def classify(raw_title: str, profile: dict) -> Classification:
    """Return a Classification. `kept` reflects product-spec §11 filter:
    rank >= seniority_min, OR Product Owner when include_product_owner."""
    t = _strip_brackets((raw_title or "").lower())
    t = re.sub(r"\s+", " ", t).strip()

    excl = [e.lower() for e in profile.get("exclude_titles", [])]
    seniority_min = profile.get("seniority_min", 3)
    include_po = profile.get("include_product_owner", True)
    patterns, is_product_pack = _profile_patterns(profile)

    # product-spec §11.5-6 — exclusions (marketing/brand/HR/talent/design-only/etc.).
    # Match at a word boundary so short terms don't hit substrings
    # (e.g. 'hr' must not match inside "Threat"). Start-boundary only, so stems
    # still match ('design' -> 'designer', 'recruit' -> 'recruiter').
    excluded_term = None
    for term in excl:
        if term and re.search(r"\b" + re.escape(term), t):
            # 'design' only excludes when it isn't a clear PM title
            if term == "design" and ("product manager" in t or "product owner" in t):
                continue
            excluded_term = term
            break
    if excluded_term:
        seg = _distinct_pm_segment(raw_title, excl, patterns)
        if seg:
            t = seg          # product-spec §11: a distinct PM title rescues a marketing/brand role
        else:
            return Classification("", "", 0, False, f"excluded:{excluded_term}")

    for rx, norm, level, rank in patterns:
        if re.search(rx, t):
            # Product Owner bumps to rank 3 if senior/lead (product-spec §11.7)
            if is_product_pack and norm == "Product Owner":
                if re.search(r"\b(senior|lead)\b", t):
                    rank, level = 3, "Senior"
                kept = include_po or rank >= seniority_min
                return Classification(norm, level, rank, kept,
                                      "" if kept else "product owner excluded")
            kept = rank >= seniority_min
            return Classification(norm, level, rank, kept,
                                  "" if kept else f"rank {rank} < {seniority_min}")

    return Classification("", "", 0, False, "not a product role")
