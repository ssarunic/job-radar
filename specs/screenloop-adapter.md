# Screenloop adapter

> **Status:** built. Adds a 12th ATS adapter for **Screenloop**
> (`app.screenloop.com/careers/{slug}`). The second HTML-scraping ATS rung after
> cvMail: Screenloop has no public JSON API, but its server-rendered pages embed the
> React board's props as JSON, so a single GET carries the full listing. Defers to
> `constitution.md §2` (public careers page, robots-checked).

## Why

Homesearch (`https://app.screenloop.com/careers/homesearch/job_posts/8985` — Head of
Product, London hybrid) is on Screenloop, which none of the eleven adapters covered.
A follow fell through to the Playwright/static discovery rungs, which have no
selectors for the board and apply the 45-day recency cutoff, so the role could not
be tracked at all. Screenloop is a UK-centric ATS used by smaller scale-ups.

## The pages (verified against Homesearch, 2026-10-14)

Public, no auth, no Cloudflare, `robots.txt` has no disallow rules. The JS bundle
makes **no** data XHR: both pages are Rails views that mount a React component from
`<div data-react-class="…" data-react-props="{…}">`, with the props entity-escaped
JSON. The `/api/...` routes behind the app require a sign-in and are not used.

**Board** — `GET https://app.screenloop.com/careers/{slug}` →
component `applicant_tracking/Careers/CareersPage`, props
`{companyInfo {name, subdomain}, jobPosts [{id, name, location {name, city, state,
country, countryCode}, job {name, department {name}}}]}`. Only published posts are
listed. No dates, no bodies, no employment type. Unknown slugs 404.

**Job page** — `GET https://app.screenloop.com/careers/{slug}/job_posts/{id}` →
component `applicant_tracking/Jobs/JobPostPage`, props
`{previewJobPost {name, department, location, locationType ("Hybrid"|…),
employmentType ("Full time"|…), status, salary}, jobPostHtmlString (HTML body)}`.

**Job URL** — `https://app.screenloop.com/careers/{slug}/job_posts/{id}` (the public
posting; what the user is deep-linked to and what dedup keys on). The `?tab=overview`
query the site appends is dropped.

## Adapter (`scrapers/ats/screenloop.py`)

`ScreenloopFetcher`, a class rung like cvMail: `live_listing=True` (recency-exempt —
the board only lists open posts), `check_robots=True` (HTML scrape), `needs_detail=True`.
The slug comes from `ats_slug` or, failing that, from any Screenloop link in
`careers_url` (a pasted job link collapses to the board).

- **listing()** — one GET of the board; `parse_board` reads `jobPosts[]` and emits
  `title`, `url`, `location`, `posted_date=None`, empty `description` /
  `employment_type` / `salary_text`, `source_detail = "Screenloop"`.
- **location** — `city, country`, with the country short-named from `countryCode`
  (`GB` → `United Kingdom`; Screenloop stores the ISO long form "United Kingdom of
  Great Britain and Northern Ireland"). A post with no city uses the office label
  (`Head Office, United Kingdom`).
- **detail(url)** — one GET of the job page; `parse_job` returns Markdown prefixed
  with `Employment type:` and `Workplace type:` header lines (plus `Salary:` when the
  structured field is set), the Workday/Oracle/Talemetry convention, so
  `classify_employment` and `workplace_model` pick them up without a listing-level
  field. Only called for roles that already passed title + location.
- **posted_date** is `None` everywhere — Screenloop exposes no dates — so lifecycle
  (`Suspected Filled` → `Closed`) is driven purely by presence on the board.

## Detection / discovery

- `ladder.detect_ats`: marker `screenloop` (URL host or page body — the word is
  distinctive enough to body-probe on).
- `discovery._from_url`: `app.screenloop.com/careers/{slug}[/job_posts/N]` → slug from
  the second path segment; `careers_url` normalised to the board.
- `discovery._probe` (follow by name): GETs the board HTML **last** in the probe order,
  after every JSON API, and requires at least one listed post (an empty board does
  not claim the name).

## Tests

`tests/test_screenloop.py` — network-free against canned pages built the way the
live ones ship (entity-escaped JSON in `data-react-props`): URL/slug parsing, props
extraction (incl. malformed JSON), location composition, board field mapping, job
page header lines + Markdown body (+ salary line), fetcher listing/detail with a
deep-link `careers_url`, OK/EMPTY, ladder registration (terminal, robots-checked,
live), `detect_ats` by URL and body, URL discovery for all link forms, and the name
probe (incl. the empty-board rejection). `tests/test_discovery.py` covers the probe
order against the shared fake client.

## Non-goals

- Screenloop's signed-in `/api/...` routes — authenticated, out of policy.
- Pagination — the board props carry every post; no paging exists on the page.
- Custom-domain boards (`careers.example.com` proxying Screenloop) — only detected
  when the page body embeds an `app.screenloop.com` link.
