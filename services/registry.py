"""Company registry — read/write config/companies.csv (follow / unfollow / list)."""
from __future__ import annotations

import csv
from pathlib import Path

from services.loader import CONFIG

CSV = CONFIG / "companies.csv"
FIELDS = ["name", "slug", "careers_url", "ats_type", "ats_slug", "priority", "active"]


def list_companies(path: Path = CSV) -> list[dict]:
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            r = {k: (v or "").strip() for k, v in r.items()}
            r["active"] = r.get("active", "true").lower() in ("true", "1", "yes")
            rows.append(r)
    return rows


def _write(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            out = {k: r.get(k, "") for k in FIELDS}
            out["active"] = "true" if r.get("active") in (True, "true", "True", "1") else "false"
            w.writerow(out)


def add_company(row: dict, path: Path = CSV) -> bool:
    """Append a company; return False if the slug is already tracked."""
    rows = list_companies(path)
    if any(r["slug"] == row["slug"] for r in rows):
        return False
    rows.append(row)
    _write(rows, path)
    return True


def set_active(slug: str, active: bool, path: Path = CSV) -> bool:
    """Toggle a company's active flag; return False if slug not found."""
    rows = list_companies(path)
    found = False
    for r in rows:
        if r["slug"] == slug:
            r["active"] = active
            found = True
    if found:
        _write(rows, path)
    return found
