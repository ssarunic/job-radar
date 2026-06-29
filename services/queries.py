"""The read API over the canonical store — *what the data means*.

Single home for listing/filtering/ranking/aggregating/detail, consumed by both
the CLI (`main.py`) and the web API (`webapp/backend/app.py`) so they can't
diverge. Paths come from `services.store`; bodies from `outputs.md_writer`.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from outputs import md_writer
from services import store

# index-only / internal keys not part of a role's public summary
_HIDDEN_FIELDS = {"_path", "location", "missing_runs", "last_checked"}


def load_index(index_path) -> list[dict]:
    p = Path(index_path)
    rows = []
    if p.exists():
        with open(p, encoding="utf-8") as f:        # stream; no whole-file copy
            for line in f:
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


def list_roles(rows, status="open", company=None, min_rank=None, q=None,
               sort="seniority") -> list[dict]:
    """Group + filter + sort roles. `status` falsy or "all" disables the status
    filter. The one filter/sort policy shared by CLI and web."""
    out = []
    for r in group_roles(rows):
        if status and status != "all" and r.get("status") != status:
            continue
        if company:
            c = company.lower()
            if c not in ((r.get("company") or "").lower(), (r.get("company_slug") or "").lower()):
                continue
        if min_rank and (r.get("seniority_rank") or 0) < min_rank:
            continue
        if q and q.lower() not in f"{r.get('company','')} {r.get('title_raw','')}".lower():
            continue
        out.append(r)
    if sort == "recent":
        out.sort(key=lambda r: (r.get("first_seen") or ""), reverse=True)
    else:  # seniority
        out.sort(key=lambda r: (-(r.get("seniority_rank") or 0),
                                (r.get("company") or ""), (r.get("title_raw") or "")))
    return out


def open_roles(rows, company=None, min_rank=None, status="open") -> list[dict]:
    """Back-compat wrapper over list_roles (CLI `roles` command)."""
    return list_roles(rows, status=status, company=company, min_rank=min_rank)


def new_roles(rows, since: str, status_in=("open",)) -> list[dict]:
    """Roles first seen on/after `since` (inclusive; explicit `--since` window)."""
    out = [r for r in group_roles(rows)
           if (r.get("first_seen") or "") >= since
           and (not status_in or r.get("status") in status_in)]
    out.sort(key=lambda r: (r.get("first_seen", ""), r.get("company", "")))
    return out


def unseen_roles(rows, seen_ids, status_in=("open",)) -> list[dict]:
    """Roles not yet surfaced by the auto `new` path (keyed on id, date-agnostic)."""
    out = [r for r in group_roles(rows)
           if r.get("id") not in seen_ids
           and (not status_in or r.get("status") in status_in)]
    out.sort(key=lambda r: (r.get("first_seen", ""), r.get("company", "")))
    return out


def role_summary(role: dict) -> dict:
    """Public projection of a role for transport — denylist of internal keys, so
    new frontmatter fields are exposed automatically."""
    return {k: v for k, v in role.items() if k not in _HIDDEN_FIELDS}


def stats(rows, new_within_days=7) -> dict:
    roles = group_roles(rows)
    cutoff = (date.today() - timedelta(days=new_within_days)).isoformat()
    open_list = [r for r in roles if r.get("status") == "open"]
    return {
        "open": len(open_list),
        "new_7d": sum(1 for r in open_list if (r.get("first_seen") or "") >= cutoff),
        "companies": len({r.get("company_slug") for r in roles if r.get("company_slug")}),
        "total": len(roles),
    }


def get_role(job_id: str) -> dict | None:
    """Detail for one role: frontmatter + Markdown ad + notes. Resolves the file
    via the index's `_path` (one parse), not a scan of every MD."""
    for row in load_index(store.index_path()):
        if row.get("id") == job_id and row.get("_path"):
            path = store.root() / row["_path"]
            if not path.exists():
                return None
            fm, body = md_writer.parse_md(path)
            ad, notes = md_writer.split_body(body)
            return {**fm, "ad_markdown": ad, "notes": notes}
    return None


def read_seen(path) -> set:
    p = Path(path)
    if p.exists():
        try:
            return set(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def write_seen(path, ids: set) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(ids)), encoding="utf-8")
