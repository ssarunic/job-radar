# cvMail adapter

> **Status:** ✅ built. Adds a 10th ATS adapter for **cvMail** (Thomson Reuters'
> legal-sector ATS — `fsr.cvmailuk.com/<firm>/`), used by most large UK law firms.
> First **HTML-scraping** ATS rung (no JSON API exists); robots-checked per
> `constitution.md §2` (HTML rungs honour robots.txt).

## Why

Mishcon de Reya (`fsr.cvmailuk.com/mishcon/…`) is cvMail — not among the 9 adapters,
so today it resolves to `custom` and can't be followed. cvMail is the standard board
for UK legal (Mishcon, and the same `fsr.cvmailuk.com/<firm>/` pattern serves many
firms), which increasingly post senior product/AI roles.

## The site (verified against Mishcon, 2026-07-07)

Old-school server-rendered ColdFusion (`main.cfm`, `cfid`/`cftoken` session cookies,
AWS ALB). **No JSON API** — everything is HTML:

- **Board**: `GET /{firm}/main.cfm?page=jobBoard` → a table of up to 50 rows.
  Header cells `td.jbTableHeaderCaptionStyle` name the columns (firm-configurable —
  Mishcon shows Job Title / Department / Location). Each row (`tr.odd` / `tr.even`)
  has `td.jbTableTextStyle` cells; the title cell wraps
  `a.jobMoreDetailCaptionStyle[href*="jobSpecific"]` with the job link
  (`main.cfm?page=jobSpecific&jobId=NNN&rcd=…`, entity-escaped).
- **Pagination**: >50 jobs paginate via the `paging` **form POST** (fields
  `jump_to`, `start_row`, a per-render `x-token`, and the `next_page` submit;
  `select[name=jump_page]` lists the pages). GET params do **not** paginate —
  the token + session cookie are required, so the fetcher re-parses the form from
  each page and POSTs `jump_to=N` through the shared session.
- **Detail**: `page=jobSpecific&jobId=NNN` → label/value rows —
  `td.jobFieldStyle` (label: Job Title, Location, Description, sometimes
  Closing Date/Duration/Salary — firm-configurable) paired with `td.jobValueStyle`
  (value). The Description value cell contains embedded HTML (sometimes with a
  nested `<!DOCTYPE>`).
- **Volatile `rcd` param**: job links carry an `rcd` that changes per render.
  Job URLs are **normalised to `page=jobSpecific&jobId=NNN` only** (verified to
  load without `rcd`) so `JobAdURL` is stable across runs — otherwise URL-based
  dedup/lifecycle would churn every run.
- **No posted date** anywhere ⇒ `posted_date=None`; the recency filter keeps
  unknown dates (product-spec §10).
- **robots.txt**: disallows a long list of *named* bots from `/`, but has **no
  `User-agent: *` group** — our `JobSeekAssistant` UA is not disallowed, so
  `HttpClient.allowed()` passes. The adapter still sets `check_robots=True`
  (HTML rung ⇒ robots-gated, unlike the JSON-API adapters).

## Adapter (`scrapers/ats/cvmail.py`)

A dedicated **`CvMailFetcher`** class rung (like Workday/Oracle/Recruitee):

- Derives the board URL from the company's careers URL: any
  `https://{host}/{firm}/…` cvMail link (deep job link included) →
  `https://{host}/{firm}/main.cfm?page=jobBoard`.
- `listing()`: GET the board, then walk pages (form POST, capped at 20). Rows map
  to `{title, location, url, posted_date=None, description="", source_type="ATS",
  source_detail="cvMail"}`. **Location** comes from the column whose header says
  "Location" (columns are firm-configurable); fallback = last text cell.
- `needs_detail=True`: `detail(url)` parses the label/value rows — Description →
  `html_to_markdown`; other fields except Job Title/Location (already captured)
  are prepended as `**Label:** value` lines so employment/salary/closing-date
  text reaches the downstream classifiers.
- Empty board (or a board page with no job rows) → `EMPTY`; the rung is
  terminal-on-empty like the other ATS rungs.

## Detection & discovery

- `detect_ats` marker: `("cvmail", "cvmail")` — URL host match covers
  `fsr.cvmailuk.com` (and sibling cvMail domains). No body-probe (cvMail boards
  are always on cvMail domains).
- `discovery._from_url`: any cvMail URL → firm = first path segment;
  `mk("cvmail", firm, careers=board_url)` with the firm segment title-cased as
  the name ("mishcon" → "Mishcon"). Name-probe can't find cvMail — add via URL.

## Wiring

- `scrapers/ladder.py`: import `CvMailFetcher`; marker; rung
  `[(True, CvMailFetcher), playwright, static]`.
- `services/discovery.py`: host branch in `_from_url`.
- `webapp/backend/mcp_app.py`: `follow_company` docstring lists the cvMail form.

## Tests

`tests/test_cvmail.py`, network-free against canned board/detail HTML: header-driven
location-column mapping, entity-escaped link normalisation (drops `rcd`, keeps
`jobId`), form-POST pagination (token + jump_to asserted), single-page boards,
detail markdown + extra-field prepending, `detect_ats`, and `discovery._from_url`
from a deep job link.
