"""Company registry — read/write config/companies.csv (follow / unfollow / list)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from models.job_posting import canonical_url
from services import store

FIELDS = ["name", "slug", "careers_url", "ats_type", "ats_slug", "priority", "active"]


def list_companies(path: Path = None) -> list[dict]:
    path = path or store.config_dir() / "companies.csv"
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            r = {k: (v or "").strip() for k, v in r.items()}
            r["active"] = r.get("active", "true").lower() in ("true", "1", "yes")
            rows.append(r)
    return rows


def _render(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")  # unix EOL, clean diffs
    w.writeheader()
    for r in rows:
        out = {k: r.get(k, "") for k in FIELDS}
        out["active"] = "true" if r.get("active") in (True, "true", "True", "1") else "false"
        w.writerow(out)
    return buf.getvalue()


def _write(rows: list[dict], path: Path) -> None:
    # Atomic (temp + os.replace): the web container writes this while the scraper
    # container may be reading it on the shared volume — never expose a half-written CSV.
    store.atomic_write_text(path, _render(rows))


def _same_company(a: dict, b: dict) -> bool:
    """True if two rows are the same company — by slug, by (ats_type, ats_slug),
    or by canonical careers_url (#3: board slug may differ from company slug)."""
    if a["slug"] == b["slug"]:
        return True
    at, asl = (a.get("ats_type") or ""), (a.get("ats_slug") or "")
    if at and asl and at == (b.get("ats_type") or "") and asl == (b.get("ats_slug") or ""):
        return True
    ua, ub = canonical_url(a.get("careers_url", "")), canonical_url(b.get("careers_url", ""))
    return bool(ua) and ua == ub


def find_existing(row: dict, path: Path = None) -> dict | None:
    path = path or store.config_dir() / "companies.csv"
    for r in list_companies(path):
        if _same_company(row, r):
            return r
    return None


def add_company(row: dict, path: Path = None) -> bool:
    """Append a company; return False if it's already tracked (slug / ATS / URL)."""
    path = path or store.config_dir() / "companies.csv"
    if find_existing(row, path) is not None:
        return False
    rows = list_companies(path)
    rows.append(row)
    _write(rows, path)
    return True


def set_active(slug: str, active: bool, path: Path = None) -> bool:
    """Toggle a company's active flag; return False if slug not found."""
    path = path or store.config_dir() / "companies.csv"
    rows = list_companies(path)
    found = False
    for r in rows:
        if r["slug"] == slug:
            r["active"] = active
            found = True
    if found:
        _write(rows, path)
    return found
