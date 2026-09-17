# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State

This repo is **implemented** (not spec-only). It's a working Python CLI
(`main.py`, Click) plus a uv/FastAPI + React web app (`webapp/`), with a test
suite. When implementing, match the existing conventions.

It's also **deployed**: CI/CD via GitHub Actions (CI on PRs; a `vX.Y.Z` tag builds
an arm64 image to GHCR) deploys to a Raspberry Pi by SSHing over
Tailscale on each tag. The scraper runs **daily at 08:00 Europe/London** and posts new
senior PM roles to Slack, deep-linked to the web app. Runbook: `specs/deploy.md`.

**Architecture authority:** `specs/constitution.md` (principles) → `specs/build-spec.md`
(storage layout, scraping ladder, ATS adapters, fetching policy).
`specs/product-spec.md` (the original root README, cited in code as
"product-spec §N") is the product/domain spec and is **historical for storage &
output** (it describes XLSX, which predates the Markdown store) — defer to
`specs/build-spec.md` for anything about how data is stored or fetched.

**Docs are two-part:** `docs/` is the plain-language **user guide** (no dev
concepts — keep it that way); `specs/` is the **dev docs** (`specs/README.md`
is the index). The root `README.md` is a short landing page linking both.

## What This Builds

A single-user tool to find and track senior Product Management roles at target
companies. Two on-demand modes:

- **Enrich (Exploratory)** — company facts (description, industry, HQ, funding,
  employees) into canonical company Markdown + a derived `company_index.jsonl`.
- **Seek (Job Seek)** — discover/rank currently-open senior PM roles per company.

Every run also emits a per-run change diff and a console/TXT summary.

## Architecture (see `specs/build-spec.md` for detail)

Hybrid: **hardcoded logic for reliability + Claude API only for fuzzy parsing** —
this split is deliberate, keep it.

- **Canonical store is Markdown with frontmatter** (`jobs/<company>/<role>--<id>.md`);
  `data/jobs.jsonl` is a *derived* index. Never overwrite user-owned content
  (`## My notes`, `status: applied`). Store paths resolve via `services/store.py`
  (honours `JSA_ROOT`); writes go through `store.atomic_write_text` (temp+replace).
- **Fetching = scraping ladder**: ATS JSON API → optional Playwright → static HTML,
  with 11 ATS adapters (Greenhouse, Ashby, Lever, SmartRecruiters, Workday,
  Talemetry, RevolutPeople, Oracle, Recruitee, cvMail, Workable). Talemetry uses
  `curl_cffi` (browser-free Cloudflare); Oracle Recruiting Cloud (`*.fa.*.oraclecloud.com`, `specs/oracle-adapter.md`);
  Recruitee (`{slug}.recruitee.com` incl. custom domains, `specs/recruitee-adapter.md`);
  cvMail (UK legal, HTML-only, `fsr.cvmailuk.com/<firm>/`, `specs/cvmail-adapter.md`);
  Workable (`apply.workable.com/<slug>/`, listing POST + v2 detail, `specs/workable-adapter.md`).
- **Claude** (`services/claude_service.py`): title classification, salary/comp
  extraction, company summarization. **Off by default**; always falls back to
  regex/heuristics; responses are validated/projected to a known schema.

Stack: Python 3.12+, requests + BeautifulSoup4, curl_cffi, anthropic, click,
python-dateutil; web app is FastAPI + React (Vite). Most logic stays hardcoded to
keep cost low (~$15–30 for 300 companies vs $150+ pure-API).

## Domain Rules That Are Easy To Get Wrong

These are the non-obvious rules the implementation must encode (product-spec §11–15). They drive most of the business logic:

- **Seniority ranking** (numeric): CPO 9, VP 8, Director 7, Head 6, EIR ~6, Principal 5, Staff 5, Group 4, Product Lead(er) 4, Senior 3, Product Manager/Mid 2, Product Owner 2 (→3 if title contains senior/lead). "Product Lead" ranks Group-tier bare, but VP/Director-prefixed forms rank up even when the seniority word isn't adjacent to "product" (e.g. "…Product Lead… Vice President" → VP). Bank/enterprise **corporate-grade** titles ("Product Manager - Director", "Product Owner, Vice President", either order) rank on the grade, not the function. An **AI/Innovation leadership family** (`include_ai_innovation`, default on) ranks in the same ladder: Chief AI Officer 9, VP 8, Director 7, Head 6, AI/Innovation Lead(er) 4 — leadership role-words only (no manager tier), IC-track qualifiers dropped ("Head of AI Research", "AI Engineer Lead"). **Combined product+engineering** titles rank on the product ladder: conjoined C-suite forms (Chief Product & Technology/Engineering Officer, CPTO) 9 — only when "product" is one of the domains, so a bare CTO is dropped; VP/Director/Head bridge the conjunction already. **Keep a role only if rank ≥ 3**, OR it's a Product Owner and `include product owner` is true.
- **Title exclusions**: drop titles containing marketing/growth marketing/brand (unless a second distinct title matches a PM pattern exactly), and people-ops/HR/talent/design-only roles.
- **Employment type**: exclude Contract — keep only Full time / Part time.
- **Salary**: never convert currency. Detect symbol/code, extract min/max (single number → both), always preserve the original text in `SalaryOriginalText`. Bonus mentioned → `CompensationType = Base+Bonus`.
- **Funding / revenue / employees**: store original strings (no conversion). For employee ranges use the midpoint for heuristics (51–200 → 125) and note the approximation.
- **Location**: accept London / UK / United Kingdom / England-with-London; remote OK if UK/Europe/EMEA-eligible (not US-only). Multi-location postings expand to one row per location, max 5; if >5 and includes London, keep only London + Remote.
- **Per-company cap**: keep top 10 most senior roles; ties broken by posted date, then alphabetical.
- **Dedup**: company = same canonical domain; job = same `JobAdURL` OR same Company + normalized title + first 120 chars of description + same location.
- **Posting lifecycle**: a posting missing for N=2 runs → `Suspected Filled`, then `Closed` on the next run.

## Operational Constraints

Public data only, politely — see **`specs/constitution.md` §2** for the crawler
policy (the single authority): public career pages + the public ATS JSON APIs
browsers already call; `robots.txt` honoured for HTML/browser discovery rungs;
documented ATS APIs not robots-gated; `curl_cffi` fingerprint impersonation only
to reach public JSON behind a passive Cloudflare wall, never to bypass auth/login.
Defaults: 20s request timeout, 1 req/sec per domain, 2 retries with exponential
backoff, 45-day recency cutoff, 30-minute runtime budget per batch, 50 companies
initial / 300 hard cap. Config + API keys are local (single-user tool;
`anthropic_api_key` reads from env, never committed).

When details are ambiguous, **`specs/constitution.md` then `specs/build-spec.md`
are the source of truth** for architecture/storage/fetching, and `specs/product-spec.md` for
product/domain intent. Items marked ✅ in the product-spec are confirmed decisions.
