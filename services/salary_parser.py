"""Salary detection from free text (product-spec §13). Regex first; never converts.

Deliberately conservative: a match REQUIRES a currency symbol/code adjacent to a
salary-scale amount (thousands separator, a 'k' suffix, or 4+ digits). This
avoids false positives like "16-17 year olds" or "EUR" inside "Europe".
"""
from __future__ import annotations

import re

from models.job_posting import Salary

SYM = {"£": "GBP", "$": "USD", "€": "EUR"}

# currency indicator: a symbol or a standalone code
_CUR = r"(£|\$|€|GBP|USD|EUR)"
# salary-scale amount: 12,000 | 90k | 120000  (NOT bare 16, 17)
_AMT = r"(\d{1,3}(?:,\d{3})+|\d+\s*[kK]|\d{4,})"

RANGE_RX = re.compile(_CUR + r"\s*" + _AMT +
                      r"\s*(?:-|–|—|to)\s*" + _CUR + r"?\s*" + _AMT,
                      re.IGNORECASE)
SINGLE_RX = re.compile(_CUR + r"\s*" + _AMT, re.IGNORECASE)


def _to_int(token: str):
    if not token:
        return None
    t = token.strip().lower().replace(",", "").replace(" ", "")
    mult = 1
    if t.endswith("k"):
        mult, t = 1000, t[:-1]
    try:
        return int(round(float(t) * mult))
    except ValueError:
        return None


def _currency(sym: str | None) -> str | None:
    if not sym:
        return None
    sym = sym.strip().upper()
    if sym in ("GBP", "USD", "EUR"):
        return sym
    return SYM.get(sym)


def _comp_type(text: str, has_number: bool) -> str:
    t = text.lower()
    if re.search(r"\bbonus\b", t):
        return "Base+Bonus"
    if re.search(r"\b(ote|on[- ]target earnings)\b", t):
        return "OTE"
    if re.search(r"\bequity\b", t) and not has_number:
        return "Equity"
    return "Base Only" if has_number else "Not Stated"


# words that mark a money amount as NOT a salary (learning budget, pension, etc.)
NEG_KW = ("budget", "allowance", "learning", "training", "pension", "charity",
          "donation", "loan", "fee", "fine", "revenue", "funding", "raised",
          "valuation", "assets", "deposit")
# words that confirm a money amount IS a salary
SAL_KW = ("salary", "compensation", "base pay", "base salary", "per annum",
          "per year", "/year", "/yr", " pa ", "remuneration", "package", "earn")


def _window(text: str, start: int, end: int) -> str:
    return text[max(0, start - 50):end + 20].lower()


ACCEPT_SCORE = 3


def _accept(win: str, amount: int | None, is_range: bool) -> int:
    """Score a money mention. A nearby NEG_KW penalises (not vetoes) so an explicit
    'Salary:' keyword can still win over a 'pension' mentioned earlier in the window."""
    score = 5 if is_range else 0
    if any(k in win for k in SAL_KW):
        score += 10
    if any(k in win for k in NEG_KW):
        score -= 8
    if amount and amount >= 20000:   # salary-scale annual figure
        score += 3
    return score


def parse(text: str) -> tuple[Salary, str]:
    """Pick the best salary-like money mention by context, not just the first."""
    if not text:
        return Salary(), "Not Stated"

    best = None  # (score, Salary)
    for m in RANGE_RX.finditer(text):
        lo, hi = _to_int(m.group(2)), _to_int(m.group(4))
        if lo and hi and lo > hi:
            lo, hi = hi, lo
        score = _accept(_window(text, m.start(), m.end()), hi or lo, True)
        if score >= ACCEPT_SCORE and (best is None or score > best[0]):
            best = (score, Salary(min=lo, max=hi,
                                  currency=_currency(m.group(1) or m.group(3)),
                                  original_text=m.group(0).strip()))

    for m in SINGLE_RX.finditer(text):
        n = _to_int(m.group(2))
        score = _accept(_window(text, m.start(), m.end()), n, False)
        if score >= ACCEPT_SCORE and (best is None or score > best[0]):
            best = (score, Salary(min=n, max=n, currency=_currency(m.group(1)),
                                  original_text=m.group(0).strip()))

    if best:
        return best[1], _comp_type(text, True)
    return Salary(), _comp_type(text, False)


# An explicit fixed-term statement. Strong enough to override a structured
# "Full time" — ATS fields describe hours, not permanence (NatWest: FULL_TIME on a
# role "offered for a period of twelve months").
_MONTHS = r"(?:\d+|six|nine|twelve|eighteen)[- ]?months?"
_FIXED_TERM_RX = re.compile(
    r"\bfixed[- ]term (?:contract|role|position|appointment)\b|\bftc\b"
    rf"|\boffered for a period of {_MONTHS}\b"
    rf"|\b{_MONTHS},? (?:fixed[- ]term|ftc|contract|secondment|maternity cover)\b"
    r"|\b(?:day|daily) rate\b")
# "contract" alone is too noisy ("details are provided in your contract", "contract
# negotiations over many years"); it needs a stated duration or "fixed" right by it.
_DURATION = r"(?:\d+|six|nine|twelve|eighteen)[- ]?(?:months?|years?)"
_CONTRACT_CTX_RX = re.compile(
    rf"\b{_DURATION}\b[^.\n]{{0,20}}\bcontract\b|\bcontract\b[^.\n]{{0,25}}\b{_DURATION}\b"
    r"|\bfixed\b[^.\n]{0,20}\bcontract\b|\bcontract (?:role|position)\b")


def employment_type(text: str) -> str:
    """Detect employment type from free body text (product-spec §10)."""
    t = (text or "").lower()
    if _FIXED_TERM_RX.search(t) or re.search(r"\b(fixed[- ]term|temporary|interim|freelance)\b", t):
        return "Contract"
    if _CONTRACT_CTX_RX.search(t):
        return "Contract"
    if re.search(r"\bpart[- ]time\b", t):
        return "Part time"
    return "Full time"  # stated, or the default when unstated


def classify_employment(raw_value: str, body: str) -> str:
    """Normalise a structured employment value (Ashby 'FullTime', Workday 'Full time',
    SR 'Contractor', 'Fixed-term'…) and fall back to body heuristics (product-spec §10, #4)."""
    v = (raw_value or "").lower()
    if v:
        if any(k in v for k in ("contract", "fixed", "temporary", "interim",
                                "freelance", "intern", "seasonal")):
            return "Contract"
        if _FIXED_TERM_RX.search((body or "").lower()):
            return "Contract"
        if "part" in v:
            return "Part time"
        if "full" in v or "permanent" in v or "regular" in v:
            return "Full time"
    return employment_type(body)
