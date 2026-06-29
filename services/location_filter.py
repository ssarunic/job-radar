"""Location acceptance + multi-location expansion (README §12). Hardcoded."""
from __future__ import annotations

import re

UK_TERMS = ("london", "united kingdom", "england", "scotland", "wales",
            "edinburgh", "manchester")
US_ONLY = ("us only", "u.s. only", "united states only", "us-based", "usa only")
EUROPE_TERMS = ("uk", "europe", "emea", "eu ", "ireland", "germany", "france",
                "spain", "netherlands", "anywhere")

SPLIT_RX = re.compile(r"\s*(?:;|/|\bor\b|\band\b|\||,)\s*", re.IGNORECASE)


def split_locations(s: str) -> list[str]:
    if not s:
        return []
    parts = [p.strip() for p in SPLIT_RX.split(s) if p.strip()]
    # de-dupe preserving order
    seen, out = set(), []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out or [s.strip()]


GENERIC_UK = ("united kingdom", "uk", "england", "britain", "great britain")


def _is_uk(loc: str) -> bool:
    l = loc.lower()
    if any(t in l for t in UK_TERMS):
        return True
    return bool(re.search(r"\buk\b", l))


def _is_europe(loc: str) -> bool:
    l = loc.lower()
    return any(t in l for t in EUROPE_TERMS) and not _is_uk(l)


def _is_remote(loc: str) -> bool:
    l = loc.lower()
    return "remote" in l or "anywhere" in l


def _is_concrete_foreign(loc: str) -> bool:
    """A real (non-remote) location that isn't UK or Europe — e.g. San Francisco."""
    return not _is_remote(loc) and not _is_uk(loc) and not _is_europe(loc)


# Named regions a UK seeker isn't eligible for (#3). A remote label naming one of
# these (without also naming UK/Europe/EMEA) is rejected — e.g. "Remote (USA)".
_INELIGIBLE_RX = re.compile(
    r"\b(us|usa|u\.s\.?a?\.?|united states|america|americas|canada|apac|latam|"
    r"india|australia|anz|singapore|japan|china|hong kong|brazil|mexico|"
    r"philippines|new zealand|nz|uae|dubai|israel|korea|africa)\b")


def _names_ineligible_region(loc_lower: str) -> bool:
    return bool(_INELIGIBLE_RX.search(loc_lower))


def accept(loc: str, profile: dict) -> bool:
    """Single-location acceptance (UK, or UK/EU-eligible remote)."""
    if _is_uk(loc):
        return True
    if _is_remote(loc) and profile.get("allow_remote", True):
        l = loc.lower()
        if any(u in l for u in US_ONLY):
            return False
        return _is_uk(l) or any(t in l for t in ("uk", "europe", "emea", "eu "))
    return False


def workplace_model(loc: str, description: str = "") -> str:
    blob = f"{loc} {description}".lower()
    if "hybrid" in blob:
        return "Hybrid"
    if "remote" in blob:
        return "Remote"
    return "On site"


def _collapse(labels: list[str]) -> list[str]:
    """Drop bare country-level UK labels when a specific UK city is present;
    de-dupe case-insensitively, preserving order."""
    has_city = any(_is_uk(l) and l.lower().strip() not in GENERIC_UK for l in labels)
    out, seen = [], set()
    for l in labels:
        if has_city and l.lower().strip() in GENERIC_UK:
            continue
        k = l.lower().strip()
        if k not in seen:
            seen.add(k)
            out.append(l)
    return out


def expand(location_str: str, profile: dict) -> list[str]:
    """Return accepted location labels, one per output row (README §12), judging
    remote against the WHOLE posting: a 'Remote' tied to US-only cities is US-remote
    and rejected. Max 5; if >5 and London present, keep London + remote only."""
    pieces = split_locations(location_str)
    if not pieces:
        return []

    uk_or_eu = any(_is_uk(p) or _is_europe(p) for p in pieces)
    foreign_present = any(_is_concrete_foreign(p) for p in pieces)
    allow_remote = profile.get("allow_remote", True)

    accepted = []
    for p in pieces:
        pl = p.lower()
        # remote checked BEFORE uk: a remote role is governed by allow_remote even
        # if it names the UK (e.g. "Remote (UK)").
        if _is_remote(p):
            if not allow_remote or any(u in pl for u in US_ONLY):
                continue
            explicit = _is_uk(pl) or any(t in pl for t in ("uk", "europe", "emea", "eu "))
            # A remote that NAMES an ineligible region (e.g. "Remote (USA)") is
            # rejected on its own terms — before posting-wide UK/EU context can
            # rescue it (#3). Only spared if it also names UK/EU explicitly.
            if _names_ineligible_region(pl) and not explicit:
                continue
            if explicit or uk_or_eu:
                accepted.append(p)          # remote alongside a UK/EU office
            elif not foreign_present:
                accepted.append(p)          # truly region-less remote
            # else: remote tied to US/foreign-only context -> reject
        elif _is_uk(p):
            accepted.append(p)
        # concrete foreign city -> reject

    accepted = _collapse(accepted)
    if len(accepted) > 5:
        if any("london" in l.lower() for l in accepted):
            accepted = [l for l in accepted
                        if "london" in l.lower() or "remote" in l.lower()]
        accepted = accepted[:5]
    return accepted
