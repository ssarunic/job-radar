"""Run-to-run reconciliation + lifecycle (SPEC §8, README §15 lifecycle).

Lifecycle via a `missing_runs` counter in frontmatter:
  missing 1 run  -> stays open
  missing 2 runs -> Suspected Filled
  missing 3+ runs -> Closed
A posting the user marked `status: applied` is never auto-advanced.
"""
from __future__ import annotations

from pathlib import Path

from outputs import md_writer


def load_existing(jobs_dir: Path) -> dict:
    """id -> {fm, body, path} for every MD already on disk."""
    out = {}
    if not jobs_dir.exists():
        return out
    for path in jobs_dir.rglob("*.md"):
        fm, body = md_writer.parse_md(path)
        jid = fm.get("id")
        if jid:
            out[jid] = {"fm": fm, "body": body, "path": path}
    return out


def reconcile(existing: dict, current_postings: list, today: str):
    """Return (current_actions, missing_actions, diff).

    current_actions: list of (job_posting, frontmatter, notes)
    missing_actions: list of (path, frontmatter)
    diff:            list of dict change records
    """
    current_actions, missing_actions, diff = [], [], []
    current_ids = set()

    for jp in current_postings:
        jid = jp.id
        current_ids.add(jid)
        fm = jp.to_frontmatter()
        prior = existing.get(jid)
        if prior:
            old = prior["fm"]
            old_status = old.get("status", "open")
            fm["first_seen"] = old.get("first_seen", today)
            fm["last_seen"] = today
            fm["last_checked"] = today
            fm["missing_runs"] = 0
            if old_status == "applied":
                fm["status"] = "applied"
                change = "updated"
            elif old_status in ("suspected_filled", "closed"):
                fm["status"] = "open"
                change = "reopened"
            else:
                fm["status"] = "open"
                change = "updated"
            notes = md_writer.extract_notes(prior["body"])
        else:
            fm["first_seen"] = fm["last_seen"] = fm["last_checked"] = today
            fm["missing_runs"] = 0
            fm["status"] = "open"
            change = "added"
            notes = ""
        # prior_path lets the writer clean up a renamed file (title change) (#3)
        current_actions.append((jp, fm, notes, prior["path"] if prior else None))
        if change in ("added", "reopened"):
            diff.append(_diff_row(change, fm))

    # Postings on disk not seen this run
    for jid, rec in existing.items():
        if jid in current_ids:
            continue
        fm = dict(rec["fm"])
        status = fm.get("status", "open")
        fm["last_checked"] = today
        mr = int(fm.get("missing_runs", 0)) + 1
        fm["missing_runs"] = mr
        if status == "applied":
            missing_actions.append((rec["path"], fm))
            continue
        new_status = status
        if mr >= 3:
            new_status = "closed"
        elif mr >= 2:
            new_status = "suspected_filled"
        if new_status != status:
            fm["status"] = new_status
            diff.append(_diff_row(new_status, fm))
        missing_actions.append((rec["path"], fm))

    return current_actions, missing_actions, diff


def _diff_row(change: str, fm: dict) -> dict:
    return {
        "change": change,
        "id": fm.get("id"),
        "company": fm.get("company"),
        "title": fm.get("title_raw"),
        "location": ", ".join(fm.get("locations") or []),
        "status": fm.get("status"),
        "url": fm.get("job_ad_url"),
    }
