"""Canonical Markdown read/write (SPEC §6.3). Preserves user-owned content."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from services.store import atomic_write_text

NOTES_RX = re.compile(r"##\s*My notes\s*\n(.*)\Z", re.DOTALL | re.IGNORECASE)
WORDS_RX = re.compile(r"[a-z0-9]+")


def _norm_lines(text: str) -> list[str]:
    """Lines reduced to lowercase words only — spacing (incl. NBSP), markdown
    emphasis, bullets and punctuation all wash out."""
    out = []
    for ln in (text or "").splitlines():
        norm = " ".join(WORDS_RX.findall(ln.lower()))
        if norm:
            out.append(norm)
    return out


def _requirements_redundant(description: str, requirements: str) -> bool:
    """True when the requirements block already appears in the description
    (many ads carry a labelled qualifications section that extraction copies
    rather than cuts). The 0.8 line-overlap threshold tolerates a few edited
    lines; below it the section is kept — the safe failure mode is a visible
    duplicate, never dropped content."""
    req = _norm_lines(requirements)
    if not req:
        return False
    desc = set(_norm_lines(description))
    matched = sum(1 for ln in req if ln in desc)
    return matched / len(req) >= 0.8


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
    return split_body(body)[1]


def split_body(body: str) -> tuple[str, str]:
    """Split a rendered body into (ad_markdown, notes) on the `## My notes`
    boundary. Single owner of that contract (render writes it; readers use this)."""
    m = NOTES_RX.search(body or "")
    if not m:
        return (body or "").strip(), ""
    return (body[:m.start()].strip(), m.group(1).strip())


def render(frontmatter: dict, description: str, requirements: str, notes: str) -> str:
    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    out = [f"---\n{fm}\n---\n"]
    out.append("## Description\n\n" + (description.strip() or "_(not captured)_") + "\n")
    if requirements.strip() and not _requirements_redundant(description, requirements):
        out.append("## Requirements\n\n" + requirements.strip() + "\n")
    out.append("## My notes\n\n" + (notes.strip() + "\n" if notes.strip() else ""))
    return "\n".join(out)


def write_posting(jobs_dir: Path, company_slug: str, role_slug: str, job_id: str,
                  frontmatter: dict, description: str, requirements: str,
                  notes: str = "", prior_path: Path | None = None) -> Path:
    company_dir = jobs_dir / company_slug
    company_dir.mkdir(parents=True, exist_ok=True)
    path = company_dir / f"{role_slug}--{job_id}.md"
    atomic_write_text(path, render(frontmatter, description, requirements, notes))
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
    atomic_write_text(path, f"---\n{fm}\n---\n\n{body}")


def update_user_fields(path: Path, *, status: str | None = None,
                       notes: str | None = None) -> dict:
    """Update the USER-OWNED parts of a posting — the `status` frontmatter field
    and the `## My notes` section — preserving the captured ad text verbatim.
    Pass None to leave a field untouched. Returns the updated frontmatter."""
    fm, body = parse_md(path)
    ad, old_notes = split_body(body)
    if status is not None:
        fm["status"] = status
    new_notes = old_notes if notes is None else notes
    fm_y = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    out = (f"---\n{fm_y}\n---\n\n{ad}\n\n## My notes\n\n"
           + (new_notes.strip() + "\n" if new_notes.strip() else ""))
    atomic_write_text(path, out)
    return fm
