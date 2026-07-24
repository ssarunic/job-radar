# RevolutPeople adapter

> **Status:** ✅ implemented (retrospective spec). ATS adapter for **RevolutPeople**
> (`revolutpeople.com`), Revolut's white-label hiring platform — used by e.g. Cleo.
> Deferred to `constitution.md §2` (public JSON the browser already calls).
> A **web variant** covers Revolut's own board at `www.revolut.com/careers` (below).

## The API (`scrapers/ats/revolut_people.py`)

Each company is a **tenant** in the path. Public JSON, no Cloudflare on the API itself:

- **List:** `GET https://revolutpeople.com/api/{tenant}/external/v3/postings?page=N`
  → `{pages, count, results:[{id, title, locations:[{name, type, country:{name}}], function}]}`.
  Listing-only (no description in the feed); paginates on `pages.total`.
- **Detail:** the v3 listing omits the body, so `detail()` calls the **v2** endpoint
  `…/api/{tenant}/external/v2/postings/{id}` → `description` (HTML → Markdown).
- **Public URL:** `https://revolutpeople.com/{tenant}/public/careers/position/{id}`.

## Adapter shape

`RevolutPeopleFetcher` — `needs_detail = True`, `rung_name = "revolutpeople"`,
`check_robots = False`. `tenant` = `company.ats_slug` or the first path segment of the
careers URL. `listing()` pages the v3 feed into the standard posting dict; **structured
`locations[]` feed the UK filter directly** (`_location` joins names, appending
"(remote)" for remote entries). `detail(url)` extracts the posting id and returns the
markdownified v2 description.

## Web variant — Revolut's own board (`RevolutWebFetcher`)

Revolut's own tenant **403s the public API** (both v2 and v3, from any client), so the
same file ships a second fetcher for `www.revolut.com/careers`:

- The careers pages are **Next.js SSG**: the listing page embeds all positions in
  `__NEXT_DATA__ → props.pageProps.positions` (`{id, text, locations, team}` — no
  description), and each position page embeds `pageProps.position` with the full
  HTML `description`.
- **Cloudflare is passive** — `curl_cffi` impersonation (`chrome`) clears it with no
  browser, same pattern as Talemetry.
- **robots.txt**: `Disallow: /*.json$` rules out the `/_next/data/…/careers.json`
  routes, so the adapter fetches only the allowed **HTML pages** and parses
  `__NEXT_DATA__` out of them (`check_robots = True`, on the careers URL).
- Location shape differs from the API: `country` is a plain string, not
  `{name}` — `_location` handles both.
- `rung_name = "revolutweb"`, `source_type = "CompanySite"`,
  `source_detail = "RevolutPeople"`; public URL
  `https://www.revolut.com/careers/position/{id}/`.

`make_fetcher(company, http)` picks the class by careers-URL host:
`revolutpeople.com` → API tenant fetcher, anything else (revolut.com) → web fetcher.

## Wiring

- `scrapers/ladder.py`: `("revolutpeople", "revolutpeople")` **and**
  `("revolut.com/careers", "revolutpeople")` in `detect_ats` markers; the
  `revolutpeople` rung calls `revolut_people.make_fetcher` (a class fetcher, not an
  `_API_MODULES` module).
- `services/discovery.py` recognises `revolutpeople.com/{tenant}/…` (tenant = first
  path segment) and `*.revolut.com/careers…` (→ `ats_slug: revolut`,
  name "Revolut") — both map to `ats_type: revolutpeople`, so `follow`/
  `follow_company` can add either board by URL.

## Tests

`tests/test_revolut_people.py` — network-free: pagination, location composition
(structured `locations[]` incl. remote + plain-string country), posting mapping +
public URL, v2 detail fetch; web variant: `make_fetcher` dispatch, `__NEXT_DATA__`
parsing, listing mapping, 403→blocked / non-200→error / no-positions→empty,
detail markdown + error paths. `tests/test_ladder.py` covers the rung dispatch;
`tests/test_discovery.py` the two URL patterns.
