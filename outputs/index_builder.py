"""Regenerate data/jobs.jsonl from all canonical MD frontmatter (SPEC §2)."""
from __future__ import annotations

import json
from pathlib import Path

from outputs import md_writer


def rebuild(jobs_dir: Path, index_path: Path) -> int:
    rows = []
    if jobs_dir.exists():
        for path in sorted(jobs_dir.rglob("*.md")):
            fm, _ = md_writer.parse_md(path)
            if fm.get("id"):
                fm["_path"] = str(path.relative_to(jobs_dir.parent))
                rows.append(fm)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)
