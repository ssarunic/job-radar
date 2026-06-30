# Job Radar — web app

Browse current/past roles and drill into a role's full Markdown ad, **and manage the
followed-company list** — follow/unfollow, open a company's detail page (its open
roles + a link out to the careers/ATS page), and scan a newly-followed company on the
spot. The roles list sorts by seniority or recency. See [`../specs/webapp/`](../specs/webapp/)
and [`../specs/company-management.md`](../specs/company-management.md) for the design.

```
webapp/
├── backend/   FastAPI over the canonical store + a registry/discovery write surface
└── frontend/  Vite + React + TS SPA (react-router, TanStack Query, react-markdown)
```

The backend reads the store at `JSA_ROOT` (default: repo root): `data/jobs.jsonl`
for lists, `jobs/<company>/*.md` for detail. It never duplicates or mutates job
data (Constitution §3).

## Run

**Dev** (two processes, hot reload):
```bash
# API  (from repo root; uses the project venv which has fastapi/uvicorn)
.venv/bin/python -m uvicorn app:app --app-dir webapp/backend --reload --port 8765
# UI   (proxies /api -> :8765)
cd webapp/frontend && npm install && npm run dev
```

**Prod / single process** (FastAPI serves the built UI):
```bash
cd webapp/frontend && npm install && npm run build   # -> dist/
.venv/bin/python -m uvicorn app:app --app-dir webapp/backend --port 8765
# open http://127.0.0.1:8765
```

**uv** (standalone backend env): `uv run --project webapp/backend uvicorn app:app --app-dir webapp/backend`.

## Tailscale (Phase 4)
Bind to the tailnet so the phone can open deep links:
`uvicorn app:app --app-dir webapp/backend --host 0.0.0.0 --port 8765`, then reach
it at `http://<your-mac>.<tailnet>.ts.net:8765`. Keep it tailnet-only (no public exposure).

## Tests
```bash
.venv/bin/python -m pytest webapp/backend/tests -q
```

## Endpoints (Phase 1)
`GET /api/stats` · `GET /api/jobs?status=&company=&min_rank=&q=&sort=` ·
`GET /api/jobs/{id}`. Client routes (`/`, `/jobs/:id`) are served by the SPA;
deep links work on reload via the catch-all → `index.html`.
