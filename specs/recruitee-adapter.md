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

## Mapping (`scrapers/ats/recruitee.py`, mirrors `lever.py`)

A module with `fetch_listing(ats_slug, http)` (registered in `_API_MODULES`; inline
descriptions ⇒ no `NEEDS_DETAIL`):

- **description** = markdownified `description` + `## Requirements` from `requirements`.
- **location** — Recruitee's `location` is often the generic "Remote job"; compose a
  filter-friendly string: `Remote — {country}` when `remote`, else `city, country`.
  This lets `location_filter` accept UK/EU-eligible remote and reject US-only remote.
- **employment_type** — map `employment_type_code` (`fulltime_permanent → Full time`,
  `parttime* → Part time`, `contract`/`temporary`/`internship`/`freelance → Contract`)
  so the Contract exclusion works.
- **posted_date** = `published_at` or `created_at`. **url** = `careers_url`.
- Skip offers whose `status` is set and not `published`.

## Detection & discovery

- **Direct** `{slug}.recruitee.com`: `detect_ats` marker + `discovery._from_url`
  (`slug = host.split(".")[0]`).
- **Custom domains** (`careers.hostaway.com`): the host has no `recruitee` marker, but
  the page **body does** — `detect_ats` already body-probes (like Talemetry). The real
  Recruitee tenant slug isn't in the custom URL, so `discovery._from_url` fetches the
  page and extracts it via `([a-z0-9-]+)\.recruitee\.com` → sets `ats_slug`. (Name-probe
  can't find Recruitee; add via the careers URL.)

## Wiring

- `scrapers/ladder.py`: import + add `recruitee` to `_API_MODULES`; add
  `("recruitee", "recruitee")` to `detect_ats` markers.
- `services/discovery.py`: `_from_url` recruitee branches (direct host + body-extract).

## Tests

`tests/test_recruitee.py`, network-free: `fetch_listing` maps fields, composes
remote/city locations, maps employment codes, drops non-published, builds the
Requirements section; discovery extracts the tenant slug from a custom-domain body.
