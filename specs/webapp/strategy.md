# Web App — Strategy

> **Layer:** Strategy (the *how*, and what we deliberately won't do). Serves
> [`outcomes.md`](outcomes.md); governed by [`../constitution.md`](../constitution.md).

## Approach in one paragraph
A **FastAPI** backend (managed by **uv**) reads the existing canonical store and writes
user fields back through `md_writer`; a **Vite + React + TypeScript** SPA renders it.
No new database — `data/jobs.jsonl` is the read model, the MD file is the write target.
The app is served on the Mac and reached privately over **Tailscale**. Each role has a
stable `/jobs/<id>` URL so notifications can deep-link.

## Architecture
```
React SPA (Vite)  ──/api──▶  FastAPI (uv)  ──reads──▶  data/jobs.jsonl, jobs/*.md, companies/*, data/runs/*
      ▲                          │
      └───────── PATCH ──────────┘ writes notes/status ──▶  md_writer.write_posting ──▶ index_builder.rebuild
```
- **Dev:** Vite dev server proxies `/api` → FastAPI (uvicorn). **Prod:** FastAPI serves
  the built static bundle — one process, one port, started by `uv run`.
- **Reuse, don't reinvent:** the API imports existing modules — `services.queries`
  (list/group/filter), `outputs.md_writer` (read/write MD), `outputs.company_index`,
  `services.reconciler` (diffs), `services.registry`. The backend lives in-repo so these
  imports work.

## Key decisions (with rationale)
- **No database (now).** At tens–hundreds of roles, reading `jobs.jsonl` + MD is fast and
  keeps the constitution's "MD canonical, indexes derived" intact. A SQLite read-model
  can slot behind the same API later without changing the canonical store.
- **Writes go through `md_writer` + index rebuild.** The web app must not become a second
  source of truth (Constitution §3). Editing a note PATCHes the MD's `## My notes`; setting
  status writes frontmatter; then the index is regenerated. This is exactly what `seek`'s
  reconciler already respects (`status: applied` is never auto-touched).
- **Stable deep links.** Role URL = `/jobs/<id>` (the canonical 8-char id). Notifications
  build `{web_base_url}/jobs/<id>` from a new `web_base_url` setting.
- **Reachability via Tailscale.** Bind the server to the tailnet; the user opens it at a
  stable tailnet hostname from phone/laptop. Private by default — satisfies "never public".
- **Markdown rendering** with `react-markdown` (the ads are already stored as Markdown).
- **Triggering scrapes** (optional, Phase 4) runs the existing `seek` as a **background
  task**; the request returns immediately. The web app never scrapes directly.

## API contract
| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/stats` | header counts (open, new-this-week, companies, last run) |
| GET | `/api/jobs?status=&company=&min_rank=&q=&sort=` | role list (grouped via `queries.group_roles`) |
| GET | `/api/jobs/{id}` | detail: frontmatter + Markdown body + notes + history |
| PATCH | `/api/jobs/{id}` | `{notes?, status?}` → write MD, rebuild index |
| GET | `/api/companies` · `/api/companies/{slug}` | enrichment + that company's roles |
| GET | `/api/runs` · `/api/runs/{ts}` | run history + diff feed |
| POST | `/api/seek` *(Phase 4)* | trigger a background scrape |

## Pages (see outcomes for content)
Jobs list (`/`) · Job detail (`/jobs/:id`, mobile-first, the deep-link target) ·
Companies (`/companies`, `/companies/:slug`) · Activity/Runs (`/runs`).
Visual language: dense list + card detail; status colours (open=green, suspected=amber,
closed=grey, applied=blue, rejected=red); seniority pills; salary emphasised; responsive.

## What we will NOT do (non-goals / guardrails)
- **No second source of truth.** No caching job data into the web layer; always read the
  canonical store; all writes via `md_writer` then rebuild the index.
- **No database, no ORM** in this iteration.
- **No public exposure**, no third-party auth. Tailscale-only; at most a single shared
  token if ever tunnelled.
- **No scraping from within the web process** — delegate to the existing `seek` pipeline
  as a background task.
- **No blocking the event loop** on a scrape or a Claude call.
- **No editing of the company list / search profile from the UI** this iteration.
- **No framework sprawl** — plain React Query + react-router + react-markdown; resist
  adding heavy state libraries or a component kit beyond minimal styling.

## Risks & mitigations
- **Write during a running `seek`** → both touch MD + rebuild the index. Mitigate: web
  writes target only user fields and rebuild after writing; keep operations small;
  (later) a simple file lock if needed.
- **Tailscale URL changes / base URL** → store `web_base_url` in `config/settings.yaml`;
  notifier reads it.
- **Mobile rendering of long ads** → mobile-first detail layout; collapse long sections.
- **id stability** → already guaranteed by Constitution §3 (URL-keyed ids), so deep links
  don't rot across scrapes.

## Tech stack
Backend: Python 3.12+, FastAPI, uvicorn, uv (pyproject). Frontend: Vite, React, TypeScript,
react-router, @tanstack/react-query, react-markdown, Tailwind (minimal). Layout: `webapp/`
(`backend/`, `frontend/`).
