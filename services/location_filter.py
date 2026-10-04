"""Location acceptance + multi-location expansion (product-spec §12).

The *rules* are hardcoded; the *geography* is profile-driven. Term sets default
to the original UK/London search and can be overridden per-seeker from
`search_profile.yaml`:

    location:
      home_terms: ["berlin", "germany"]     # concrete locations you accept
      home_word_terms: ["de"]               # short codes, word-boundary matched
      home_generic: ["germany", "deutschland"]  # country labels collapsed when a city is present
      home_city: "berlin"                   # anchor kept when >5 locations collapse
      remote_regions: ["germany", "europe", "emea", "eu "]  # remote labels eligible for you
      eligible_context: [...]               # office locations that make a co-listed remote OK
      remote_excluded: ["us only", ...]     # explicit exclusions on remote labels

Omitted keys fall back to the UK defaults below, so the shipped behaviour is
unchanged.
"""
from __future__ import annotations

import re

UK_TERMS = ("london", "united kingdom", "england", "scotland", "wales",
            "edinburgh", "manchester")
US_ONLY = ("us only", "u.s. only", "united states only", "us-based", "usa only")
EUROPE_TERMS = ("uk", "europe", "emea", "eu ", "anywhere",
                # EU/EEA + Switzerland, so a remote pinned to any of them
                # ("Remote - Denmark", "Poland - Remote") stays eligible.
                "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech",
                "denmark", "estonia", "finland", "france", "germany", "greece",
                "hungary", "iceland", "ireland", "italy", "latvia", "lithuania",
                "luxembourg", "malta", "netherlands", "norway", "poland",
                "portugal", "romania", "slovakia", "slovenia", "spain", "sweden",
                "switzerland")
GENERIC_UK = ("united kingdom", "uk", "england", "britain", "great britain")

_DEFAULTS = {
    "home_terms": UK_TERMS,
    "home_word_terms": ("uk",),               # \b-matched (avoid 'uk' in 'Kentucky')
    "home_generic": GENERIC_UK,
    "home_city": "london",
    "remote_regions": ("uk", "europe", "emea", "eu "),
    "eligible_context": EUROPE_TERMS,
    "remote_excluded": US_ONLY,
}


def _terms(profile: dict) -> dict:
    cfg = (profile or {}).get("location") or {}
    out = {}
    for k, dflt in _DEFAULTS.items():
        v = cfg.get(k, dflt)
        if isinstance(dflt, tuple):
            v = tuple(str(t).lower() for t in v)
        else:
            v = str(v).lower()
        out[k] = v
    return out


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


def _is_home(loc: str, t: dict) -> bool:
    l = loc.lower()
    if any(term in l for term in t["home_terms"]):
        return True
    return any(re.search(r"\b" + re.escape(w) + r"\b", l) for w in t["home_word_terms"])


def _is_eligible_region(loc: str, t: dict) -> bool:
    l = loc.lower()
    return any(term in l for term in t["eligible_context"]) and not _is_home(l, t)


def _is_remote(loc: str) -> bool:
    l = loc.lower()
    return "remote" in l or "anywhere" in l


# Words that say *how* a remote role works, not *where* it is. A remote label made
# only of these ("Remote", "Fully remote - Anywhere", "Remote (Global)") is
# region-less; anything left over is a place name ("Austin - Remote").
_REMOTE_FILLER_RX = re.compile(
    r"\b(remote|remotely|anywhere|fully|full|first|friendly|global|globally|"
    r"worldwide|flexible|hybrid|distributed|work|working|from|home|wfh|"
    r"in|the|or|and|only|based|option|optional|eligible|ok|possible)\b")


def _remote_names_place(loc: str) -> bool:
    """True when a remote label also names somewhere, e.g. 'Austin - Remote'."""
    rest = _REMOTE_FILLER_RX.sub(" ", loc.lower())
    return bool(re.search(r"[^\W\d_]", rest))


def _is_concrete_foreign(loc: str, t: dict) -> bool:
    """A real location that isn't home or an eligible region — including a remote
    label pinned to such a place ("Austin - Remote")."""
    if _is_home(loc, t) or _is_eligible_region(loc, t):
        return False
    return not _is_remote(loc) or _remote_names_place(loc)


# Named regions the seeker isn't eligible for (#3). A remote label naming one of
# these (without also naming a home/eligible region) is rejected — e.g.
# "Remote (USA)". Deliberately broad; the home/eligible term sets win when both
# match, so a Berlin-profile "Remote (Germany)" is spared by remote_regions.
_INELIGIBLE_RX = re.compile(
    r"\b(us|usa|u\.s\.?a?\.?|united states|america|americas|canada|apac|latam|"
    r"india|australia|anz|singapore|japan|china|hong kong|brazil|mexico|"
    r"philippines|new zealand|nz|uae|dubai|israel|korea|africa)\b")


def _names_ineligible_region(loc_lower: str) -> bool:
    return bool(_INELIGIBLE_RX.search(loc_lower))


def _remote_explicitly_eligible(loc_lower: str, t: dict) -> bool:
    return _is_home(loc_lower, t) or any(term in loc_lower for term in t["remote_regions"])


def accept(loc: str, profile: dict) -> bool:
    """Single-location acceptance (home, or home-region-eligible remote)."""
    t = _terms(profile)
    if _is_home(loc, t):
        return True
    if _is_remote(loc) and profile.get("allow_remote", True):
        l = loc.lower()
        if any(u in l for u in t["remote_excluded"]):
            return False
        return _remote_explicitly_eligible(l, t)
    return False


def workplace_model(loc: str, description: str = "") -> str:
    blob = f"{loc} {description}".lower()
    if "hybrid" in blob:
        return "Hybrid"
    if "remote" in blob:
        return "Remote"
    return "On site"


def _collapse(labels: list[str], t: dict) -> list[str]:
    """Drop bare country-level home labels when a specific home city is present;
    de-dupe case-insensitively, preserving order."""
    has_city = any(_is_home(l, t) and l.lower().strip() not in t["home_generic"]
                   for l in labels)
    out, seen = [], set()
    for l in labels:
        if has_city and l.lower().strip() in t["home_generic"]:
            continue
        k = l.lower().strip()
        if k not in seen:
            seen.add(k)
            out.append(l)
    return out


def expand(location_str: str, profile: dict) -> list[str]:
    """Return accepted location labels, one per output row (product-spec §12), judging
    remote against the WHOLE posting: a 'Remote' tied to ineligible-only cities is
    rejected. Max 5; if >5 and the home city is present, keep home city + remote only."""
    t = _terms(profile)
    pieces = split_locations(location_str)
    if not pieces:
        return []

    home_or_eligible = any(_is_home(p, t) or _is_eligible_region(p, t) for p in pieces)
    foreign_present = any(_is_concrete_foreign(p, t) for p in pieces)
    allow_remote = profile.get("allow_remote", True)

    accepted = []
    for p in pieces:
        pl = p.lower()
        # remote checked BEFORE home: a remote role is governed by allow_remote even
        # if it names the home region (e.g. "Remote (UK)").
        if _is_remote(p):
            if not allow_remote or any(u in pl for u in t["remote_excluded"]):
                continue
            explicit = _remote_explicitly_eligible(pl, t)
            # A remote that NAMES an ineligible region (e.g. "Remote (USA)") is
            # rejected on its own terms — before posting-wide home/eligible context
            # can rescue it (#3). Only spared if it also names a home/eligible region.
            if _names_ineligible_region(pl) and not explicit:
                continue
            # Same for a remote pinned to any other place that isn't home or an
            # eligible region ("Austin - Remote", "São Paulo - Remote"): the role
            # is remote *within that place*, so no sibling office can rescue it.
            if _remote_names_place(p) and not explicit and not _is_eligible_region(p, t):
                continue
            if explicit or home_or_eligible:
                accepted.append(p)          # remote alongside a home/eligible office
            elif not foreign_present:
                accepted.append(p)          # truly region-less remote
            # else: remote tied to ineligible-only context -> reject
        elif _is_home(p, t):
            accepted.append(p)
        # concrete foreign city -> reject

    accepted = _collapse(accepted, t)
    if len(accepted) > 5:
        if any(t["home_city"] in l.lower() for l in accepted):
            accepted = [l for l in accepted
                        if t["home_city"] in l.lower() or "remote" in l.lower()]
        accepted = accepted[:5]
    return accepted
