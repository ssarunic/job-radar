# Build Spec — Job Seek Mode (Local-First)

> **Status:** implemented & deployed — live on a Raspberry Pi via CI/CD
> (tag → GHCR arm64 image → push-deploy over Tailscale SSH), daily 08:00 scraper → Slack. See `specs/deploy.md`.
> **Relationship to `README.md`:** `README.md` remains the source of truth for *domain rules*
> (seniority ranking, title/location/salary handling, dedup, lifecycle). This document is the
> source of truth for *how we build and store* the Job Seek pipeline. Where the two differ, the
> divergence is called out under [§9 Divergence from README](#9-divergence-from-readme).

---

## 1. Scope of this iteration

Build a **one-shot CLI** (`python main.py seek`) that, for a configured list of companies:

1. Resolves each company's careers listing.
2. Fetches open roles using the **scraping ladder** (ATS JSON API → Playwright → static HTML).
3. Applies the README's filtering + ranking rules.
4. Writes one Markdown file per kept role (canonical record) and regenerates a JSONL index.
5. Emits a per-run diff and a console/TXT summary.

**Built since:** scheduler (launchd/cron via `scripts/`) + ntfy/Slack notifications
(`outputs/notify.py`, fires only on new/reopened roles; Slack deep-links to the web app) — see §13.

**Built since:** Exploratory/company-enrichment mode (`enrich` command, `companies/<slug>.md`
canonical + `data/company_index.jsonl`) — see §14.

**Built since:** Web company management — the web app gained a write surface over
`services.registry` + `services.discovery`: list/follow/unfollow
(`GET/POST /api/companies`, `PATCH /api/companies/{slug}`), a **company detail page**
(`GET /api/companies/{slug}` → open roles + careers link), **scan-on-follow** (a new
company is seeked immediately, Slack suppressed), and a **Seniority / Most recent
sort** toggle on the roles list. So the followed-company list is managed from the
browser instead of SSH + `docker exec`. Tailnet-only, no auth. See
`specs/company-management.md`.

**Built since:** Web "Refresh now" + Activity — a global **`POST /api/seek`** runs a
full seek in the background (in-process lock, `GET /api/seek` status, Slack
suppressed) behind a topbar **↻ Refresh** button with a **top loading bar +
per-company progress** ("Scanning {company} k/N", from `seek_run`'s progress
callback); an **Activity** page reads run
history (`GET /api/runs`, `GET /api/runs/{ts}` over `data/runs/*/diff.jsonl` +
`summary.txt`, timestamp-validated) and shows each run's added/reopened/updated/closed
roles. See `specs/webapp/tactical.md` (Phases 3–4).

**Built since:** CI/CD + deploy — GitHub Actions (CI on PRs; `vX.Y.Z` tag → arm64 image → GHCR),
multi-stage Docker + Compose, push-deploy over Tailscale SSH to the Raspberry Pi, in-container 08:00
daily scheduler (`scripts/scheduler.py`), and a Workday UK location facet — see `specs/deploy.md`.

**Still out of scope** (deferred): Telegram/email notifiers, XLSX export, fit scoring,
web-app write-back (edit notes / mark applied), GitHub branch protection (needs Pro on private repos).

Build against **2–3 companies of different ATS types** first (one Greenhouse/Lever-style API,
one custom JS site requiring Playwright) so both paths are exercised before scaling the list.

---

## 2. Storage model (the key decision)

Three representations, with **one canonical source** so they can't drift:

| Artifact | Role | Format |
| --- | --- | --- |
| `jobs/<company-slug>/<role-slug>--<id>.md` | **Canonical record** per posting (+ user notes) | Markdown w/ YAML frontmatter |
| `data/jobs.jsonl` | **Derived index**, rebuilt from frontmatter every run | JSON Lines (one object/line) |
| `data/runs/<ts>/diff.jsonl` | Per-run change record | JSON Lines |

Rules:

- **Frontmatter is canonical.** Lifecycle fields (`first_seen`, `last_seen`, `status`) and the
  user's `## My notes` live in the MD file. The scraper reads existing frontmatter to compute the
  diff, updates frontmatter, then **regenerates `jobs.jsonl` from scratch** by scanning all MD files.
- **No single big `jobs.json` array.** JSONL only — line-level git diffs, crash-safe appends,
  nested fields preserved, `pandas.read_json(path, lines=True)` works.
- **Never overwrite the `## My notes` section** or any `status: applied` set by the user. When a
  role's frontmatter is regenerated, preserve user-owned fields (see §6.3).
- **Identity is one MD file per role (#3).** The id keys on the canonical URL only — location
  labels never change identity, so a role with multiple offices is a single canonical record with
  `locations: [...]`. The index is the **derived display view**: `index_builder` expands each role
  to one JSONL row per location (README §12 one-row-per-location). A title rename keeps the id but
  changes the filename slug; the writer removes the stale file (`prior_path`).
- Upgrade path (do **not** build now): swap the derived index for SQLite, keeping MD canonical.

---

## 3. Inputs (author by hand)

### 3.1 `config/companies.csv`

One row per company. CSV is fine here (flat, hand-edited).

| column | required | example | notes |
| --- | --- | --- | --- |
| `name` | yes | NatWest | display name |
| `slug` | yes | natwest | folder name under `jobs/`; lowercase, kebab |
| `careers_url` | yes | https://jobs.natwestgroup.com/search/searchjobs | listing/search page |
| `ats_type` | no | greenhouse \| lever \| ashby \| workday \| smartrecruiters \| custom \| auto | `auto` ⇒ detect (§4.1) |
| `ats_slug` | no | natwest | the org identifier the ATS API expects, if different from `slug` |
| `priority` | no | high | ordering only |
| `active` | no | true | `false` ⇒ skipped without deleting the row |

### 3.2 `config/search_profile.yaml` — the "what I'm looking for" doc

Global criteria. Field semantics map directly onto README §10–13.

```yaml
roles:          ["Product Manager", "Senior Product Manager", "Group Product Manager",
                 "Principal Product Manager", "Head of Product", "Director of Product"]
seniority_min:  3                 # README §11: keep rank >= 3
include_product_owner: true       # README §11 step 8
exclude_titles: ["marketing", "growth marketing", "brand", "design", "hr", "talent", "people ops"]
locations:      ["London", "UK", "United Kingdom", "England"]
allow_remote:   true              # accept if UK/Europe/EMEA-eligible, not US-only
remote_keywords: ["remote", "anywhere", "uk remote", "emea remote", "europe remote"]
employment:     ["Full time", "Part time"]   # exclude Contract
recency_days:   45
max_roles_per_company: 10
```

### 3.3 `config/overrides/<slug>.yaml` — per-company override (optional)

Created **only** when a company needs to deviate. Any key here shadows `search_profile.yaml`
for that company, plus scraping-specific hints:

```yaml
careers_url: "https://...alternate-search-url..."
ats_type: custom
selectors:                 # only for custom Playwright sites
  job_card:     ".job-result"
  title:        ".job-result__title"
  location:     ".job-result__location"
  link:         "a.job-result__link"
wait_for:       ".job-result"   # Playwright selector to await before scraping
locations_add:  ["Edinburgh"]   # extend, don't replace, the global list
```

### 3.4 `config/settings.yaml` — operational constants (README §10)

Hardcoded per single-user tool: `request_timeout: 20`, `rate_limit_per_sec: 1`,
`retries: 2`, `runtime_budget_min: 30`, `max_companies: 300`, `user_agent: "<string>"`,
`anthropic_api_key` (or env var), `headless: true`.

---

## 4. The scraping ladder (cheapest rung first)

For each active company, attempt rungs in order; stop at the first that yields postings.
Log which rung succeeded into each role's `source_detail`.

**Contract (#1).** Every rung's `listing()` returns a `ListingResult(status, postings,
rung, error)` with `status ∈ {ok, empty, blocked, error}`. `open_company()` runs an
ordered attempt loop (`scrapers/ladder.py::_attempt`): stop on `ok` (the winning fetcher
stays open for detail); on `error`/`blocked` fall through to the next rung; on `empty`,
fall through for *discovery* rungs (custom Playwright→static) but treat it as terminal
for an ATS-API rung (trust an API that genuinely returned nothing). Exceptions are caught
and converted to `status=error`, so one bad company never kills the batch.

**Shared HTTP client (#8).** All `requests`-based adapters go through
`scrapers/http_client.py::HttpClient`: per-domain rate limiting, `retries` with exponential
backoff (retry only on connection errors + 429/5xx; never on 4xx), a single User-Agent, and
a `robots.txt` check (`allowed()`, fails open on challenge/missing; `respect_robots: true`).
Discovery rungs (static/Playwright/Talemetry) are robots-checked; documented ATS JSON APIs
are exempt.

### 4.1 Rung 1 — ATS JSON API (no browser)

If `ats_type` is set (or detected), call the platform's public JSON endpoint with `requests`.
Detection (`ats_type: auto`): fetch `careers_url`, inspect final URL/host and page markers:

| ATS | detect signal | jobs endpoint |
| --- | --- | --- |
| Greenhouse | `boards.greenhouse.io`, `grnh.se` | `https://boards-api.greenhouse.io/v1/boards/{ats_slug}/jobs?content=true` — descriptions inline |
| Ashby | `jobs.ashbyhq.com` | `https://api.ashbyhq.com/posting-api/job-board/{ats_slug}?includeCompensation=true` — descriptions inline |
| Lever | `jobs.lever.co` | `https://api.lever.co/v0/postings/{ats_slug}?mode=json` — descriptions inline |
| SmartRecruiters | `careers/jobs.smartrecruiters.com` | `https://api.smartrecruiters.com/v1/companies/{ats_slug}/postings?q=product` + per-posting detail (`/postings/{id}` sections) |
| Workday | host contains `myworkdayjobs.com` | `POST {tenant}.wdN.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` (limit≤20) + per-posting detail (`GET cxs{externalPath}` → description, real date, employment type) |
| Talemetry (Jobvite/Radancy) | `Talemetry` in 404 page / `search_type=talemetry` XHR | `{origin}/search/jobs.json?search_type=talemetry&q=...&per_page=100&page=N` |

This rung handles most companies and is immune to HTML redesigns. Prefer it whenever possible.
**Empirically, of 30 target companies: 10 Greenhouse, 14 Ashby, 1 Lever, 1 SmartRecruiters, 2 Workday, 1 Talemetry, 1 needs work (Google).** Ashby is the modern AI-startup default. `scratchpad/probe_ats.py` detects a company's ATS by trying each API against candidate slugs.

**Cloudflare-walled JSON (e.g. NatWest / Talemetry) — no browser needed.** Some ATS
sit behind Cloudflare, but NatWest's is *fingerprint-based* (passive), not a JS
challenge. So `scrapers/ats/talemetry.py` uses **`curl_cffi` impersonating Safari's
TLS fingerprint** — plain `requests` and Chrome-impersonation get `403`, but Safari
clears both the `jobs.json` listing API and detail pages with **no browser**.
`q=product` is an effective server-side prefilter; the classifier does the rest.

Detail bodies come from the page's **schema.org `JobPosting` JSON-LD** (URL
`/jobs/{id}-{permalink}`), parsed tolerantly (trailing commas). That yields clean
Markdown **plus** structured `employmentType` and `datePosted` — richer than a
rendered-text scrape, and feeds recency + Contract filtering. `needs_detail=True`.

This makes the whole stack **browser-free**: Playwright/Chromium is no longer
required (it was the only browser user). Playwright remains an *optional* fallback
for hypothetical `custom` JS sites (Rung 2) — not installed by default; the ladder
degrades to static HTML when it's absent. A genuine JS challenge (not NatWest's
case) would need a browser or a FlareSolverr sidecar.

### 4.2 Rung 2 — Playwright (JS-rendered sites)

For `ats_type: custom` or when Rung 1 is unavailable/blocked. Use **Playwright (sync API,
Chromium, headless per settings)**:

- `page.goto(url, wait_until="domcontentloaded")`, then `page.wait_for_selector(wait_for)` —
  prefer an explicit selector wait over `networkidle` (more reliable on long-polling sites).
- Extract job cards via the override `selectors`.
- **Bot detection:** if a captcha/challenge page is detected, fall back to a persistent context
  or `playwright-stealth`, and log the company as `blocked` rather than failing the whole run.
- Respect the per-domain rate limit (§5) even though it's a browser.

### 4.3 Rung 3 — static HTML (`requests` + BeautifulSoup)

Last resort for simple server-rendered listings. Same parse contract as Rung 2.

### 4.4 Detail fetch

For each kept posting, fetch its detail page (same ladder) to extract description, requirements,
salary text, and posted date — before the Claude-parsing step (§7).

---

## 5. Operational constraints (README §10, §17)

Public HTML only; respect `robots.txt`; no login areas. Per-domain rate limit **1 req/sec**,
**20s** timeout, **2 retries** with exponential backoff. Enforce the **30-min** runtime budget
with a per-company time slice; when the budget is nearly exhausted, stop early and report partial
results in the summary. Hard cap **300** companies.

---

## 6. Data model

### 6.1 `JobPosting` dataclass (`models/`)

Mirror README §6.2 fields. Minimum set the index/MD must carry:

`id, company, company_slug, title_raw, title_normalised, seniority_level, seniority_rank,
employment_type, workplace_model, locations (list), remote_eligible_regions, salary{min,max,
currency,original_text}, compensation_type, description, requirements, posted_date,
job_ad_url, source_type, source_detail, first_seen, last_seen, last_checked, status, notes`.

### 6.2 `id` (stable key)

`id = sha1(canonical_job_ad_url)[:8]` when a URL exists (README §15 primary key); otherwise
`sha1(company_slug + normalised_title + first_120_chars(description) + sorted(locations))[:8]`.
The `id` is the dedup key and the suffix in the MD filename.

### 6.3 MD file shape

```markdown
---
id: a1b2c3
company: NatWest
company_slug: natwest
title_raw: Senior Product Manager, Payments
title_normalised: Senior Product Manager
seniority_rank: 3
locations: [London, Remote UK]
salary:
  min: 90000
  max: 110000
  currency: GBP
  original_text: "£90,000–£110,000 + bonus"
compensation_type: Base+Bonus
employment_type: Full time
workplace_model: Hybrid
job_ad_url: https://jobs.natwestgroup.com/jobs/12345
source_detail: Greenhouse
first_seen: 2026-06-27
last_seen: 2026-06-27
last_checked: 2026-06-27
status: open            # open | suspected_filled | closed | applied
---

## Description
<full ad as **Markdown** — headings/lists/bold preserved, converted from the ATS
HTML field (Ashby descriptionHtml, Greenhouse content, Lever description+lists,
SmartRecruiters/Workday section HTML) via `scrapers/htmltext.html_to_markdown`>

## Requirements
- <merged bullets>

## My notes
<!-- user-owned; never overwritten by the scraper -->
```

**User-owned, preserve on regeneration:** the `## My notes` body and `status: applied`.
Everything else is scraper-managed.

---

## 7. Filtering, ranking, parsing (delegate to README)

Apply, in order, exactly as specified in the README — do not reinvent:

1. **Title normalisation + seniority rank** — README §11. Keep if `rank >= seniority_min` OR
   (Product Owner AND `include_product_owner`).
2. **Title exclusions** — README §11 steps 5–6 (marketing/brand/HR/design-only).
3. **Employment type** — exclude Contract (README §10).
4. **Location expansion** — one row per location, max 5; >5 with London ⇒ London + Remote only
   (README §12). Remote accepted only if UK/Europe/EMEA-eligible; a remote label naming a
   non-eligible region (`Remote (USA)`, `Remote - Canada`, `Remote (APAC)`, …) is rejected (#3).
5. **Salary** — never convert currency; min/max + currency + original text; bonus ⇒ `Base+Bonus`
   (README §13). **Source preference:** ATS-provided *structured* compensation (Ashby
   `summaryComponents`) is authoritative when present, then Claude (if enabled), then the
   context-aware regex over the description.
6. **Recency** — drop if older than `recency_days` when a date is present. The
   cutoff tests a **freshness** date (last-updated) when the source provides one,
   not first-publish: a live ATS feed only returns currently-open roles, so an
   evergreen role first published months ago but updated recently still counts.
   `posted_date` (first-publish) is still stored for display. (Refinement over
   README §10 — see §9.)
7. **Per-company cap** — keep top `max_roles_per_company` by seniority; ties by posted date, then
   alphabetical (README §9.2 step 10). The cap runs **after** the detail fetch and detail-derived
   filters (recency, employment): the pipeline ranks a candidate pool, fetches detail, applies the
   final filters, and keeps the first `max_roles` survivors — so a stale/contract role can't occupy
   a slot and then be silently dropped.
8. **Dedup** — README §15 (URL, or company + normalised title + first 120 chars + location).

**Claude API only for the fuzzy steps** (README §21.4, §22): title classification, salary
extraction from free text, description summarisation, requirement parsing. **Always** fall back
to regex/heuristics on API failure; cache successful extractions; validate every response against
its JSON schema before use. All navigation/filtering/ranking stays hardcoded.

---

## 8. Run lifecycle & diff

Per run (`python main.py seek`):

1. Load configs; build the active company list (respect `active`, `max_companies`).
2. Load prior state by scanning existing `jobs/**/*.md` frontmatter into memory.
3. For each company: ladder-fetch listing → filter/rank → detail-fetch kept roles → parse.
4. **Reconcile against prior state:**
   - new `id` ⇒ create MD, `status: open`, `first_seen = last_seen = today`. If the `id` misses
     but the **canonical URL** matches an existing record (old location-derived id → new URL-only
     id), treat it as the same role: carry over `first_seen`/notes/`applied`, rename the file (#2).
   - seen again ⇒ update `last_seen`, `last_checked`; refresh scraper-managed fields; preserve
     user-owned fields (§6.3).
   - **missing this run** ⇒ apply README lifecycle: missing for **N=2** consecutive runs ⇒
     `suspected_filled`; missing the next run ⇒ `closed`. (Track a `missing_runs` counter in
     frontmatter; never auto-close a `status: applied` role.) **Only postings of companies that
     were authoritatively checked this run are aged** — a partial run (`--only`/`--limit`, runtime
     budget, blocked/error) passes `processed_slugs` so it never ages companies it didn't look at (#1).
5. Regenerate `data/jobs.jsonl` from all MD frontmatter.
6. Write `data/runs/<ts>/diff.jsonl` with `{change: added|updated|reopened|suspected_filled|closed,
   id, …}`. An `updated` row is emitted only when a *content* field actually changed between runs
   (title, locations, salary, employment, comp type, posted date, URL, source — not lifecycle
   bookkeeping like `last_seen`), and carries a `changes: {field: [old, new]}` map (#7).
7. Print + write `data/runs/<ts>/summary.txt`: companies processed, roles added/updated/closed,
   failures, blocked, elapsed vs budget, list of failed URLs (README §16).

---

## 9. Divergence from README

The README predates the local-first storage decision. This spec **overrides** it on storage and
fetching; it **inherits** all domain rules unchanged.

| Topic | README | This spec |
| --- | --- | --- |
| Primary store | Versioned **XLSX** tables | **MD-per-role (canonical) + `jobs.jsonl` index** |
| Diff format | XLSX/CSV | **JSONL** under `data/runs/<ts>/` |
| Fetching | requests + BeautifulSoup | **ATS-API → Playwright → static HTML** ladder |
| Modes built now | Exploratory + Job Seek | **Job Seek only** this iteration |
| XLSX output | Core output | Deferred — optional *export* derived from the index later |
| Recency basis | `posted_date` only | **freshness (last-updated) when available**, else posted_date (§7.6) |

Everything in README §6 (fields), §11 (titles/ranking), §12 (location), §13 (salary), §14
(confidence), §15 (dedup), §16 (errors), §17 (ethics) applies as written.

---

## 10. Folder layout

```
job-search-assistant/
├── config/
│   ├── companies.csv
│   ├── search_profile.yaml
│   ├── settings.yaml
│   └── overrides/<slug>.yaml
├── data/
│   ├── jobs.jsonl                 # derived index
│   └── runs/<ts>/{diff.jsonl,summary.txt}
├── jobs/<company-slug>/<role-slug>--<id>.md   # canonical
├── models/                        # JobPosting dataclass
├── scrapers/
│   ├── ladder.py                  # orchestrates rungs 1–3
│   ├── ats/{greenhouse,lever,ashby,workday,smartrecruiters}.py
│   ├── playwright_scraper.py
│   ├── static_scraper.py
│   └── rate_limiter.py
├── services/
│   ├── title_normalizer.py        # README §11 (hardcoded)
│   ├── location_filter.py         # README §12 (hardcoded)
│   ├── salary_parser.py           # regex first, Claude fallback
│   ├── claude_service.py          # fuzzy parsing only, schema-validated
│   └── reconciler.py              # §8 lifecycle + diff
├── outputs/
│   ├── md_writer.py               # canonical MD read/write, preserves user fields
│   ├── index_builder.py           # regenerates jobs.jsonl from MD
│   └── summary.py
├── main.py                        # Click CLI: `seek`
└── requirements.txt
```

Stack: Python 3.12+, `click`, `pyyaml`, `requests`, `beautifulsoup4`, `playwright`,
`anthropic`, `python-dateutil`, `pandas` (index reads only).

---

## 11. First milestone (definition of done)

`python main.py seek` runs end-to-end over 2–3 seed companies (≥1 ATS-API, ≥1 Playwright) and:

- creates correct `jobs/<slug>/*.md` with valid frontmatter,
- regenerates `data/jobs.jsonl`,
- on a second run, correctly reports added/updated and advances lifecycle for a removed posting,
- preserves a hand-edited `## My notes` and a manual `status: applied` across runs,
- writes a readable `summary.txt`.

No scheduler, no notifications, no XLSX. Those come only after this is solid.

---

## 13. Scheduling & notifications

The one-shot is driven on a schedule by the OS (no long-running Python loop):

- `scripts/run_seek.sh` — wrapper: resolves the repo, runs `seek` with the venv, logs to
  `data/runs/cron.log`.
- `scripts/com.jobsearch.seek.plist` — macOS launchd agent (daily 08:00). Load with
  `cp … ~/Library/LaunchAgents/ && launchctl load …`. Linux: a cron line (see `scripts/README.md`).

**Notifications** (`outputs/notify.py`): after a run, if `notify.enabled` and the diff contains
`added`/`reopened` rows, push a message listing the new roles. Never fires for routine
updates/closures; never fails the run (wrapped). Configure under `notify:` in
`config/settings.yaml`. The send is injectable, so providers are unit-tested without network.
Providers:
- **ntfy** (`https://ntfy.sh/<topic>` — zero setup, install the app, subscribe to the topic):
  plain-text body.
- **slack** — Incoming Webhook (`notify.slack_webhook`, or `$SLACK_WEBHOOK_URL` if blank).
  Sends a Block Kit message where **each role title deep-links to its web-app detail page**
  (`web_base_url/jobs/<id>`, from `settings.web_base_url` or `$WEB_BASE_URL`) so you can open
  it in the tracker from your phone, with an "apply ↗" link to the external posting. Falls
  back to linking the external posting when no `web_base_url` is set. The scheduler/scraper
  container is the one that fires these (it runs `seek`), so the webhook + base URL are set on
  that service (see `docker-compose.yml`).

---

## 14. Exploratory mode (company enrichment)

`python main.py enrich [--only --limit]` builds the Company Index. For each company it
ladder-fetches the listing and derives, **public-HTML-only**:

- **Description** — the "About <company>" blurb embedded in a job posting (Greenhouse/Ashby/Lever
  ship descriptions); or a Claude 1–2 sentence summary when `use_claude` is on.
- **HQ** — the most common posting city (an *approximation*, flagged in `notes`).
- **Industry / funding / revenue / employees / founded** — only when `use_claude` parses the
  About text; otherwise left blank with `DataConfidence: Low` (no paid APIs, README §14).

Storage mirrors jobs: `companies/<slug>.md` is canonical (note-preserving via the same renderer),
`data/company_index.jsonl` is the derived index. Workday/SmartRecruiters/Talemetry boards ship no
listing descriptions → those land `Low` confidence. Verified live: 30 companies, 25 Medium / 5 Low
with heuristics only (Claude off).

---

## 12. How to run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium        # for Playwright/Talemetry rungs

.venv/bin/python main.py seek                # all active companies
.venv/bin/python main.py seek --only natwest # one company by slug
.venv/bin/python main.py seek --limit 1      # first N active companies
```

Outputs: `jobs/<slug>/*.md` (canonical), `data/jobs.jsonl` (index),
`data/runs/<ts>/{diff.jsonl,summary.txt}`.

**Tests** (network-free, cover the deterministic core):
```bash
.venv/bin/python -m pytest tests/ -q     # 85 tests: title, salary, location, ID, MD, reconciler
```
The suite drove fixes to title ranking (#6: Principal-before-Group; added VP-of/
Director-Product-Management/Head-comma variants; `'hr'` no longer substring-matches
"Threat"), `Remote (UK)` now honours `allow_remote: false`, and salary context
scoring (a "pension"/"budget" mention penalises rather than vetoes, so an explicit
"Salary:" still wins).

**Verified live (2026-06-27):** full batch of **30 companies in ~85s, 0 errors,
0 blocked, 19 London/UK senior-PM roles** found across 6 ATS platforms
(Greenhouse, Ashby, Lever, SmartRecruiters, Workday, Talemetry+Cloudflare).
Hits: Wise 9, Monzo 4, Cohere 2, Mimica 2, Harvey 1, Capsa 1. Salary parsed
context-aware (rejects "learning budget £1,000", age "16-17"); US-remote roles
(e.g. "San Francisco; Remote") correctly rejected; Wise "London / United Kingdom"
collapsed to one row; lifecycle (open→suspected_filled→closed) and
notes/`applied` preservation confirmed. NatWest returns 0 — genuinely no senior
PM roles open. Workday paginates 25 pages max (logged); raise `ats_max_pages` for more.

**Still needs work:** Google (custom careers API), Tessl (no public ATS API found),
Kraken/Octopus (Lever slug returns 0 — needs correct slug). Marked `active=false`
in `companies.csv`.
```

