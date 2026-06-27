#!/usr/bin/env python3
"""Job Search Assistant — Job Seek mode (SPEC §1, §8).

Usage:
    python main.py seek                 # all active companies
    python main.py seek --only natwest  # one company
    python main.py seek --limit 1       # first N active companies
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone
from pathlib import Path

import click

from outputs import index_builder, md_writer, notify, summary
from scrapers.http_client import HttpClient
from scrapers.ladder import open_company
from scrapers.rate_limiter import RateLimiter
from scrapers.result import BLOCKED, ERROR
from services import discovery, pipeline, queries, reconciler, registry
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
    http = HttpClient(settings, limiter)
    claude = ClaudeService(settings)
    today = datetime.now(timezone.utc).date()
    today_iso = today.isoformat()
    started = time.monotonic()
    budget_s = settings.get("runtime_budget_min", 30) * 60

    existing = reconciler.load_existing(JOBS_DIR)
    all_current: list = []
    processed_slugs: set = set()   # companies authoritatively checked this run (#1)
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
        kept = []
        with open_company(company, profile, http) as (fetcher, result):
            rung = result.rung
            if result.status in (BLOCKED, ERROR):
                key = "blocked" if result.status == BLOCKED else "errors"
                stats[key] += 1
                failed_urls.append(company["careers_url"])
                stats["per_company"][name] = {
                    "kept": 0, "rung": rung,
                    "status": f"{result.status}: {result.error}".strip(": ")}
                icon = "⚠" if result.status == BLOCKED else "✗"
                click.echo(f"   {icon} {result.status} via {rung}: {result.error}")
                continue
            try:
                kept = (pipeline.process_company(company, profile, result.postings,
                                                 fetcher, settings, claude, today)
                        if result.postings else [])
            except Exception as e:  # noqa: BLE001 — keep the batch alive (README §16)
                stats["errors"] += 1
                failed_urls.append(company["careers_url"])
                stats["per_company"][name] = {"kept": 0, "rung": rung, "status": f"error: {e}"}
                click.echo(f"   ✗ error: {e}")
                continue

        stats["ok"] += 1
        stats["kept"] += len(kept)
        processed_slugs.add(company["slug"])   # authoritative (ok/empty) -> may age its jobs
        stats["per_company"][name] = {"kept": len(kept), "rung": rung,
                                      "status": f"{result.status}/{len(result.postings)} listed"}
        all_current.extend(kept)
        click.echo(f"   ✓ {len(kept)} kept (from {len(result.postings)} listed) via {rung}")

    # --- Reconcile, write canonical MD, rebuild index, emit diff/summary -----
    # Only age postings for companies we actually checked this run (#1).
    current_actions, missing_actions, diff = reconciler.reconcile(
        existing, all_current, today_iso, processed_slugs)

    for jp, fm, notes, prior_path in current_actions:
        md_writer.write_posting(JOBS_DIR, jp.company_slug, jp.role_slug, jp.id,
                                fm, jp.description, jp.requirements, notes,
                                prior_path=prior_path)
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

    # Push only when this run surfaced new/reopened roles (no-op unless configured).
    try:
        if notify.notify(diff, settings, http):
            click.echo("📲 notification sent")
    except Exception as e:  # noqa: BLE001 — never let notify failure fail the run
        click.echo(f"(notification skipped: {e})")


def _http():
    settings = load_settings()
    return HttpClient(settings, RateLimiter(settings.get("rate_limit_per_sec", 1)))


def _fmt_salary(sal: dict | None) -> str:
    if not sal or sal.get("min") is None:
        return ""
    cur = sal.get("currency") or ""
    lo, hi = sal.get("min"), sal.get("max")
    rng = f"{lo:,}" if lo == hi else f"{lo:,}–{hi:,}"
    return f" · {cur} {rng}"


def _print_roles(roles: list, header: str) -> None:
    click.echo(f"{header}: {len(roles)}")
    for r in roles:
        locs = ", ".join(r.get("locations") or [])
        click.echo(f"  • {r.get('company','')}: {r.get('title_raw','')} "
                   f"(rank {r.get('seniority_rank','?')}) [{locs}]"
                   f"{_fmt_salary(r.get('salary'))}")
        click.echo(f"      seen {r.get('first_seen','?')} · {r.get('status','?')} · "
                   f"{r.get('job_ad_url','')}")


@cli.command("companies")
def companies_cmd():
    """List the companies you're tracking."""
    rows = registry.list_companies()
    active = sum(1 for c in rows if c["active"])
    click.echo(f"Tracking {active} active / {len(rows)} total:")
    for c in sorted(rows, key=lambda c: (not c["active"], c["name"].lower())):
        flag = "●" if c["active"] else "○"
        click.echo(f"  {flag} {c['name']:<22} {c['ats_type'] or 'auto':<14} (slug {c['slug']})")


@cli.command()
@click.argument("query")
def follow(query):
    """Start tracking a company by name (auto-detects ATS) or careers URL."""
    info = discovery.discover(query, _http())
    if not info:
        click.echo(f"Couldn't auto-detect an ATS for {query!r}. Add it to "
                   f"config/companies.csv manually (ats_type workday/talemetry/custom "
                   f"+ careers_url).")
        return
    info["active"] = True
    if registry.add_company(info):
        click.echo(f"✓ Following {info['name']} via {info['ats_type']} "
                   f"(slug {info['ats_slug'] or info['slug']}).")
        click.echo(f"  Run:  python main.py seek --only {info['slug']}")
    else:
        click.echo(f"Already tracking {info['slug']}.")


@cli.command()
@click.argument("slug")
def unfollow(slug):
    """Stop tracking a company (sets active=false; keeps its data)."""
    if registry.set_active(slug, False):
        click.echo(f"✓ Unfollowed {slug} (active=false).")
    else:
        click.echo(f"No company with slug {slug!r}. See `companies`.")


@cli.command("roles")
@click.option("--company", default=None, help="Filter by company name or slug.")
@click.option("--min-rank", type=int, default=None, help="Minimum seniority rank.")
@click.option("--status", default="open", help="open | suspected_filled | closed | applied | all.")
@click.option("--limit", type=int, default=None)
def roles_cmd(company, min_rank, status, limit):
    """Show tracked roles (open by default)."""
    rows = queries.load_index(DATA_DIR / "jobs.jsonl")
    res = queries.open_roles(rows, company=company, min_rank=min_rank,
                             status=(None if status == "all" else status))
    if limit:
        res = res[:limit]
    _print_roles(res, header=f"{status} roles" + (f" at {company}" if company else ""))


@cli.command("new")
@click.option("--since", default=None, help="ISO date (YYYY-MM-DD); overrides the auto marker.")
def new_cmd(since):
    """New roles since your last check (or --since DATE)."""
    rows = queries.load_index(DATA_DIR / "jobs.jsonl")
    marker_path = DATA_DIR / "last_checked.txt"
    # auto marker: strictly after last check (same-day roles already seen);
    # explicit --since: inclusive window.
    since_eff = since or queries.read_marker(marker_path) or "0000-00-00"
    res = queries.new_roles(rows, since_eff, strict=not since)
    _print_roles(res, header=f"New open roles since {since_eff}")
    if not since:                       # advance the marker only on the auto path
        queries.write_marker(marker_path, date.today().isoformat())
        click.echo(f"  (marker advanced to {date.today().isoformat()})")


if __name__ == "__main__":
    cli()
