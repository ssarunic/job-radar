"""Canonical-store layout — the single place that knows *where the data lives*.

Both the CLI and the web API resolve store paths through here, honouring the
JSA_ROOT env override (default: repo root) so either surface can be pointed at a
temp store in tests. Constitution §3: this owns location, not meaning."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def root() -> Path:
    return Path(os.environ.get("JSA_ROOT", str(REPO_ROOT)))


def jobs_dir() -> Path:
    return root() / "jobs"


def companies_dir() -> Path:
    return root() / "companies"


def data_dir() -> Path:
    return root() / "data"


def config_dir() -> Path:
    return root() / "config"


def index_path() -> Path:
    return data_dir() / "jobs.jsonl"


def company_index_path() -> Path:
    return data_dir() / "company_index.jsonl"


def runs_dir() -> Path:
    return data_dir() / "runs"


def seen_path() -> Path:
    return data_dir() / "seen_roles.json"


def last_run() -> str | None:
    """Timestamp name of the most recent run dir, or None."""
    rd = runs_dir()
    if not rd.exists():
        return None
    names = [p.name for p in rd.iterdir() if p.is_dir()]
    return max(names) if names else None
