"""Read-side queries over the derived index for the CLI (roles / new-since)."""
from __future__ import annotations

import json
from pathlib import Path


def load_index(index_path: Path) -> list[dict]:
    rows = []
    p = Path(index_path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def group_roles(rows: list[dict]) -> list[dict]:
    """Collapse the expanded one-row-per-location index back to one role per id."""
    by_id: dict[str, dict] = {}
    for r in rows:
        d = by_id.get(r["id"])
        if d is None:
            d = dict(r)
            d["locations"] = []
            by_id[r["id"]] = d
        loc = r.get("location")
        if loc and loc not in d["locations"]:
            d["locations"].append(loc)
    return list(by_id.values())


def open_roles(rows, company=None, min_rank=None, status="open") -> list[dict]:
    out = []
    for r in group_roles(rows):
        if status and r.get("status") != status:
            continue
        if company:
            c = company.lower()
            if c not in (r.get("company", "").lower(), r.get("company_slug", "").lower()):
                continue
        if min_rank and (r.get("seniority_rank") or 0) < min_rank:
            continue
        out.append(r)
    out.sort(key=lambda r: (r.get("company", ""), -(r.get("seniority_rank") or 0),
                            r.get("title_raw", "")))
    return out


def new_roles(rows, since: str, status_in=("open",)) -> list[dict]:
    """Roles first seen on/after `since` (inclusive; ISO dates compare lexically).
    Used by the explicit `--since DATE` window."""
    out = [r for r in group_roles(rows)
           if (r.get("first_seen") or "") >= since
           and (not status_in or r.get("status") in status_in)]
    out.sort(key=lambda r: (r.get("first_seen", ""), r.get("company", "")))
    return out


def unseen_roles(rows, seen_ids, status_in=("open",)) -> list[dict]:
    """Roles not yet surfaced by the auto `new` path (#1). Keyed on role id, so it's
    independent of `first_seen` date granularity — a role discovered later the same
    day still shows on the next call instead of being hidden."""
    out = [r for r in group_roles(rows)
           if r.get("id") not in seen_ids
           and (not status_in or r.get("status") in status_in)]
    out.sort(key=lambda r: (r.get("first_seen", ""), r.get("company", "")))
    return out


def read_seen(path: Path) -> set:
    import json
    p = Path(path)
    if p.exists():
        try:
            return set(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def write_seen(path: Path, ids: set) -> None:
    import json
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(ids)), encoding="utf-8")
