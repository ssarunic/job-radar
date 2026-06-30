# Web App — Tactical

> **Layer:** Tactical (the checkable to-do list). Executes [`strategy.md`](strategy.md).
> Each phase is independently shippable (own branch + PR). Check items off as done.
>
> **Status (2026-06-30):** Phases 0 and 1 shipped. Phase 4 mostly shipped
> (notifications + Tailscale + heartbeat). Phase 3 partially shipped — company list +
> detail (roles) + follow/unfollow are live; enrichment cards, the runs API, and the
> Activity page are not. Phase 2 (job write-back: editable notes/status) not started.
> Company-management design: [`../company-management.md`](../company-management.md).

## Phase 0 — Scaffold
- [x] `webapp/backend/` — uv project (`pyproject.toml`), FastAPI + uvicorn; import path to repo root so `services.*`/`outputs.*` resolve.
- [x] `webapp/frontend/` — Vite + React + TS; router, react-query, react-markdown, plain CSS (`index.css` — Tailwind not used).
- [x] Dev: Vite proxy `/api` → `http://127.0.0.1:8765`. Prod: FastAPI mounts the built `dist/` as static.
- [x] Entrypoint serves API (+ static in prod); documented in `webapp/README.md`.
- [x] Add `webapp/` build artifacts (`node_modules`, `dist`, `.venv`) to `.gitignore`.

## Phase 1 — Read-only core  *(the heart of the ask)*
- [x] `GET /api/stats` — counts (open / new-7d / companies / last-run ts).
- [x] `GET /api/jobs` — read `data/jobs.jsonl`, `queries.group_roles`, filter `status|company|min_rank|q`, sort `seniority|recent`.
- [x] `GET /api/jobs/{id}` — locate MD by id, return frontmatter + raw Markdown body + extracted notes.
- [x] **Jobs list page (`/`)** — top-bar stats; filter/sort controls (incl. Seniority / Most-recent toggle); dense rows (company · title · seniority pill · locations · salary · first_seen · status badge); Open/Past via status filter; row → detail.
- [x] **Job detail page (`/jobs/:id`)** — header (title, status badge, seniority, locations, employment, workplace, salary, dates, source, "View original" → `job_ad_url`); render Markdown ad; Requirements; notes shown read-only (Phase 2 makes editable). **Mobile-first.**
- [x] Empty/404 states; loading states.
- [x] **Acceptance:** open `/jobs/<id>` directly → correct role renders with formatted ad on mobile.

## Phase 2 — Write-back
- [ ] `PATCH /api/jobs/{id}` — `{notes?, status?}`; write via `md_writer.write_posting` (preserve everything else), then `index_builder.rebuild`. Reject unknown status values.
- [ ] Detail page: editable notes (autosave/explicit save) + status control (Applied / Not interested / reopen).
- [ ] Guard: never clobber scraper-managed fields; `applied` round-trips through a later `seek` (covered by reconciler — add a test).
- [ ] **Acceptance:** set Applied + note in UI → file updated → next `seek` keeps both, no re-add.

## Phase 3 — Companies & Activity
- [x] `GET /api/companies`, `GET /api/companies/{slug}` — that company's open roles. Plus **write** endpoints (`POST` follow + scan, `PATCH` active) beyond the original read-only scope — see [`../company-management.md`](../company-management.md). *(Enrichment fields — description / HQ / industry / confidence — not surfaced yet.)*
- [x] **Companies page** (name · ATS · # open roles · follow/unfollow; add-by-name/URL with scan-on-follow) + **company detail** (open roles list + careers/ATS link). *(Enrichment cards deferred.)*
- [ ] `GET /api/runs`, `GET /api/runs/{ts}` from `data/runs/*/diff.jsonl` + `summary.txt`.
- [ ] **Activity page** — run feed with added/closed/updated, linking to roles.

## Phase 4 — Live & linked
- [x] `web_base_url` in `config/settings.yaml`; Slack/ntfy notifier emits `{web_base_url}/jobs/{id}` per new role. *(`/runs/{ts}` summary link not built.)*
- [x] Tailscale: bind/serve so the tailnet hostname reaches the app from phone; one-time setup documented in `webapp/README.md` + `specs/deploy.md`.
- [ ] `POST /api/seek` — background task + global "Refresh now" button + last-run/"running…" indicator. *(Per-company **scan-on-follow** shipped instead; a global refresh button is still TODO.)*
- [x] Heartbeat + failure alert in the notifier (so silence ≠ broken) — daily "all quiet" + failed-company flag.
- [x] **Acceptance:** new role found by scheduled `seek` → Slack message → tap on phone → role detail over Tailscale.

## Cross-cutting
- [x] Backend: thin route layer; reuse `services`/`outputs`; no business logic duplicated.
- [x] Tests: API handlers tested against a temp store (network-free); keep `main` green.
- [ ] Optional single shared token if ever tunnelled beyond Tailscale. *(Not needed — tailnet-only.)*
- [x] Constitution unchanged — no principle changed for this feature (as expected).

## Explicitly deferred (from strategy non-goals)
SQLite read-model · company-*profile* editing in UI · auth/multi-user · analytics/fit-score.
*(Company-**list** editing — follow / unfollow — was added since, via [`../company-management.md`](../company-management.md).)*
