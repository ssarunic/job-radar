#!/usr/bin/env python3
"""Job Search Assistant — Job Seek mode (SPEC §1, §8).

Usage:
    python main.py seek                 # all active companies
    python main.py seek --only natwest  # one company
    python main.py seek --limit 1       # first N active companies
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import click

from outputs import index_builder, md_writer, summary
from scrapers.ladder import make_fetcher
from scrapers.rate_limiter import RateLimiter
from services import pipeline, reconciler
from services.claude_service import ClaudeService
from services.loader import (load_companies, load_profile, load_settings,
                             merged_profile)

ROOT = Path(__file__).resolve().parent
JOBS_DIR = ROOT / "jobs"
DATA_DIR = ROOT / "data"


@click.group()
def cli():
    pass


@cli.command()
@click.option("--only", default=None, help="Process a single company by slug.")
@click.option("--limit", default=None, type=int, help="Process first N active companies.")
def seek(only, limit):
    """Discover open senior PM roles across the configured companies."""
    settings = load_settings()
    base_profile = load_profile()
    companies = [c for c in load_companies() if c["active"]]
    if only:
        companies = [c for c in companies if c["slug"] == only]
    if limit:
        companies = companies[:limit]
    companies = companies[: settings.get("max_companies", 300)]

    if not companies:
        click.echo("No active companies match. Check config/companies.csv.")
        return

    limiter = RateLimiter(settings.get("rate_limit_per_sec", 1))
    claude = ClaudeService(settings)
    today = datetime.now(timezone.utc).date()
    today_iso = today.isoformat()
    started = time.monotonic()
    budget_s = settings.get("runtime_budget_min", 30) * 60

    existing = reconciler.load_existing(JOBS_DIR)
    all_current: list = []
    stats = {"companies": 0, "ok": 0, "blocked": 0, "errors": 0,
             "kept": 0, "per_company": {}}
    failed_urls: list[str] = []

    for company in companies:
        if time.monotonic() - started > budget_s:
            click.echo(f"⏱  Runtime budget reached — stopping before {company['name']}.")
            break
        name = company["name"]
        stats["companies"] += 1
        profile = merged_profile(company, base_profile)
        click.echo(f"→ {name} ({company.get('ats_type') or 'auto'}) …")
        try:
            with make_fetcher(company, profile, settings, limiter) as fetcher:
                raw, status, rung = fetcher.listing()
                if status == "blocked":
                    stats["blocked"] += 1
                    failed_urls.append(company["careers_url"])
                    stats["per_company"][name] = {"kept": 0, "rung": rung, "status": "blocked"}
                    click.echo(f"   ⚠ blocked (bot challenge) via {rung}")
                    continue
                kept = pipeline.process_company(
                    company, profile, raw, fetcher, settings, claude, today)
        except Exception as e:  # noqa: BLE001 — keep the batch alive (README §16)
            stats["errors"] += 1
            failed_urls.append(company["careers_url"])
            stats["per_company"][name] = {"kept": 0, "rung": "-", "status": f"error: {e}"}
            click.echo(f"   ✗ error: {e}")
            continue

        stats["ok"] += 1
        stats["kept"] += len(kept)
        stats["per_company"][name] = {"kept": len(kept), "rung": rung,
                                      "status": f"{status}/{len(raw)} listed"}
        all_current.extend(kept)
        click.echo(f"   ✓ {len(kept)} kept (from {len(raw)} listed) via {rung}")

    # --- Reconcile, write canonical MD, rebuild index, emit diff/summary -----
    current_actions, missing_actions, diff = reconciler.reconcile(
        existing, all_current, today_iso)

    for jp, fm, notes in current_actions:
        md_writer.write_posting(JOBS_DIR, jp.company_slug, jp.role_slug, jp.id,
                                fm, jp.description, jp.requirements, notes)
    for path, fm in missing_actions:
        md_writer.update_frontmatter(path, fm)

    n_index = index_builder.rebuild(JOBS_DIR, DATA_DIR / "jobs.jsonl")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    run_dir = DATA_DIR / "runs" / ts
    summary.write_diff(run_dir, diff)
    text = summary.build_summary(stats, diff, failed_urls,
                                 time.monotonic() - started,
                                 settings.get("runtime_budget_min", 30))
    text += f"\nIndex: {n_index} postings -> data/jobs.jsonl"
    summary.emit(run_dir, text)


if __name__ == "__main__":
    cli()
