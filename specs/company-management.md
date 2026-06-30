# Company Management (web write API + UI)

> **Status:** proposed. Lets the followed-company list be managed from the web app
> instead of SSH + `docker exec`. Defers to `constitution.md` (principles) and
> `build-spec.md` (storage/surfaces); this specs one feature on top of them.

## Problem

Adding/removing followed companies on the deployed Raspberry Pi is painful: the
web app is **read-only** (Phase 1), so the only way to change the list is to SSH in
and run `docker exec … python main.py follow/unfollow`. For a headless server this
is the main day-to-day friction.

## Key finding — persistence is already solved (do not re-do it)

The followed-company list is `config/companies.csv`, read/written by
`services/registry.py` via `store.config_dir()`. Because `store.root()` honours
`JSA_ROOT` (=`/data` on the Pi), `config_dir()` resolves to **`/data/config`** — on
the persistent `jsa-data` volume. `docker/entrypoint.sh` seeds `/data/config` from
the image **only on first run** (`if [ ! -f … ]`), never overwriting after. So
`follow`/`unfollow` already persist across redeploys. **This feature is about access
(a write API + UI), not persistence.**

## Goals

- Add / remove (soft) / list followed companies from the web app, on the tailnet.
- Reuse the existing `services/registry.py` + `services/discovery.py` logic verbatim
  — the web is a thin surface, exactly like the read API (constitution §3).
- Surface auto-detected ATS feedback and dedupe on add; show active state + open-role
  counts in the list.

## Non-goals

- **No auth / no public exposure.** The web app is tailnet-only (single-user tool,
  constitution §2); the network boundary is the access control. Do not add login.
- **No hard delete.** Unfollow = `active:false` (keeps the company's data), matching
  the CLI. Hard delete is out of scope.
- **No MCP** yet — see Future. The HTTP API below is the shared substrate an MCP
  server (or the existing `job-tracker` skill, repointed at the Pi) would wrap later.

## Design

### Backend — `webapp/backend/app.py` (4 endpoints)

A thin layer over `registry` + `discovery`, mirroring the read endpoints. Discovery
needs an `HttpClient`; build one per request from settings (network only on the
auto-detect path).

| Method & path | Body | Behaviour | Responses |
|---|---|---|---|
| `GET /api/companies` | — | List all (active + inactive) with open-role counts | `200 {count, companies:[…]}` |
| `GET /api/companies/{slug}` | — | One company + its open role summaries (`queries.list_roles`, sort=seniority) | `200 {company, roles:[…]}` · `404` if unknown |
| `POST /api/companies` | `{query}` **or** `{name, ats_type, careers_url, ats_slug?}`; `scan` (default `true`) | `query` → `discovery.discover()`; explicit fields → manual row (no network). `registry.add_company()`, then (if `scan`) a one-off `run_service.seek_run` for just this company so its roles show immediately | `201 {company, scanned}` · `409` if already tracked · `422` if not auto-detected |
| `PATCH /api/companies/{slug}` | `{active: bool}` | `registry.set_active()` | `200 {slug, active}` · `404` if slug unknown |

- Each `company` object: `{name, slug, ats_type, ats_slug, careers_url, active, open_roles}`.
  `open_roles` must be counted over **grouped** roles (`queries.group_roles`), not raw
  index rows — the index stores one row per location, so a multi-location role would
  otherwise be over-counted (it showed "2 open" while the list showed 1). Same basis
  as `queries.stats` / `list_roles`. One index load per call, no per-row queries.
- The auto-detect path (`POST {query}`) runs `discovery.discover` synchronously
  (FastAPI offloads sync handlers to a threadpool); bounded by the existing 20s
  request timeout. Acceptable for an interactive add.
- **Scan-on-follow** (`scan: true`, default): after a successful add, run
  `run_service.seek_run` scoped to *just* the new company (one ATS fetch + pipeline,
  reconcile only ages that slug), so its roles appear in the UI immediately rather
  than at the next 08:00 run. **Slack is suppressed** for this interactive scan
  (settings copied with `notify.enabled=false`); the scan is **non-fatal** (a fetch
  error/timeout still returns `201` with `scanned:false`). Synchronous so the
  response's `open_roles` reflects what was found.

### Backend — registry write hardening

`registry._write` currently does a plain `open(path, "w")`. The web container writes
while the scraper container may read the same file on the shared volume; a reader
could observe a truncated CSV mid-write. **Render the CSV to a string and write via
`store.atomic_write_text`** (temp + `os.replace`, same guarantee the canonical store
already uses). Pure refactor — no signature change.

### Frontend — `webapp/frontend/src`

- Routes `/companies` and `/companies/:slug` (`react-router`), nav link in `App.tsx`.
- `pages/Companies.tsx`:
  - **List** of tracked companies (TanStack Query `["companies"]`): name, ATS badge,
    open-role count, and an active toggle (Follow / Unfollow). Rows are clickable →
    the detail page; the toggle button `stopPropagation`s so it doesn't navigate.
  - **Add** row: one input (company name *or* careers URL) + "Follow" (shows
    "Scanning…"). On submit, `POST /api/companies {query}`; on success show the
    discovered ATS + roles found; friendly message on `409` / `422`.
  - Mutations invalidate `["companies"]` (and `["stats"]`) so the list refreshes.
- `pages/CompanyDetail.tsx` (`/companies/:slug`): company header (ATS badge, open
  count, follow/unfollow), a **careers/ATS link out**, and the company's open roles
  (each linking to the role detail). Empty-state links to the careers page.
- `pages/JobsList.tsx`: a **sort toggle** (Seniority / Most recent) wired to the
  backend's existing `sort=seniority|recent`.
- `api.ts`: add a small `apiSend(path, method, body)` helper (the current `api()` is
  GET-only).

### Security / safety

- Tailnet-only; no auth (see Non-goals). Validate/trim inputs; reject empty `query`.
- Single-writer in practice (only the web container mutates config; the scraper only
  reads); atomic write covers the read-during-write race.

## Build sequence

1. **Registry atomic write** — refactor `_write`; existing registry tests stay green.
2. **Backend endpoints** + tests (`webapp/backend/tests/test_api.py`): list, manual
   add, dedupe `409`, toggle, `404`; monkeypatch `discovery.discover` for the
   `{query}` path so tests stay network-free.
3. **Frontend** — `api.ts` helper, `Companies.tsx`, route + nav link.
4. **Docs** — note the new surface in `build-spec.md`; `README` web-app blurb.

## Testing

- Backend: extend `webapp/backend/tests/test_api.py` against a temp `JSA_ROOT`
  (seed a `config/companies.csv`), network-free (discovery monkeypatched).
- Registry: existing `tests/test_registry*.py` must stay green after the atomic-write refactor.
- Frontend: keep parity with current coverage (no test harness today) — manual check
  via `npm run build` + the dev server.

## Future

- **MCP server** wrapping these endpoints → manage by chatting to Claude from mobile;
  repoint the `job-tracker` skill at the Pi's API instead of the local store.
- **"Follow & scan now"** — trigger a single-company `seek_run` on add.
- Per-company **priority** editing and reordering.
