"""Claude API — fuzzy parsing ONLY, with hard fallback to heuristics (README §21.4, §22).

Disabled by default (settings.use_claude=false) so a run costs nothing. When
enabled, every response is validated; any failure returns None so the caller
falls back to regex/heuristics. Successful extractions are cached in-process.
"""
from __future__ import annotations

import hashlib
import json
import re

_cache: dict[str, dict] = {}

_COMPANY_KEYS = ("description", "industry", "sub_industry", "hq_location",
                 "total_funding", "employee_count", "year_founded")
_CURRENCIES = {"GBP", "USD", "EUR", None}
_COMP_TYPES = {"Base Only", "Base+Bonus", "OTE", "Equity", "Not Stated"}


def _as_int(v):
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


class ClaudeService:
    def __init__(self, settings: dict):
        self.enabled = bool(settings.get("use_claude")) and bool(settings.get("anthropic_api_key"))
        self.model = settings.get("anthropic_model", "claude-haiku-4-5-20251001")
        self._client = None
        if self.enabled:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=settings["anthropic_api_key"])
            except Exception:
                self.enabled = False

    def _ask_json(self, prompt: str) -> dict | None:
        if not self.enabled:
            return None
        # stable content hash (Python's salted str hash() is not stable across runs)
        key = hashlib.sha1(f"{self.model}\n{prompt}".encode("utf-8")).hexdigest()
        if key in _cache:
            return _cache[key]
        try:
            msg = self._client.messages.create(
                model=self.model, max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            m = re.search(r"\{.*\}", text, re.DOTALL)
            data = json.loads(m.group(0)) if m else None
            if isinstance(data, dict):
                _cache[key] = data
                return data
        except Exception:
            return None
        return None

    def extract_company(self, text: str, company_name: str) -> dict | None:
        """Summarise a company from job-description text (README §22 enrich prompt).
        Returns {description,industry,sub_industry,hq_location,total_funding,
        employee_count,year_founded} or None."""
        if not self.enabled or not text:
            return None
        prompt = (
            f"From this job-posting text for {company_name}, extract company facts. "
            "Return ONLY JSON with keys description (1-2 sentence summary), industry "
            "(broad), sub_industry (narrow), hq_location ('City, Country'), "
            "total_funding (original string or ''), employee_count (string or ''), "
            "year_founded (YYYY or null). Use '' / null when not stated; do not invent.\n\n"
            + text[:6000])
        data = self._ask_json(prompt)
        if not data or not isinstance(data.get("description"), str) or not data["description"].strip():
            return None
        # project to the known schema (drop hallucinated keys; coerce to str/null)
        out = {k: ("" if data.get(k) is None else str(data.get(k, ""))) for k in _COMPANY_KEYS}
        out["year_founded"] = data.get("year_founded") if isinstance(data.get("year_founded"), int) else None
        return out

    def extract_salary(self, text: str) -> dict | None:
        """Return {min,max,currency,compensation_type,original_text} or None."""
        if not self.enabled or not text:
            return None
        prompt = (
            "Extract salary info from this job text. Return ONLY JSON with keys "
            "salary_min (int|null), salary_max (int|null), currency "
            "(GBP|USD|EUR|null), compensation_type "
            "(Base Only|Base+Bonus|OTE|Equity|Not Stated), original_text (string). "
            "Do not convert currency.\n\n" + text[:4000])
        data = self._ask_json(prompt)
        if not data:
            return None
        # schema validation: enums + numeric/string coercion (reject on bad enum)
        if data.get("compensation_type") not in _COMP_TYPES:
            return None
        if data.get("currency") not in _CURRENCIES:
            return None
        return {
            "salary_min": _as_int(data.get("salary_min")),
            "salary_max": _as_int(data.get("salary_max")),
            "currency": data.get("currency"),
            "compensation_type": data["compensation_type"],
            "original_text": str(data.get("original_text") or ""),
        }
