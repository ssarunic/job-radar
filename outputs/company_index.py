"""Canonical company MD (companies/<slug>.md) + derived data/company_index.jsonl.

Mirrors the jobs store: MD is canonical (and note-preserving via md_writer.render),
the JSONL is regenerated from frontmatter."""
from __future__ import annotations

import json
from pathlib import Path

from outputs import md_writer
from services import store


def write_company(companies_dir: Path, company) -> Path:
    companies_dir.mkdir(parents=True, exist_ok=True)
    path = companies_dir / f"{company.slug}.md"
    notes = ""
    if path.exists():
        _, body = md_writer.parse_md(path)
        notes = md_writer.extract_notes(body)
    store.atomic_write_text(
        path, md_writer.render(company.to_frontmatter(), company.description, "", notes))
    return path


def rebuild_index(companies_dir: Path, index_path: Path) -> int:
    rows = []
    if companies_dir.exists():
        for path in sorted(companies_dir.glob("*.md")):
            fm, _ = md_writer.parse_md(path)
            if fm.get("slug"):
                fm["_path"] = str(path.relative_to(companies_dir.parent))
                rows.append(fm)
    store.atomic_write_text(
        index_path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return len(rows)
