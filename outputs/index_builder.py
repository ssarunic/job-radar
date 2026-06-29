"""Regenerate data/jobs.jsonl from all canonical MD frontmatter (SPEC §2)."""
from __future__ import annotations

import json
from pathlib import Path

from outputs import md_writer
from services import store


def rebuild(jobs_dir: Path, index_path: Path) -> int:
    """Regenerate jobs.jsonl. The MD file is the canonical per-role record; the
    index is the DERIVED display view with one row per (role, location) (#3,
    README §12 one-row-per-location)."""
    rows = []
    if jobs_dir.exists():
        for path in sorted(jobs_dir.rglob("*.md")):
            fm, _ = md_writer.parse_md(path)
            if not fm.get("id"):
                continue
            rel = str(path.relative_to(jobs_dir.parent))
            locations = fm.get("locations") or [""]
            for loc in locations:
                row = dict(fm)
                row.pop("locations", None)
                row["location"] = loc          # expanded display row
                row["_path"] = rel
                rows.append(row)
    store.atomic_write_text(
        index_path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return len(rows)
