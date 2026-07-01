# Web "Refresh now" + Activity (run history)

> **Status:** ✅ implemented (retrospective spec). A global on-demand seek from the
> web app, and a run-history feed. Extends the read-only web app (`webapp/tactical.md`
> Phases 3–4). Content search over runs is specced separately in `activity-search.md`.

## Overview

Two capabilities, both thin layers over the shared pipeline/store:

1. **Refresh now** — a topbar button runs a **full seek in the background** (the web
   container shares the image + volume with the scraper) and streams progress, so you
   can pull fresh roles without waiting for the 08:00 run.
2. **Activity** — a feed of past runs read from `data/runs/*/` (the diffs the pipeline
   already writes), each drillable to its individual changes.

## Endpoints (`webapp/backend/app.py`)

| Method & path | Behaviour | Response |
|---|---|---|
| `POST /api/seek` | Start a full seek on a daemon thread. In-process `threading.Lock` guards against double-clicks (`409` if already running). Slack **suppressed** (settings copied with `notify.enabled=false`). | `202 {started}` · `409` |
| `GET /api/seek` | Poll status: `{running, started_at, finished_at, added, summary, error, total, done, current}`. `done/total/current` come from `seek_run`'s `progress` callback (parses its `→ {company}` start-of-company lines). | `200` |
| `GET /api/runs?limit=&q=` | Newest-first run list, `{ts, counts, total}` per run. `q` filters to runs whose changes match a company/role (see `activity-search.md`). | `200 {count, runs}` |
| `GET /api/runs/{ts}` | One run: `{ts, changes[], summary, counts}`. `{ts}` is **regex-validated** (`\d{4}-…Z`), which also blocks path traversal. | `200` · `404` |

- A web "Refresh" and the 08:00 scheduler run could overlap in principle; atomic
  store/index writes keep that safe (just not pretty) — single-user, low frequency.

## Static serving & the SPA fallback (security)

The catch-all `GET /{full_path:path}` serves the built frontend (`webapp/frontend/dist`)
and falls back to `index.html` for client routes. It **confines every candidate to the
dist root** — `candidate.resolve().is_relative_to(_DIST.resolve())` — so encoded dot
segments (`%2e%2e`) can't escape to serve repo / `/data` files. This closed a P1 path
traversal; regression test `test_spa_blocks_path_traversal`.

## Frontend (`webapp/frontend/src`)

- **`↻ Refresh` button** in the topbar (`App.tsx`): `POST /api/seek`, then polls
  `GET /api/seek` while running; renders a **fixed top loading bar** (fills `done/total`)
  and a "Scanning {company} (k/N)" caption; on completion invalidates the role/company/
  runs queries and shows `+N new` / `up to date`. Derives state from the query (no
  `setState`-in-effect; only a ref-guarded cache-invalidation).
- **`pages/Activity.tsx`** — run feed (per-change count badges) + the search box; each
  run → `pages/RunDetail.tsx` grouping added/reopened/updated/closed, roles linking to
  `/jobs/:id`.

## Tests

`webapp/backend/tests/test_api.py` — manual seek runs + reports (progress `done/total`,
Slack suppressed), `409` conflict, runs list/detail, `404` + bad-ts, SPA traversal,
content search (`?q=`).

## Non-goals

- Cancelling an in-flight seek; cross-process (web↔scheduler) locking; per-run
  highlighting inside the detail page (see `activity-search.md` non-goals).
