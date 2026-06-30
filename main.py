#!/usr/bin/env python3
"""Job Search Assistant — Job Seek mode (SPEC §1, §8).

Usage:
    python main.py seek                 # all active companies
    python main.py seek --only natwest  # one company
    python main.py seek --limit 1       # first N active companies
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import click

from outputs import company_index
from scrapers.http_client import HttpClient
from scrapers.ladder import open_company
from scrapers.rate_limiter import RateLimiter
from scrapers.result import BLOCKED, ERROR
from services import company_enricher, discovery, queries, registry, run_service, store
from services.claude_service import ClaudeService
from services.loader import load_companies, load_dotenv, load_profile, load_settings, merged_profile


@click.group()
def cli():
    load_dotenv()   # pick up local .env (SLACK_WEBHOOK_URL, WEB_BASE_URL, ANTHROPIC_API_KEY)


@cli.command()
@click.option("--only", default=None, help="Process a single company by slug.")
@click.option("--limit", default=None, type=int, help="Process first N active companies.")
@click.option("--notify-empty/--no-notify-empty", default=False,
              help="Send an 'all quiet' heartbeat even when no new roles "
                   "(the daily scheduler passes this).")
def seek(only, limit, notify_empty):
    """Discover open senior PM roles across the configured companies."""
    settings = load_settings()
    companies = run_service.select_companies(
        load_companies(), only=only, limit=limit,
        max_companies=settings.get("max_companies", 300))
    if not companies:
        click.echo("No active companies match. Check config/companies.csv.")
        return
    run_service.seek_run(settings, load_profile(), companies, progress=click.echo,
                         notify_empty=notify_empty)


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


@cli.command("enrich")
@click.option("--only", default=None, help="Enrich a single company by slug.")
@click.option("--limit", default=None, type=int, help="Enrich first N active companies.")
def enrich_cmd(only, limit):
    """Exploratory mode: enrich tracked companies into the Company Index."""
    settings = load_settings()
    base_profile = load_profile()
    companies = [c for c in load_companies() if c["active"]]
    if only:
        companies = [c for c in companies if c["slug"] == only]
    if limit:
        companies = companies[:limit]
    http = HttpClient(settings, RateLimiter(settings.get("rate_limit_per_sec", 1)))
    claude = ClaudeService(settings)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    n = 0
    for company in companies:
        profile = merged_profile(company, base_profile)
        click.echo(f"→ enrich {company['name']} …")
        try:
            with open_company(company, profile, http) as (fetcher, result):
                postings = result.postings if result.status not in (BLOCKED, ERROR) else []
            c = company_enricher.enrich(company, postings, claude, now_iso)
            company_index.write_company(store.companies_dir(), c)
            n += 1
            click.echo(f"   {c.data_confidence:<6} HQ={c.hq_location or '?':<18} "
                       f"{(c.description or '(no description)')[:64]}")
        except Exception as e:  # noqa: BLE001 — keep the batch alive
            click.echo(f"   ✗ error: {e}")

    n_idx = company_index.rebuild_index(store.companies_dir(), store.company_index_path())
    click.echo(f"Enriched {n} companies → {n_idx} rows in data/company_index.jsonl")


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
        click.echo(f"  Run:  {sys.executable} main.py seek --only {info['slug']}")
    else:
        existing = registry.find_existing(info)
        who = existing["name"] if existing else info["slug"]
        click.echo(f"Already tracking {who}.")


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
    rows = queries.load_index(store.index_path())
    res = queries.open_roles(rows, company=company, min_rank=min_rank,
                             status=(None if status == "all" else status))
    if limit:
        res = res[:limit]
    _print_roles(res, header=f"{status} roles" + (f" at {company}" if company else ""))


@cli.command("new")
@click.option("--since", default=None, help="ISO date (YYYY-MM-DD); overrides the auto marker.")
def new_cmd(since):
    """New roles since your last check (or --since DATE)."""
    rows = queries.load_index(store.index_path())
    if since:                           # explicit inclusive window; no state change
        _print_roles(queries.new_roles(rows, since),
                     header=f"New open roles since {since}")
        return
    # auto path: roles not yet surfaced, tracked by id (robust to same-day re-runs).
    seen_path = store.seen_path()
    seen = queries.read_seen(seen_path)
    res = queries.unseen_roles(rows, seen)
    _print_roles(res, header="New open roles since last check")
    if res:
        queries.write_seen(seen_path, seen | {r["id"] for r in res})


if __name__ == "__main__":
    cli()
