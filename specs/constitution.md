# Constitution — Job Search Assistant

The durable, project-wide principles that govern every feature. These change
rarely and deliberately. Anything in `outcomes`/`strategy`/`tactical` (or in code)
that conflicts with this document is wrong and must be reconciled here first.

## Purpose
A local, single-user tool that finds and tracks **senior Product Manager roles**
(London / England, Senior+ ) at a defined list of target companies, and surfaces
them where the user will actually see them. Two modes: **Job Seek** (role discovery)
and **Exploratory** (company enrichment).

## Principles

1. **Local-first & single-user.** Runs on the user's Mac. No multi-user, no
   accounts, no SSO. Anything exposed off-device goes over the user's private
   Tailscale network, never the public internet.

2. **Public data only, politely.** Public HTML/JSON endpoints only; respect
   `robots.txt`; per-domain rate limiting, timeouts, bounded retries. No login
   areas, no scraping behind auth.

3. **Markdown is canonical; everything else is derived.** `jobs/<company>/<role>--<id>.md`
   (and `companies/<slug>.md`) are the single source of truth. `data/*.jsonl` indexes
   are disposable and rebuilt from frontmatter. Representations must never be allowed
   to drift. **User-owned fields are sacred** — `## My notes` and `status: applied`
   are never overwritten by automation.

4. **Hardcoded reliability + Claude only for the fuzzy bits.** Navigation, filtering,
   ranking, dedup, lifecycle are deterministic code. Claude is used *only* for fuzzy
   parsing (salary/description/title), is **off by default** (cost), and **always**
   has a regex/heuristic fallback.

5. **Cheapest rung first.** The scraping ladder tries ATS JSON APIs before a browser
   before static HTML, via a structured `ListingResult` contract. One bad company
   never kills a run.

6. **Domain rules are fixed and London-focused.** Seniority ranking, title/location/
   salary handling, dedup, and lifecycle follow the root `README.md` (the domain source
   of truth). Scope is London/England, Senior+ (this is a deliberate constraint, not a
   gap).

7. **Deterministic core, always tested.** The decision logic (title, salary, location,
   identity, reconciliation, adapters) has **network-free tests**; new behaviour ships
   with tests. `main` stays green.

8. **Spec before code, PR before main.** Specs in `specs/` are written/updated before
   building. Work happens on feature branches with PRs; `main` is always releasable.
   Prefer small, reversible changes.

9. **Cost ≈ zero to run.** No paid APIs; scheduling via the OS (launchd/cron), not a
   paid runtime. Claude usage is opt-in.

10. **Honesty & observability.** Report failures plainly; **silence must never be
    mistaken for success** (a run that breaks should say so). Approximations are
    labelled (e.g. enrichment HQ, confidence levels).

## System shape (for orientation)
```
config/*  ──▶  scraping ladder (ATS API → Playwright → static)  ──▶  pipeline (filter/rank/parse)
                                                                          │
                          jobs/*.md  ◀── reconciler (lifecycle) ──────────┘
                              │                              data/runs/<ts>/diff.jsonl
                  data/jobs.jsonl (derived index)
                              │
        CLI (seek/enrich/roles/new/follow) · Skill · [web app] · notifications
```

## Authority
- **Domain rules:** root `README.md`.
- **Core build detail:** [`specs/build-spec.md`](build-spec.md).
- **Per-feature:** `specs/<feature>/{outcomes,strategy,tactical}.md`.
