# AGENTS.md

Guidance for coding agents (Codex, etc.) working in this repository.

## Source of truth (read these first)

This repo is **implemented**, not spec-only. The authoritative docs, in order:

1. **`specs/constitution.md`** — non-negotiable principles (local-first; Markdown
   canonical / JSONL derived; crawler ethics; never overwrite user-owned content).
2. **`specs/build-spec.md`** — the build/architecture spec: **storage layout,
   scraping ladder, ATS adapters, and fetching policy live here.**
3. **`CLAUDE.md`** — working guidance + the domain rules that are easy to get
   wrong (seniority ranking, title/employment/location filters, salary, lifecycle).
4. **`README.md`** — the original product/domain spec. **Historical for storage &
   output** (it predates the Markdown store and describes XLSX); defer to
   `specs/build-spec.md` for anything about how data is stored or fetched.

If these ever disagree, the constitution wins, then build-spec, then CLAUDE.md;
README is last and only for product/domain intent.

## Architecture in one paragraph

Python CLI (`main.py`, Click) + a uv/FastAPI + React web app (`webapp/`). Two
modes: **seek** (find/rank senior PM roles) and **enrich** (company facts).
Canonical store is **Markdown with frontmatter** (`jobs/<company>/<role>--<id>.md`);
`data/jobs.jsonl` is a derived index. Fetching uses a **scraping ladder** (ATS
JSON API → optional Playwright → static HTML) with 7 ATS adapters. Claude is used
**only** for fuzzy parsing and is **off by default**, always with a heuristic
fallback. Store paths resolve through `services/store.py` (honours `JSA_ROOT`).

**Deployed** via CI/CD (push a `vX.Y.Z` tag → GitHub Actions → arm64 image → GHCR →
push-deploy over Tailscale SSH) to a Raspberry Pi; the scraper runs daily at 08:00 and
posts new roles to Slack. See `specs/deploy.md` (and `[[deploy-pipeline]]` memory).

**Lint/test (CI-gated, run before pushing):** `ruff check .` (config in `ruff.toml`;
broad `except` is an intentional pattern so `BLE` is off), `python -m pytest tests/
webapp/backend/tests/ -q`, and in `webapp/frontend/`: `npm run lint` (ESLint) + `npm run build`.
