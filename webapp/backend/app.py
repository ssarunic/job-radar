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
from pydantic import BaseModel

_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR.parents[1]))   # repo root -> services.*/outputs.*

from models.job_posting import _slugify        # noqa: E402
from scrapers.http_client import HttpClient     # noqa: E402
from scrapers.rate_limiter import RateLimiter   # noqa: E402
from services import discovery, loader, queries, registry, store   # noqa: E402

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


# --- company management (write surface over services.registry + discovery) ----

def _open_role_counts() -> dict:
    """Open-role count per company_slug, from one load of the derived index."""
    counts: dict = {}
    for r in queries.load_index(store.index_path()):
        if r.get("status") == "open":
            slug = r.get("company_slug")
            counts[slug] = counts.get(slug, 0) + 1
    return counts


def _company_view(c: dict, counts: dict) -> dict:
    return {"name": c.get("name"), "slug": c.get("slug"),
            "ats_type": c.get("ats_type"), "ats_slug": c.get("ats_slug"),
            "careers_url": c.get("careers_url"), "active": bool(c.get("active")),
            "open_roles": counts.get(c.get("slug"), 0)}


@app.get("/api/companies")
def list_companies():
    counts = _open_role_counts()
    companies = [_company_view(c, counts) for c in registry.list_companies()]
    return {"count": len(companies), "companies": companies}


class AddCompany(BaseModel):
    query: Optional[str] = None          # company name or careers URL (auto-detect)
    name: Optional[str] = None           # explicit manual entry (below) — no network
    ats_type: Optional[str] = None
    ats_slug: Optional[str] = None
    careers_url: Optional[str] = None
    priority: Optional[str] = None


@app.post("/api/companies", status_code=201)
def follow_company(body: AddCompany):
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
        settings = loader.load_settings()
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
    counts = _open_role_counts()
    return {"company": _company_view(info, counts)}


class ActivePatch(BaseModel):
    active: bool


@app.patch("/api/companies/{slug}")
def set_company_active(slug: str, body: ActivePatch):
    if not registry.set_active(slug, body.active):
        raise HTTPException(404, f"no company with slug {slug!r}")
    return {"slug": slug, "active": body.active}


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
