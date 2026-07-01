# specs/

Spec-driven development for Job Search Assistant, inspired by GitHub's Spec Kit.
**Specs live here and are written before code.** Four layers, narrowing from
durable principles to a concrete task list:

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
  feature's combined strategy+tactical). Domain rules still live in the root `README.md`.
- **Web app:** [`webapp/outcomes.md`](webapp/outcomes.md) · [`webapp/strategy.md`](webapp/strategy.md) · [`webapp/tactical.md`](webapp/tactical.md)
- **Web features:** [`company-management.md`](company-management.md) · [`web-refresh-and-activity.md`](web-refresh-and-activity.md) · [`activity-search.md`](activity-search.md) · [`notifications.md`](notifications.md)
- **ATS adapters:** [`oracle-adapter.md`](oracle-adapter.md) · [`recruitee-adapter.md`](recruitee-adapter.md) · [`revolut-people-adapter.md`](revolut-people-adapter.md)  (the JSON-API adapters — greenhouse/ashby/lever/smartrecruiters/workday/talemetry — are covered in `build-spec.md` §4.1)
- **Backlog:** [`backlog.md`](backlog.md) 📋 — deferred ideas, not scheduled.

## Conventions
- New design/spec docs **always** go under `specs/` (never the repo root).
- A feature gets its own folder: `specs/<feature>/{outcomes,strategy,tactical}.md`.
- Keep each doc honest about **non-goals** — what we deliberately won't do is as
  important as what we will.
