"""Config loading + per-company profile merge (SPEC §3)."""
from __future__ import annotations

import csv
import os

import yaml

from services import store

# Paths resolved per call (not frozen at import) so JSA_ROOT works in test/web/embedded.


def load_settings() -> dict:
    with open(store.config_dir() / "settings.yaml") as f:
        s = yaml.safe_load(f) or {}
    if not s.get("anthropic_api_key"):
        s["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
    return s


def load_profile() -> dict:
    with open(store.config_dir() / "search_profile.yaml") as f:
        return yaml.safe_load(f) or {}


def load_companies() -> list[dict]:
    rows = []
    with open(store.config_dir() / "companies.csv", newline="") as f:
        for row in csv.DictReader(f):
            row = {k: (v or "").strip() for k, v in row.items()}
            row["active"] = row.get("active", "true").lower() in ("true", "1", "yes")
            rows.append(row)
    return rows


def merged_profile(company: dict, base_profile: dict) -> dict:
    """Overlay config/overrides/<slug>.yaml onto the global profile (SPEC §3.3)."""
    prof = dict(base_profile)
    ov_path = store.config_dir() / "overrides" / f"{company['slug']}.yaml"
    if ov_path.exists():
        with open(ov_path) as f:
            ov = yaml.safe_load(f) or {}
        # locations_add extends rather than replaces
        add = ov.pop("locations_add", None)
        if add:
            prof["locations"] = list(prof.get("locations", [])) + list(add)
        prof.update(ov)
    return prof
