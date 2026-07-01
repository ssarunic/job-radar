# Activity search (content search over run history)

**Status**: ✅ Complete
**Created**: 2026-07-01
**Updated**: 2026-07-01
**Priority**: Low (small UX gain; completes the "search-first list pages" theme)

## Overview

The **Activity** page lists scraper runs (a timestamp + change-count badges per run).
There's no way to answer "which run touched *Monzo* / *Product Director*?" without
opening runs one by one. This adds a **content search**: a search box that filters the
run list to runs whose changes match a company or role title, mirroring the Roles
page's `?q=` search.

The run data needed for search is **already loaded server-side** — `list_runs` reads
each run's `diff.jsonl` (via `_read_run`) to compute counts, but only returns the
counts. We extend `GET /api/runs` with an optional `q`: when set, filter to matching
runs and return a small `matched` list of "Company: Title" snippets so the list can
show *why* each run matched. No new endpoint, no extra I/O.

## Goals

1. A search box on the Activity page that filters the run list by company/role title.
2. Server-side filtering on the existing `GET /api/runs` via `?q=` (mirrors `/api/jobs?q=`).
3. Each surviving run shows a few matched-change snippets so the match is legible.

## Non-goals

- Highlighting matched changes **inside** the run-detail page (`RunDetail`) — possible
  follow-up, not needed for v1.
- Change-type or date filtering (considered and rejected — see Alternatives).
- A dedicated search index / new endpoint.

## Background findings

- [`webapp/backend/app.py:238`](../webapp/backend/app.py#L238) `list_runs(limit)` — lists
  run dirs newest-first and returns `{ts, counts, total}` per run. It already calls
  [`_read_run(ts)`](../webapp/backend/app.py#L227) which parses the full `changes` from
  `diff.jsonl` — so the searchable content is in hand and just discarded.
- [`webapp/backend/app.py:219`](../webapp/backend/app.py#L219) `_run_counts(changes)` —
  counts by change type. A change row is `{change, id, company, title, location, …}`.
- [`webapp/backend/app.py:254`](../webapp/backend/app.py#L254) `get_run(ts)` — returns
  full changes for one run (unchanged).
- Precedent — [`services/queries.py:61`](../services/queries.py#L61): `/api/jobs?q=`
  matches case-insensitively against `company + title_raw`. We mirror the semantics.
- Frontend — [`webapp/frontend/src/pages/Activity.tsx:12`](../webapp/frontend/src/pages/Activity.tsx#L12)
  `useQuery(["runs"])`; the Roles search pattern (state → params → query key) lives in
  `webapp/frontend/src/pages/JobsList.tsx`.

## Clarifications

- **What does "search" mean here?** → **Content search** by company/role: filter the run
  list to runs whose changes match the term. (Rejected: change-type filter; date filter.)
- **Companies-search work** (top-box→search + Follow modal, same session) → shipped
  **separately** as PR #45, so this feature is **Activity-only**.
- **Match semantics** → case-insensitive substring over `company + title` of each change,
  matching the `/api/jobs?q=` behaviour for consistency.

## Execution plan

### Phase A — Backend `?q=` on `/api/runs`
Add an optional `q` to `list_runs`. When present: keep only runs with ≥1 change whose
`"{company} {title}"` contains `q` (case-insensitive); attach `matched` — up to 5 deduped
`"Company: Title"` snippets. Response shape stays `{ts, counts, total}` + optional `matched`.

| # | File | Change |
|---|------|--------|
| 1 | `webapp/backend/app.py` | `list_runs(limit, q=None)` — filter + `matched` |
| 2 | `webapp/backend/tests/test_api.py` | test: `?q=` filters runs + returns matched snippets |

**Gate:** `.venv/bin/python -m pytest webapp/backend/tests/test_api.py -q` green; `ruff check .` clean.

### Phase B — Frontend search box
Search box on Activity (debounce-free, query-key driven like Roles); render matched
snippets under each run row.

| # | File | Change |
|---|------|--------|
| 1 | `webapp/frontend/src/pages/Activity.tsx` | search state + `/runs?q=`; queryKey `["runs", q]`; show `matched` |

**Gate:** `npm run lint` clean; `npm run build` passes.

### Phase C — Docs + live verify
Tick the webapp tactical checklist (Phase 3 runs/Activity) note; smoke-test on the local
server (search "monzo" → only matching runs).

**Gate:** manual check on `127.0.0.1:8765/activity`.

## Alternatives considered

- **New `/api/runs/search` endpoint** — rejected; a `q` param on the existing `/api/runs`
  is simpler and mirrors `/api/jobs?q=`.
- **Return full `changes` for every run, filter client-side** — rejected; larger payloads
  and duplicates the filter logic in the client. Server already has the data.
- **Change-type / date filters** — rejected; low value (runs are few and newest-first;
  content search is the useful axis).

## Files touched

**Modified:** `webapp/backend/app.py`, `webapp/backend/tests/test_api.py`,
`webapp/frontend/src/pages/Activity.tsx`, `specs/webapp/tactical.md`, `specs/README.md`
**Created:** `specs/activity-search.md`
**Deleted:** —

## Open questions

- None blocking. Debouncing the search input is skipped (client-side-cheap; the query is
  server-side but runs are few) — revisit only if the run history grows large.

## Rollback plan

Fully revertable — additive `q` param (default `None` = today's behaviour) + one frontend
page. No schema/data changes. Revert the commit(s) to restore.

## Outcome

Built as planned, no deviations.
- **Backend** ([`webapp/backend/app.py`](../webapp/backend/app.py)): `list_runs(limit, q=None)`
  + `_run_matches()` — server-side filter (reuses `_read_run`'s changes) returning ≤5
  `Company: Title` snippets. Additive; `q` absent = prior behaviour.
- **Frontend** ([`Activity.tsx`](../webapp/frontend/src/pages/Activity.tsx)): search box
  (queryKey `["runs", q]`), matched-snippet line per run, "No runs match." empty state.
- **Tests:** `test_runs_content_search` (company + title match, snippets, no-match, no-q).
  268 tests pass; ruff + eslint clean. Live-verified: `?q=monzo` → 1 run w/ snippets.

Branch `feature/activity-search`; anchor commit `959b69b`, implementation `7addbc9`.
No follow-ups except the deferred RunDetail highlight (Non-goals).
