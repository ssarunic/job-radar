# Recruitee adapter

> **Status:** proposed → building. Adds a 9th ATS adapter for **Recruitee**
> (`{slug}.recruitee.com`, often on a custom domain like `careers.hostaway.com`).
> Simplest adapter class — one JSON call, descriptions inline. Defers to
> `constitution.md §2` (public JSON the browser already calls).

## Why

Hostaway (`https://careers.hostaway.com/o/...`) is Recruitee — not among the 8
adapters, so today it can't be fetched. Recruitee is common for EU/remote startups.

## The API (verified against Hostaway)

Public, no auth: `GET https://{slug}.recruitee.com/api/offers/` → `{"offers": [...]}`.
Each offer carries everything inline — **no detail call needed**:
`{id, title, slug, careers_url, location, city, country, remote, hybrid, on_site,
description (HTML), requirements (HTML), employment_type_code, published_at,
created_at, department, status}`.

## Adapter (`scrapers/ats/recruitee.py`)

A dedicated **`RecruiteeFetcher`** class (its own rung, like Workday/Oracle — *not* an
`_API_MODULES` module, because it derives the API base from the careers URL rather than
an ATS slug). Custom domains **proxy** `/api/offers/`, so the fetcher hits
**`{careers_origin}/api/offers/`** — no tenant-slug resolution. Inline descriptions ⇒
`needs_detail = False`. Per offer:

- **description** = markdownified `description` + `## Requirements` from `requirements`.
- **location** — Recruitee's `location` is often the generic "Remote job"; compose a
  filter-friendly string: `Remote — {country}` when `remote`, else `city, country`.
  This lets `location_filter` accept UK/EU-eligible remote and reject US-only remote.
- **employment_type** — map `employment_type_code` (`fulltime_permanent → Full time`,
  `parttime* → Part time`, `contract`/`temporary`/`internship`/`freelance → Contract`)
  so the Contract exclusion works.
- **salary** — Recruitee's `salary` is a **dict** `{min,max,period,currency}` (often all
  null), *not* a string; coerced to text via `_salary_text` so the salary parser never
  gets a dict.
- **posted_date** = `published_at` or `created_at`. **url** = `careers_url`.
- Skip offers whose `status` is set and not `published`.

## Detection & discovery

- **Direct** `{slug}.recruitee.com`: `detect_ats` marker + `discovery._from_url`.
- **Custom domains** (`careers.hostaway.com`): the host has no `recruitee` marker, but the
  page **body does** — `detect_ats` / `discovery` body-probe for it (like Talemetry). **No
  tenant-slug resolution** is needed (the slug isn't even on custom-domain pages — only a
  `careers-analytics` tracking subdomain); the fetcher uses the careers-URL origin, and the
  discovered name is the domain's SLD (`careers.hostaway.com` → "Hostaway"). Name-probe
  can't find Recruitee — add via the careers URL.

## Wiring

- `scrapers/ladder.py`: import `RecruiteeFetcher`; add `("recruitee", "recruitee")` to
  `detect_ats` markers; add an `if ats == "recruitee": [(True, RecruiteeFetcher), …]` rung
  (**not** `_API_MODULES` — it's a class fetcher).
- `services/discovery.py`: `_from_url` recruitee branches (direct host + custom-domain
  body-probe → `mk("recruitee", "", careers=url)`, SLD-derived name).

## Tests

`tests/test_recruitee.py`, network-free: `fetch_listing` maps fields, composes
remote/city locations, maps employment codes, drops non-published, builds the
Requirements section; discovery extracts the tenant slug from a custom-domain body.
