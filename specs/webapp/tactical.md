# Web App — Tactical

> **Layer:** Tactical (the checkable to-do list). Executes [`strategy.md`](strategy.md).
> Each phase is independently shippable (own branch + PR). Check items off as done.

## Phase 0 — Scaffold
- [ ] `webapp/backend/` — uv project (`pyproject.toml`), FastAPI + uvicorn; import path to repo root so `services.*`/`outputs.*` resolve.
- [ ] `webapp/frontend/` — Vite + React + TS; router, react-query, react-markdown, Tailwind.
- [ ] Dev: Vite proxy `/api` → `http://127.0.0.1:8000`. Prod: FastAPI mounts the built `dist/` as static.
- [ ] `uv run` entrypoint that serves API (+ static in prod); document in `webapp/README.md`.
- [ ] Add `webapp/` build artifacts (`node_modules`, `dist`, `.venv`) to `.gitignore`.

## Phase 1 — Read-only core  *(the heart of the ask)*
- [ ] `GET /api/stats` — counts (open / new-7d / companies / last-run ts).
- [ ] `GET /api/jobs` — read `data/jobs.jsonl`, `queries.group_roles`, filter `status|company|min_rank|q`, sort `seniority|recent`.
- [ ] `GET /api/jobs/{id}` — locate MD by id, return frontmatter + raw Markdown body + extracted notes.
- [ ] **Jobs list page (`/`)** — top-bar stats; filter/sort controls; dense rows (company · title · seniority pill · locations · salary · first_seen · status badge); Open/Past toggle; row → detail.
- [ ] **Job detail page (`/jobs/:id`)** — header (title, company link, status badge, seniority, locations, employment, workplace, salary, dates, source, "View original" → `job_ad_url`); render Markdown ad; Requirements; notes shown read-only (Phase 2 makes editable). **Mobile-first.**
- [ ] Empty/404 states; loading skeletons.
- [ ] **Acceptance:** open `/jobs/<id>` directly → correct role renders with formatted ad on mobile.

## Phase 2 — Write-back
- [ ] `PATCH /api/jobs/{id}` — `{notes?, status?}`; write via `md_writer.write_posting` (preserve everything else), then `index_builder.rebuild`. Reject unknown status values.
- [ ] Detail page: editable notes (autosave/explicit save) + status control (Applied / Not interested / reopen).
- [ ] Guard: never clobber scraper-managed fields; `applied` round-trips through a later `seek` (covered by reconciler — add a test).
- [ ] **Acceptance:** set Applied + note in UI → file updated → next `seek` keeps both, no re-add.

## Phase 3 — Companies & Activity
- [ ] `GET /api/companies`, `GET /api/companies/{slug}` (enrichment + that company's roles).
- [ ] **Companies page** (cards: name, description, HQ, industry, confidence, # open roles) + **company detail** (roles list).
- [ ] `GET /api/runs`, `GET /api/runs/{ts}` from `data/runs/*/diff.jsonl` + `summary.txt`.
- [ ] **Activity page** — run feed with added/closed/updated, linking to roles.

## Phase 4 — Live & linked
- [ ] `web_base_url` in `config/settings.yaml`; Slack/ntfy notifier emits `{web_base_url}/jobs/{id}` per new role and a `/runs/{ts}` summary link.
- [ ] Tailscale: bind/serve so the tailnet hostname reaches the app from phone; document the one-time setup in `webapp/README.md`.
- [ ] `POST /api/seek` — background task running the existing pipeline; "Refresh now" button + last-run/“running…” indicator (poll `/api/stats`).
- [ ] Heartbeat + failure alert in the notifier (so silence ≠ broken) — ties the daily loop together.
- [ ] **Acceptance:** new role found by scheduled `seek` → Slack message → tap on phone → role detail over Tailscale.

## Cross-cutting
- [ ] Backend: thin route layer; reuse `services`/`outputs`; no business logic duplicated.
- [ ] Tests: API handlers tested against a temp store (network-free); keep `main` green.
- [ ] Optional single shared token if ever tunnelled beyond Tailscale.
- [ ] Update [`../constitution.md`](../constitution.md) only if a principle actually changes (it shouldn't for this feature).

## Explicitly deferred (from strategy non-goals)
SQLite read-model · company-list/profile editing in UI · auth/multi-user · analytics/fit-score.
