# Workable adapter

> **Status:** built. Adds an 11th ATS adapter for **Workable**
> (`apply.workable.com/{slug}/`, aliased from `{slug}.workable.com`). A slug-based
> JSON-API adapter in the Greenhouse/Ashby/Lever family, with a SmartRecruiters-style
> per-posting detail call. Defers to `constitution.md §2` (public JSON the browser
> already calls).

## Why

CloudTalk (`https://apply.workable.com/cloudtalk/j/4BE1A55963` — Director of Product,
remote in Europe incl. the UK) is on Workable, which none of the ten adapters covered.
Without it a follow falls through to the Playwright/static discovery rungs, which
are unreliable on Workable's JavaScript board **and** apply the 45-day recency
cutoff — so a still-open role ages out mid-tracking. Workable is common among
European scale-ups.

## The API (verified against CloudTalk and Blueground, 2026-09-08)

Public, no auth, no Cloudflare. Both are the XHRs the board page itself makes.

**Listing** — `POST https://apply.workable.com/api/v3/accounts/{slug}/jobs` with body
`{"query":"","location":[],"department":[],"worktype":[],"remote":[]}` →
`{"total": N, "results": [...], "nextPage": "<token>"?}`. Ten results per page;
send the body key `token` = `nextPage` to continue. The API keeps issuing a token
after the last page, so stop on **any** of: no `nextPage`, empty `results`, or
`len(collected) >= total`, plus a 50-page hard cap. Unknown slugs 404; some dormant
accounts 200 with `total: 0`.

Each result: `{id, shortcode, title, remote, workplace ("remote"|"hybrid"|"on_site"),
location {country, countryCode, city, region}, locations [same shape, one per
eligible country/city], state ("published"), isInternal, published (ISO), department[]}`.
No description, no employment type.

**Detail** — `GET https://apply.workable.com/api/v2/accounts/{slug}/jobs/{shortcode}`
→ the listing fields plus `description`, `requirements`, `benefits` (HTML).

**Job URL** — `https://apply.workable.com/{slug}/j/{shortcode}/` (the public posting;
what the user is deep-linked to and what dedup keys on).

## Adapter (`scrapers/ats/workable.py`)

A module in `ladder._API_MODULES` (slug-keyed, like SmartRecruiters), so the generic
`_ApiFetcher` wraps it: `live_listing=True` (recency-exempt), `check_robots=False`
(documented ATS API), `NEEDS_DETAIL=True`.

- **fetch_listing(slug, http)** — pages the v3 endpoint; skips `state != published`
  and `isInternal`. Emits `title`, `url`, `posted_date`/`freshness_date` =
  `published`, empty `description`/`employment_type`/`salary_text`,
  `source_detail = "Workable"`.
- **location** — one label per `locations[]` entry as `city, region, country`
  (falling back to the primary `location`), prefixed `Remote — ` for remote roles.
  So CloudTalk's Director becomes `Remote — Spain; Remote — Czechia; Remote — United
  Kingdom; …`, and `location_filter.expand` judges each country on its own terms:
  the UK label is home, Spain/Ireland/Netherlands are eligible-region remote, and
  the >5 rule trims the rest. A remote role with no countries is a bare `Remote`.
- **fetch_detail(url, http)** — parses `{slug}` and `{shortcode}` from the job URL,
  fetches v2, returns Markdown: description + `## Requirements` + `## Benefits`
  (labelled so requirements extraction finds the section). Only called for roles
  that already passed title + location, so it costs a handful of requests.
- **employment_type** stays empty — the public API doesn't expose it, so the
  Contract exclusion can't fire for Workable; the title classifier and description
  are the guard.

## Detection / discovery

- `ladder.detect_ats`: marker `workable.com` (URL host or page body — the bare word
  "workable" is too common to body-probe on).
- `discovery._from_url`: `apply.workable.com/{slug}/…` → slug from the first path
  segment; `{slug}.workable.com` → slug from the subdomain. `careers_url` is
  normalised to `https://apply.workable.com/{slug}/`.
- `discovery._probe` (follow by name): POSTs the v3 listing **last** in the probe
  order and requires `total > 0`, mirroring the SmartRecruiters guard.

## Tests

`tests/test_workable.py` — network-free against a canned `post_json`/`get_json`
client: field mapping, unlisted/internal skipping, location composition (remote
multi-country, on-site city, fallback to primary), paging via `token` with the
stop-at-total guard, empty-page stop, job-URL parsing, detail composition, ladder
registration (`_build_rungs` → `_ApiFetcher`, OK/EMPTY), `detect_ats` by URL and
body, and URL discovery for both host forms. `tests/test_discovery.py` covers the
name probe and the `total: 0` rejection.

## Non-goals

- Salary: Workable postings carry no structured comp; the salary parser runs on the
  detail Markdown as for any other adapter.
- Workable's older widget API (`www.workable.com/api/accounts/{slug}`) — it
  redirects to HTML now; not used.
- Hosted-domain boards (`careers.example.com` proxying Workable) — only detected
  when the page body embeds an `apply.workable.com` link.
