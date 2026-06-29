"""Job Search Assistant — web API (Phase 1, read-only).

Thin HTTP layer over the shared read API: paths from services.store, all
listing/stats/detail logic from services.queries (same lib the CLI uses, so the
two can't diverge). Constitution §3: this owns only *how it's invoked*.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR.parents[1]))   # repo root -> services.*/outputs.*

from services import queries, store   # noqa: E402

app = FastAPI(title="Job Search Assistant", version="1.0")


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
