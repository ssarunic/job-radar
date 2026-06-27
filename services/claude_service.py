"""Claude API — fuzzy parsing ONLY, with hard fallback to heuristics (README §21.4, §22).

Disabled by default (settings.use_claude=false) so a run costs nothing. When
enabled, every response is validated; any failure returns None so the caller
falls back to regex/heuristics. Successful extractions are cached in-process.
"""
from __future__ import annotations

import json
import re

_cache: dict[str, dict] = {}


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
        key = str(hash(prompt))
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
        if not data or not isinstance(data.get("description", ""), str):
            return None
        return data

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
        # minimal schema validation
        if data.get("compensation_type") not in (
                "Base Only", "Base+Bonus", "OTE", "Equity", "Not Stated"):
            return None
        return data
