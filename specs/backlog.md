# Backlog — future considerations

> **Status:** 📋 ideas, not scheduled. Deferred items surfaced during development —
> captured so they're not lost. None are committed work. Promote an item to its own
> spec (`specs/<feature>.md`) when it's picked up. Ordered roughly by value.

## Role coverage

### Role-tracks — track non-PM roles for chosen companies
The classifier is hard-wired to the **senior-PM taxonomy** (`services/title_normalizer.py`).
There's no way to track a *different* role class (e.g. Forward Deployed Engineer, Product
Engineer) for a subset of companies. Design options (from the discussion):
- **A. Per-company override** — a `match_titles` keyword include in `config/overrides/<slug>.yaml`
  that bypasses the seniority gate. Smallest change; reuses `merged_profile`. Good for "watch X at a few companies".
- **B. `config/tracks.yaml`** — named tracks (match patterns + company scope), roles tagged
  with their track. The scalable option if several role types across different company sets.
- **C.** Multiple named search profiles (bigger — touches profile model, pipeline, store, UI).
**Cross-cutting:** tag each kept role with its track, else non-PM roles pollute the PM
seniority sort / open-role counts / cap / Slack digest.

### "Product Builder" / hybrid roles
A survey (Product Engineer / Forward Deployed Engineer / Member of Technical Staff /
Founding-X) found the concept is **big at AI-native companies** but these are *engineering*
roles, not PM. If wanted, add **"Product Engineer" as a role-track** (needs Role-tracks above).
Fit for a PM depends on hands-on coding — assess per-CV.

### Founding-PM visibility
Two gaps block Founding-PM roles from showing up:
1. **Taxonomy:** a bare "Founding Product Manager" ranks Mid (2) → dropped. Add a rule so
   "Founding …" product roles rank senior (like the Staff / Product Lead fixes).
2. **Company set:** the tracked list skews late-stage; Founding-PM roles live at **seed /
   Series-A** companies. Add a batch of early-stage (e.g. recent YC AI) companies.

## Web app

- **Phase 2 — job write-back** (`webapp/tactical.md` Phase 2, not started): `PATCH /api/jobs/{id}`
  for editable notes + status (Applied / Not interested) from the UI, round-tripping through `seek`.
- **Enrichment cards** on the Companies page (description / HQ / industry / confidence) — the
  last unshipped Phase-3 item; the `enrich` data + `company_index.jsonl` already exist.
- **Activity run-detail highlight** — highlight the matched changes inside a run when arriving
  via Activity search (non-goal deferred in `activity-search.md`).
- **`/runs/{ts}` Slack summary link** — the notifier deep-links per role but not to a run summary.
- **MCP server** wrapping the web API (follow/unfollow/seek) so companies can be managed by
  chatting to Claude from mobile; repoint the `job-tracker` skill at the Pi's API.

## Ops / data

- **Config sync** — the Pi's live `/data/config/companies.csv` and the repo's `config/companies.csv`
  diverge (web-UI adds like JPMC/Hostaway don't reach git). Consider an export/commit path so a
  fresh reinstall seeds the real list. Low urgency (volume persists).
- **`seek --no-notify` flag** — a first-class way to run the CLI seek without posting to Slack
  (today: unset `$SLACK_WEBHOOK_URL`, or use the web scan which suppresses it).
- **SQLite read-model** — keep Markdown canonical, add SQLite as a *derived* projection **only**
  when a feature needs it: run/Activity time-series, web write-back with real concurrency, or
  full-text search. Not now (see the DB discussion — the JSONL index already covers fast reads).
