"""Job Search Assistant — web API (Phase 1, read-only).

Thin HTTP layer over the shared read API: paths from services.store, all
listing/stats/detail logic from services.queries (same lib the CLI uses, so the
two can't diverge). Constitution §3: this owns only *how it's invoked*.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR.parents[1]))   # repo root -> services.*/outputs.*
sys.path.insert(0, str(_BACKEND_DIR))              # -> mcp_app when imported as a package

import mcp_app  # noqa: E402

from models.job_posting import _slugify  # noqa: E402
from outputs import index_builder, md_writer  # noqa: E402
from scrapers.http_client import HttpClient  # noqa: E402
from scrapers.rate_limiter import RateLimiter  # noqa: E402
from services import discovery, loader, queries, registry, run_service, store  # noqa: E402


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # The MCP session manager must be running for /mcp requests to be served.
    async with mcp_app.mcp.session_manager.run():
        yield


app = FastAPI(title="Job Search Assistant", version="1.0", lifespan=_lifespan)

# MCP server at /mcp (spec: mounted into this app — one server, one deploy). Lifting
# the FastMCP sub-app's routes (rather than app.mount) keeps the exact path `/mcp`
# working — Starlette's Mount only matches `/mcp/…` — and must precede the SPA
# catch-all below so GET /mcp (the SSE stream) isn't swallowed by it.
app.router.routes.extend(mcp_app.mcp.streamable_http_app().routes)


@app.get("/api/stats")
def stats():
    return {**queries.stats(queries.load_index(store.index_path())),
            "last_run": store.last_run()}


@app.get("/api/jobs")
def list_jobs(status: Optional[str] = "open", company: Optional[str] = None,
              min_rank: Optional[int] = None, q: Optional[str] = None,
              sort: str = "seniority"):
    roles = queries.list_roles(queries.load_index(store.index_path()),
                               status=status, company=company, min_rank=min_rank,
                               q=q, sort=sort)
    return {"count": len(roles), "jobs": [queries.role_summary(r) for r in roles]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    role = queries.get_role(job_id)
    if not role:
        raise HTTPException(status_code=404, detail="job not found")
    return role


@app.get("/api/jobs/{job_id}/markdown")
def get_job_markdown(job_id: str, download: bool = False):
    """The canonical role file, byte-for-byte — frontmatter, ad and notes
    (spec: job-markdown-export.md). Made for pasting into an LLM."""
    path = _role_path(job_id)
    if not path:
        raise HTTPException(status_code=404, detail="job not found")
    headers = {}
    if download:   # slug + stem are already slugified, safe in a header
        headers["Content-Disposition"] = \
            f'attachment; filename="{path.parent.name}--{path.name}"'
    return Response(path.read_text(encoding="utf-8"),
                    media_type="text/markdown; charset=utf-8", headers=headers)


class JobUpdate(BaseModel):
    """User-owned fields only. Status may only move between open, applied and
    rejected — suspected_filled/closed belong to the scan lifecycle."""
    status: Optional[str] = None
    notes: Optional[str] = None


def _role_path(job_id: str):
    for row in queries.load_index(store.index_path()):
        if row.get("id") == job_id and row.get("_path"):
            p = store.root() / row["_path"]
            return p if p.exists() else None
    return None


@app.patch("/api/jobs/{job_id}")
def update_job(job_id: str, body: JobUpdate):
    if body.status is None and body.notes is None:
        raise HTTPException(status_code=422, detail="provide status and/or notes")
    if body.status is not None and body.status not in ("applied", "rejected", "open"):
        raise HTTPException(status_code=422,
                            detail="status must be 'applied', 'rejected' or 'open'")
    path = _role_path(job_id)
    if not path:
        raise HTTPException(status_code=404, detail="job not found")
    md_writer.update_user_fields(path, status=body.status, notes=body.notes)
    if body.status is not None:   # status lives in the derived index; notes don't
        index_builder.rebuild(store.jobs_dir(), store.index_path())
    return queries.get_role(job_id)


# --- company management (write surface over services.registry + discovery) ----

def _open_role_counts() -> dict:
    """Open-role count per company_slug. Groups first (the index is one row per
    location; `group_roles` collapses them to one role per id) so the count matches
    the role list — same basis as `queries.stats` / `list_roles`."""
    counts: dict = {}
    for r in queries.group_roles(queries.load_index(store.index_path())):
        if r.get("status") == "open":
            slug = r.get("company_slug")
            counts[slug] = counts.get(slug, 0) + 1
    return counts


def _company_view(c: dict, counts: dict) -> dict:
    return {"name": c.get("name"), "slug": c.get("slug"),
            "ats_type": c.get("ats_type"), "ats_slug": c.get("ats_slug"),
            "careers_url": c.get("careers_url"), "active": bool(c.get("active")),
            "open_roles": counts.get(c.get("slug"), 0)}


class ProfileUpdate(BaseModel):
    """The wizard's editable subset of search_profile.yaml. Everything is
    optional — only provided fields are merged; the rest of the file (packs,
    exclusions, operational knobs) is preserved."""
    search_label: Optional[str] = None
    seniority_min: Optional[int] = None
    allow_remote: Optional[bool] = None
    home_city: Optional[str] = None
    home_terms: Optional[list[str]] = None
    remote_regions: Optional[list[str]] = None
    exclude_titles: Optional[list[str]] = None


@app.get("/api/profile")
def get_profile():
    """The current search profile + whether any company is followed yet —
    the frontend uses (companies_followed == 0) to offer first-run setup."""
    followed = sum(1 for c in registry.list_companies() if c.get("active"))
    return {"profile": loader.load_profile(), "companies_followed": followed}


@app.put("/api/profile")
def update_profile(body: ProfileUpdate):
    """Merge the wizard fields into search_profile.yaml (atomic write). YAML
    comments in the shipped default are not preserved — the file becomes
    machine-written after first save; docs/configuration.md documents fields."""
    if body.seniority_min is not None and not 1 <= body.seniority_min <= 9:
        raise HTTPException(status_code=422, detail="seniority_min must be 1–9")
    for name in ("home_terms", "remote_regions", "exclude_titles"):
        v = getattr(body, name)
        if v is not None and any(not str(t).strip() for t in v):
            raise HTTPException(status_code=422, detail=f"{name} contains empty terms")

    profile = loader.load_profile()
    for key in ("search_label", "seniority_min", "allow_remote", "exclude_titles"):
        v = getattr(body, key)
        if v is not None:
            profile[key] = v
    loc_updates = {k: v for k, v in
                   {"home_city": body.home_city, "home_terms": body.home_terms,
                    "remote_regions": body.remote_regions}.items() if v is not None}
    if loc_updates:
        profile["location"] = {**(profile.get("location") or {}), **loc_updates}

    store.atomic_write_text(store.config_dir() / "search_profile.yaml",
                            yaml.safe_dump(profile, sort_keys=False, allow_unicode=True))
    return {"profile": profile}


@app.get("/api/companies")
def list_companies():
    counts = _open_role_counts()
    companies = [_company_view(c, counts) for c in registry.list_companies()]
    return {"count": len(companies), "companies": companies}


@app.get("/api/companies/{slug}")
def company_detail(slug: str):
    match = next((c for c in registry.list_companies() if c["slug"] == slug), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"no company with slug {slug!r}")
    counts = _open_role_counts()
    roles = queries.list_roles(queries.load_index(store.index_path()),
                               status="open", company=slug, sort="seniority")
    return {"company": _company_view(match, counts),
            "roles": [queries.role_summary(r) for r in roles]}


class AddCompany(BaseModel):
    query: Optional[str] = None          # company name or careers URL (auto-detect)
    name: Optional[str] = None           # explicit manual entry (below) — no network
    ats_type: Optional[str] = None
    ats_slug: Optional[str] = None
    careers_url: Optional[str] = None
    priority: Optional[str] = None
    scan: bool = True                    # immediately seek this company's roles


def _scan_company(slug: str, settings: dict) -> bool:
    """Run a one-off seek for just this company so its roles show up immediately,
    instead of waiting for the daily run. Slack is suppressed (you're in the UI),
    and a scan failure is non-fatal — the follow already succeeded."""
    try:
        rows = [c for c in registry.list_companies() if c["slug"] == slug]
        if not rows:
            return False
        quiet = {**settings, "notify": {**(settings.get("notify") or {}), "enabled": False}}
        run_service.seek_run(quiet, loader.load_profile(), rows)
        return True
    except Exception:                                # noqa: BLE001 — never fail the follow
        return False


@app.post("/api/companies", status_code=201)
def follow_company(body: AddCompany):
    settings = loader.load_settings()
    if body.ats_type and body.careers_url:           # manual entry, no discovery
        name = (body.name or body.careers_url).strip()
        info = {"name": name, "slug": _slugify(body.name or name),
                "careers_url": body.careers_url.strip(), "ats_type": body.ats_type.strip(),
                "ats_slug": (body.ats_slug or "").strip(), "priority": body.priority or "",
                "active": True}
    else:                                            # auto-detect by name/URL
        query = (body.query or "").strip()
        if not query:
            raise HTTPException(422, "provide `query` (name or URL), or `ats_type` + `careers_url`")
        http = HttpClient(settings, RateLimiter(settings.get("rate_limit_per_sec", 1)))
        info = discovery.discover(query, http)
        if not info:
            raise HTTPException(422, f"couldn't auto-detect an ATS for {query!r} — "
                                     "add manually with ats_type + careers_url")
        info["active"] = True
    if not registry.add_company(info):
        existing = registry.find_existing(info)
        who = (existing or {}).get("name") or (existing or {}).get("slug") or info["slug"]
        raise HTTPException(409, f"already tracking {who}")
    scanned = _scan_company(info["slug"], settings) if body.scan else False
    counts = _open_role_counts()                     # reflects roles just scanned in
    return {"company": _company_view(info, counts), "scanned": scanned}


class ActivePatch(BaseModel):
    active: bool


@app.patch("/api/companies/{slug}")
def set_company_active(slug: str, body: ActivePatch):
    if not registry.set_active(slug, body.active):
        raise HTTPException(404, f"no company with slug {slug!r}")
    return {"slug": slug, "active": body.active}


# --- manual "Refresh now" — run a full seek in the background ------------------
# The web container shares the image + volume with the scraper, so it can run the
# same pipeline. In-process lock guards against double-clicks and reports status;
# Slack is suppressed (you're in the UI). A web run and the 08:00 scheduler run could
# in principle overlap — atomic store/index writes keep that safe, just not pretty.

_seek_lock = threading.Lock()
_seek_state: dict = {"running": False, "started_at": None, "finished_at": None,
                     "added": None, "summary": None, "error": None,
                     "total": None, "done": 0, "current": None}


def _seek_progress(msg: str) -> None:
    # seek_run emits "→ {name} ({ats}) …" as it starts each company — count those for
    # per-company progress. Other narration lines (✓/⚠/✗) are ignored.
    if msg.startswith("→ "):                    # "→ "
        _seek_state["current"] = msg[2:].split(" (")[0].strip()
        _seek_state["done"] = (_seek_state.get("done") or 0) + 1


def _run_seek() -> None:
    try:
        settings = loader.load_settings()
        companies = run_service.select_companies(
            loader.load_companies(), max_companies=settings.get("max_companies", 300))
        _seek_state.update(total=len(companies), done=0, current=None)
        quiet = {**settings, "notify": {**(settings.get("notify") or {}), "enabled": False}}
        result = run_service.seek_run(quiet, loader.load_profile(), companies,
                                      progress=_seek_progress)
        added = sum(1 for d in result.diff if d.get("change") in ("added", "reopened"))
        _seek_state.update(added=added, summary=result.summary_text, error=None, current=None)
    except Exception as e:                           # noqa: BLE001 — report, don't crash
        _seek_state.update(error=str(e))
    finally:
        _seek_state.update(running=False,
                           finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))


@app.post("/api/seek", status_code=202)
def start_seek():
    with _seek_lock:
        if _seek_state["running"]:
            raise HTTPException(status_code=409, detail="a refresh is already running")
        _seek_state.update(running=True, error=None, summary=None, added=None,
                           finished_at=None, total=None, done=0, current=None,
                           started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    threading.Thread(target=_run_seek, daemon=True).start()
    return {"started": True}


@app.get("/api/seek")
def seek_status():
    return dict(_seek_state)


# --- run history (Activity) ----------------------------------------------------
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{6}Z$")    # also blocks path traversal via {ts}


def _run_counts(changes: list) -> dict:
    counts: dict = {}
    for c in changes:
        k = c.get("change")
        counts[k] = counts.get(k, 0) + 1
    return counts


def _read_run(ts: str) -> Optional[dict]:
    run_dir = store.runs_dir() / ts
    diff_path = run_dir / "diff.jsonl"
    if not diff_path.exists():
        return None
    changes = [json.loads(ln) for ln in diff_path.read_text().splitlines() if ln.strip()]
    summary_path = run_dir / "summary.txt"
    summary = summary_path.read_text() if summary_path.exists() else ""
    return {"ts": ts, "changes": changes, "summary": summary}


def _run_matches(changes: list, q: str) -> list:
    """Deduped 'Company: Title' snippets whose company+title contains q (max 5)."""
    out, seen = [], set()
    for c in changes:
        blob = f"{c.get('company', '')} {c.get('title', '')}".lower()
        if q in blob:
            snip = f"{c.get('company', '')}: {c.get('title', '')}".strip(": ")
            if snip and snip not in seen:
                seen.add(snip)
                out.append(snip)
    return out[:5]


@app.get("/api/runs")
def list_runs(limit: int = 50, q: Optional[str] = None):
    rd = store.runs_dir()
    if not rd.exists():
        return {"count": 0, "runs": []}
    ql = (q or "").strip().lower()
    names = sorted((p.name for p in rd.iterdir() if p.is_dir() and _TS_RE.match(p.name)),
                   reverse=True)[:limit]
    runs = []
    for ts in names:
        run = _read_run(ts)
        if run is None:
            continue
        row = {"ts": ts, "counts": _run_counts(run["changes"]), "total": len(run["changes"])}
        if ql:                                   # content search: keep only matching runs
            matched = _run_matches(run["changes"], ql)
            if not matched:
                continue
            row["matched"] = matched
        runs.append(row)
    return {"count": len(runs), "runs": runs}


@app.get("/api/runs/{ts}")
def get_run(ts: str):
    if not _TS_RE.match(ts):
        raise HTTPException(status_code=404, detail="no such run")
    run = _read_run(ts)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no run {ts!r}")
    return {**run, "counts": _run_counts(run["changes"])}


# --- serve built frontend (prod); SPA fallback for client routes -------------
_DIST = _BACKEND_DIR.parent / "frontend" / "dist"


@app.get("/{full_path:path}")
def spa(full_path: str):
    if not _DIST.exists():
        raise HTTPException(status_code=404, detail="frontend not built")
    if full_path:
        # Resolve and confine to dist — encoded dot segments (e.g. %2e%2e) decode to
        # ".." and would otherwise escape the static root and serve repo / /data files.
        candidate = (_DIST / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(_DIST.resolve()):
            return FileResponse(candidate)
    return FileResponse(_DIST / "index.html")   # client-side routes -> index.html
