"""Seek-run orchestration, extracted from the CLI.

`seek()` in `main.py` had grown into a god-function owning config, fetching,
pipeline, reconciliation, writing, indexing, summary, and notification. This
module owns that flow and returns a structured `RunResult`, so the web
"Refresh now" / scheduler can invoke it directly instead of shelling out or
duplicating it. Click is now a thin adapter that supplies inputs and a
`progress` callback for live narration.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from outputs import index_builder, md_writer, notify, summary
from scrapers.http_client import HttpClient
from scrapers.ladder import open_company
from scrapers.rate_limiter import RateLimiter
from scrapers.result import BLOCKED, ERROR
from services import pipeline, reconciler, store
from services.claude_service import ClaudeService
from services.loader import merged_profile


def select_companies(companies, only=None, limit=None, max_companies=300):
    """The active-set selection shared by `seek` and `enrich` (CLI adapters)."""
    active = [c for c in companies if c.get("active")]
    if only:
        active = [c for c in active if c["slug"] == only]
    if limit:
        active = active[:limit]
    return active[:max_companies]


@dataclass
class CompanyOutcome:
    name: str
    slug: str
    rung: str
    status: str           # human label: "ok/12 listed" | "blocked: ..." | "error: ..."
    kept: int = 0
    listed: int = 0
    error: str = ""
    ok: bool = False


@dataclass
class RunResult:
    stats: dict
    diff: list
    failed_urls: list
    n_index: int
    run_dir: Path
    summary_text: str
    outcomes: list = field(default_factory=list)   # list[CompanyOutcome]
    notified: bool = False


def _noop(_msg):
    pass


def seek_run(settings, base_profile, companies, *, http=None, claude=None,
             today=None, progress=_noop, notify_empty=False) -> RunResult:
    """Run ladder → pipeline → reconcile → write → index → summary → notify for
    `companies`. `progress(msg)` receives live narration lines (CLI passes
    `click.echo`; web can log or ignore). Returns a `RunResult`."""
    http = http or HttpClient(settings, RateLimiter(settings.get("rate_limit_per_sec", 1)))
    claude = claude or ClaudeService(settings)
    today = today or datetime.now(timezone.utc).date()
    today_iso = today.isoformat()
    started = time.monotonic()
    budget_s = settings.get("runtime_budget_min", 30) * 60

    existing = reconciler.load_existing(store.jobs_dir())
    all_current: list = []
    processed_slugs: set = set()   # companies authoritatively checked this run (#1)
    stats = {"companies": 0, "ok": 0, "blocked": 0, "errors": 0,
             "kept": 0, "per_company": {}}
    failed_urls: list[str] = []
    outcomes: list[CompanyOutcome] = []

    for company in companies:
        if time.monotonic() - started > budget_s:
            progress(f"⏱  Runtime budget reached — stopping before {company['name']}.")
            break
        name = company["name"]
        stats["companies"] += 1
        profile = merged_profile(company, base_profile)
        progress(f"→ {name} ({company.get('ats_type') or 'auto'}) …")
        kept: list = []
        with open_company(company, profile, http) as (fetcher, result):
            rung = result.rung
            if result.status in (BLOCKED, ERROR):
                key = "blocked" if result.status == BLOCKED else "errors"
                stats[key] += 1
                failed_urls.append(company["careers_url"])
                label = f"{result.status}: {result.error}".strip(": ")
                stats["per_company"][name] = {"kept": 0, "rung": rung, "status": label}
                outcomes.append(CompanyOutcome(name, company["slug"], rung, label,
                                               error=result.error or ""))
                icon = "⚠" if result.status == BLOCKED else "✗"
                progress(f"   {icon} {result.status} via {rung}: {result.error}")
                continue
            try:
                kept = (pipeline.process_company(company, profile, result.postings,
                                                 fetcher, settings, claude, today)
                        if result.postings else [])
            except Exception as e:  # noqa: BLE001 — keep the batch alive (product-spec §16)
                stats["errors"] += 1
                failed_urls.append(company["careers_url"])
                stats["per_company"][name] = {"kept": 0, "rung": rung, "status": f"error: {e}"}
                outcomes.append(CompanyOutcome(name, company["slug"], rung, f"error: {e}",
                                               error=str(e)))
                progress(f"   ✗ error: {e}")
                continue

        stats["ok"] += 1
        stats["kept"] += len(kept)
        processed_slugs.add(company["slug"])   # authoritative (ok/empty) -> may age its jobs
        label = f"{result.status}/{len(result.postings)} listed"
        stats["per_company"][name] = {"kept": len(kept), "rung": rung, "status": label}
        outcomes.append(CompanyOutcome(name, company["slug"], rung, label,
                                       kept=len(kept), listed=len(result.postings), ok=True))
        all_current.extend(kept)
        progress(f"   ✓ {len(kept)} kept (from {len(result.postings)} listed) via {rung}")

    # --- Reconcile, write canonical MD, rebuild index, emit diff/summary -----
    # Only age postings for companies we actually checked this run (#1).
    current_actions, missing_actions, diff = reconciler.reconcile(
        existing, all_current, today_iso, processed_slugs)

    for jp, fm, notes, prior_path in current_actions:
        md_writer.write_posting(store.jobs_dir(), jp.company_slug, jp.role_slug, jp.id,
                                fm, jp.description, jp.requirements, notes,
                                prior_path=prior_path)
    for path, fm in missing_actions:
        md_writer.update_frontmatter(path, fm)

    n_index = index_builder.rebuild(store.jobs_dir(), store.index_path())

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    run_dir = store.runs_dir() / ts
    summary.write_diff(run_dir, diff)
    text = summary.build_summary(stats, diff, failed_urls,
                                 time.monotonic() - started,
                                 settings.get("runtime_budget_min", 30))
    text += f"\nIndex: {n_index} postings -> data/jobs.jsonl"
    summary.emit(run_dir, text)

    notified = False
    try:
        notify_summary = {"companies": stats["companies"], "open_total": n_index,
                          "failed": stats["blocked"] + stats["errors"]}
        notified = bool(notify.notify(diff, settings, http,
                                      notify_empty=notify_empty, summary=notify_summary,
                                      label=base_profile.get("search_label",
                                                             notify.DEFAULT_LABEL)))
        if notified:
            progress("📲 notification sent")
    except Exception as e:  # noqa: BLE001 — never let notify failure fail the run
        progress(f"(notification skipped: {e})")

    return RunResult(stats=stats, diff=diff, failed_urls=failed_urls, n_index=n_index,
                     run_dir=run_dir, summary_text=text, outcomes=outcomes, notified=notified)
