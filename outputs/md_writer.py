"""Canonical Markdown read/write (SPEC §6.3). Preserves user-owned content."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

NOTES_RX = re.compile(r"##\s*My notes\s*\n(.*)\Z", re.DOTALL | re.IGNORECASE)


def parse_md(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_str)."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1]) or {}
            return fm, parts[2].lstrip("\n")
    return {}, text


def extract_notes(body: str) -> str:
    m = NOTES_RX.search(body or "")
    return m.group(1).strip() if m else ""


def render(frontmatter: dict, description: str, requirements: str, notes: str) -> str:
    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    out = [f"---\n{fm}\n---\n"]
    out.append("## Description\n\n" + (description.strip() or "_(not captured)_") + "\n")
    if requirements.strip():
        out.append("## Requirements\n\n" + requirements.strip() + "\n")
    out.append("## My notes\n\n" + (notes.strip() + "\n" if notes.strip() else ""))
    return "\n".join(out)


def write_posting(jobs_dir: Path, company_slug: str, role_slug: str, job_id: str,
                  frontmatter: dict, description: str, requirements: str,
                  notes: str = "", prior_path: Path | None = None) -> Path:
    company_dir = jobs_dir / company_slug
    company_dir.mkdir(parents=True, exist_ok=True)
    path = company_dir / f"{role_slug}--{job_id}.md"
    path.write_text(render(frontmatter, description, requirements, notes),
                    encoding="utf-8")
    # Title rename -> same id, new slug: remove the stale file (#3)
    if prior_path is not None:
        prior_path = Path(prior_path)
        if prior_path != path and prior_path.exists():
            prior_path.unlink()
    return path


def update_frontmatter(path: Path, frontmatter: dict) -> None:
    """Rewrite only the frontmatter, preserving the existing body verbatim."""
    _, body = parse_md(path)
    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")
