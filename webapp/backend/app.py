"""Job Search Assistant — web API (Phase 1, read-only).

FastAPI over the canonical store (Constitution §3): lists from data/jobs.jsonl,
detail from the per-role MD. Reuses services.queries / services.reconciler /
outputs.md_writer. The data root is JSA_ROOT (env) or the repo root, resolved per
request so tests can point at a temp store.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

_BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = _BACKEND_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from outputs import md_writer            # noqa: E402
from services import queries, reconciler  # noqa: E402

app = FastAPI(title="Job Search Assistant", version="1.0")


# --- store paths (resolved per call so JSA_ROOT can change in tests) ---------
def _root() -> Path:
    return Path(os.environ.get("JSA_ROOT", str(REPO_ROOT)))


def _jobs_dir() -> Path:
    return _root() / "jobs"


def _index_path() -> Path:
    return _root() / "data" / "jobs.jsonl"


def _runs_dir() -> Path:
    return _root() / "data" / "runs"


_SUMMARY_FIELDS = (
    "id", "company", "company_slug", "title_raw", "title_normalised",
    "seniority_rank", "seniority_level", "locations", "salary", "status",
    "first_seen", "last_seen", "posted_date", "workplace_model",
    "employment_type", "source_detail", "job_ad_url",
)


def _summary(role: dict) -> dict:
    return {k: role.get(k) for k in _SUMMARY_FIELDS}


def _split_body(body: str) -> tuple[str, str]:
    """Return (ad_markdown, notes_markdown) — the ad is everything before My notes."""
    parts = re.split(r"\n##\s*My notes\s*\n", body or "", maxsplit=1)
    ad = parts[0].strip()
    notes = parts[1].strip() if len(parts) > 1 else ""
    return ad, notes


# --- API ---------------------------------------------------------------------
@app.get("/api/stats")
def stats():
    roles = queries.group_roles(queries.load_index(_index_path()))
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    open_roles = [r for r in roles if r.get("status") == "open"]
    last_run = None
    if _runs_dir().exists():
        names = [p.name for p in _runs_dir().iterdir() if p.is_dir()]
        last_run = max(names) if names else None
    return {
        "open": len(open_roles),
        "new_7d": sum(1 for r in open_roles if (r.get("first_seen") or "") >= cutoff),
        "companies": len({r.get("company_slug") for r in roles if r.get("company_slug")}),
        "total": len(roles),
        "last_run": last_run,
    }


@app.get("/api/jobs")
def list_jobs(status: Optional[str] = "open", company: Optional[str] = None,
              min_rank: Optional[int] = None, q: Optional[str] = None,
              sort: str = "seniority"):
    roles = queries.group_roles(queries.load_index(_index_path()))
    out = []
    for r in roles:
        if status and status != "all" and r.get("status") != status:
            continue
        if company and company.lower() not in (
                (r.get("company") or "").lower(), (r.get("company_slug") or "").lower()):
            continue
        if min_rank and (r.get("seniority_rank") or 0) < min_rank:
            continue
        if q and q.lower() not in f"{r.get('company','')} {r.get('title_raw','')}".lower():
            continue
        out.append(_summary(r))
    if sort == "recent":
        out.sort(key=lambda r: (r.get("first_seen") or ""), reverse=True)
    else:  # seniority
        out.sort(key=lambda r: (-(r.get("seniority_rank") or 0), (r.get("company") or "")))
    return {"count": len(out), "jobs": out}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    rec = reconciler.load_existing(_jobs_dir()).get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="job not found")
    ad, notes = _split_body(rec["body"])
    return {**rec["fm"], "ad_markdown": ad, "notes": notes}


# --- serve built frontend (prod); SPA fallback for client routes -------------
_DIST = _BACKEND_DIR.parent / "frontend" / "dist"


@app.get("/{full_path:path}")
def spa(full_path: str):
    if not _DIST.exists():
        raise HTTPException(status_code=404, detail="frontend not built")
    candidate = _DIST / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(_DIST / "index.html")   # client-side routes -> index.html
