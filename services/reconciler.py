"""Run-to-run reconciliation + lifecycle (SPEC §8, product-spec §15 lifecycle).

Lifecycle via a `missing_runs` counter in frontmatter:
  missing 1 run  -> stays open
  missing 2 runs -> Suspected Filled
  missing 3+ runs -> Closed
A posting the user marked `status: applied` or `status: rejected` is never
auto-advanced.
"""
from __future__ import annotations

from pathlib import Path

from models.job_posting import canonical_url
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


def reconcile(existing: dict, current_postings: list, today: str,
              processed_slugs=None):
    """Return (current_actions, missing_actions, diff).

    current_actions: list of (job_posting, frontmatter, notes, prior_path)
    missing_actions: list of (path, frontmatter)
    diff:            list of dict change records

    processed_slugs: set of company slugs that were authoritatively checked this
    run. Only postings of those companies are aged when missing (#1) — so a
    partial run (--only/--limit, runtime budget, blocked/error) never ages
    companies it didn't actually look at. None = age all (legacy/tests).
    """
    current_actions, missing_actions, diff = [], [], []
    current_ids = set()

    # #2 migration: index existing by canonical URL so a posting whose id changed
    # (old location-derived id -> new URL-only id) is still recognised by URL.
    by_url = {}
    for jid, rec in existing.items():
        u = canonical_url(rec["fm"].get("job_ad_url", ""))
        if u:
            by_url.setdefault(u, (jid, rec))

    for jp in current_postings:
        jid = jp.id
        current_ids.add(jid)
        fm = jp.to_frontmatter()
        prior = existing.get(jid)
        if prior is None:                       # id miss -> try URL (migration) (#2)
            u = canonical_url(jp.job_ad_url)
            alt = by_url.get(u) if u else None
            if alt and alt[0] != jid:
                current_ids.add(alt[0])         # old record consumed, don't age it
                prior = alt[1]
        if prior:
            old = prior["fm"]
            old_status = old.get("status", "open")
            fm["first_seen"] = old.get("first_seen", today)
            fm["last_seen"] = today
            fm["last_checked"] = today
            fm["missing_runs"] = 0
            if old_status in ("applied", "rejected"):
                fm["status"] = old_status
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
        elif change == "updated" and prior:          # #7: emit meaningful updates
            changed = _changed_fields(prior["fm"], fm)
            if changed:
                diff.append(_diff_row("updated", fm, changed))

    # Postings on disk not seen this run
    for jid, rec in existing.items():
        if jid in current_ids:
            continue
        # #1 only age a posting if its company was authoritatively checked this run
        if processed_slugs is not None and \
                rec["fm"].get("company_slug") not in processed_slugs:
            continue
        fm = dict(rec["fm"])
        status = fm.get("status", "open")
        fm["last_checked"] = today
        mr = int(fm.get("missing_runs", 0)) + 1
        fm["missing_runs"] = mr
        if status in ("applied", "rejected"):
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


# Content fields whose change is worth reporting (not lifecycle bookkeeping) (#7)
_COMPARED = ("title_raw", "title_normalised", "seniority_rank", "locations",
             "employment_type", "workplace_model", "compensation_type",
             "posted_date", "job_ad_url", "source_detail", "salary")


def _changed_fields(old: dict, new: dict) -> dict:
    """Return {field: [old, new]} for meaningful content changes between runs."""
    changes = {}
    for f in _COMPARED:
        o, n = old.get(f), new.get(f)
        if o != n:
            changes[f] = [o, n]
    return changes


def _diff_row(change: str, fm: dict, changes: dict | None = None) -> dict:
    row = {
        "change": change,
        "id": fm.get("id"),
        "company": fm.get("company"),
        "title": fm.get("title_raw"),
        "location": ", ".join(fm.get("locations") or []),
        "status": fm.get("status"),
        "url": fm.get("job_ad_url"),
    }
    if changes:
        row["changes"] = changes
    return row
