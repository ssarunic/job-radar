"""Canonical-store layout — the single place that knows *where the data lives*.

Both the CLI and the web API resolve store paths through here, honouring the
JSA_ROOT env override (default: repo root) so either surface can be pointed at a
temp store in tests. Constitution §3: this owns location, not meaning."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def atomic_write_text(path, text: str) -> None:
    """Write text atomically (temp file in the same dir + os.replace), so a
    concurrent reader never observes a half-written file — the canonical store
    and derived index are shared across the web + scraper containers."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix or ".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)   # atomic on the same filesystem
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
