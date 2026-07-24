# specs/ — dev docs

Documentation for people working *on* JobRadar (forks, self-hosting, new
adapters). If you just want to *use* it, start at
[`docs/getting-started.md`](../docs/getting-started.md).

## Read in this order

1. [`constitution.md`](constitution.md) — the principles. Crawler ethics (the
   single authority), hybrid hardcoded-logic + optional-Claude design,
   local-first storage. Everything else defers to this.
2. [`product-spec.md`](product-spec.md) — the original product/domain spec
   (moved from the repo root). Authoritative for business rules (seniority
   ladder §11, filters, salary §13, dedup §15, lifecycle); **historical** for
   storage/output (it predates the Markdown store and describes XLSX).
3. [`build-spec.md`](build-spec.md) — the implementation spec. Storage layout,
   the scraping ladder, config schemas, derived indexes, and where it
   deliberately diverges from the product spec (§9).

## Spec-driven development

Specs live here and are written before code (inspired by GitHub's Spec Kit).
Four layers, narrowing from durable principles to a concrete task list:

| Layer | File | Question it answers | Changes… |
| --- | --- | --- | --- |
| **Constitution** | [`constitution.md`](constitution.md) | What principles govern *everything* we build? | rarely |
| **Outcomes** | `<feature>/outcomes.md` | Who is this for and what must become true? (the *what/why*) | per feature |
| **Strategy** | `<feature>/strategy.md` | How we'll do it — and explicitly what we won't | per feature |
| **Tactical** | `<feature>/tactical.md` | The actual, checkable to-do list | as we work |

Rule of precedence: **Constitution > Outcomes > Strategy > Tactical.** If a lower
layer conflicts with a higher one, the higher one wins; change the higher doc
deliberately rather than letting code drift from it.

## Current specs

- **Core (CLI / scraper):** [`build-spec.md`](build-spec.md) — the detailed implementation
  spec for the `seek`/`enrich` pipeline (predates this structure; treated as the core
  feature's combined strategy+tactical). Domain rules live in [`product-spec.md`](product-spec.md).
- **Web app:** [`webapp/outcomes.md`](webapp/outcomes.md) · [`webapp/strategy.md`](webapp/strategy.md) · [`webapp/tactical.md`](webapp/tactical.md)
- **Web features:** [`setup-wizard.md`](setup-wizard.md) · [`job-notes-applied.md`](job-notes-applied.md) · [`company-management.md`](company-management.md) · [`web-refresh-and-activity.md`](web-refresh-and-activity.md) · [`activity-search.md`](activity-search.md) · [`notifications.md`](notifications.md)
- **MCP server:** [`mcp-server.md`](mcp-server.md) — tools, transport, host allowlist ([user-side setup](../docs/claude-mcp.md))
- **ATS adapters:** [`oracle-adapter.md`](oracle-adapter.md) · [`recruitee-adapter.md`](recruitee-adapter.md) · [`revolut-people-adapter.md`](revolut-people-adapter.md) · [`cvmail-adapter.md`](cvmail-adapter.md)  (the JSON-API adapters — greenhouse/ashby/lever/smartrecruiters/workday/talemetry — are covered in `build-spec.md` §4.1)
- **Deploy:** [`deploy.md`](deploy.md) — CI/CD runbook: tag-to-release → GHCR → push-deploy over Tailscale to a Raspberry Pi. Specific to the author's setup; treat it as an example self-host recipe.
- **Backlog:** [`backlog.md`](backlog.md) 📋 — deferred ideas, not scheduled.

## Adding an ATS adapter

Follow the shape of an existing one — a fetcher class with
`listing() -> ListingResult` and `detail(url) -> markdown`, plus `rung_name`,
`needs_detail`, `check_robots` attributes. Register it in `scrapers/ladder.py`
(a `detect_ats` marker + a `_build_rungs` rung) and in `services/discovery.py`
if it should be followable by pasting a URL. Write network-free tests with a
faked HTTP layer (`tests/test_talemetry.py` is a good template), and add a
spec here. `constitution.md §2` governs what's acceptable to fetch: public
data only, politely.

## Conventions

- New design/spec docs **always** go under `specs/` (never the repo root).
- A feature gets its own folder: `specs/<feature>/{outcomes,strategy,tactical}.md`.
- Keep each doc honest about **non-goals** — what we deliberately won't do is as
  important as what we will.
- Tests are network-free: `python -m pytest tests/ webapp/backend/tests/`.
  Lint: `ruff` (Python), `eslint` + Vite build (frontend).
- Trunk-based: feature branch → PR (CI gate) → squash to main → `git tag vX.Y.Z`
  builds and deploys (see [`deploy.md`](deploy.md)).
- [`CLAUDE.md`](../CLAUDE.md) at the repo root is the working agreement for AI
  coding agents.
