# RevolutPeople adapter

> **Status:** ✅ implemented (retrospective spec). ATS adapter for **RevolutPeople**
> (`revolutpeople.com`), Revolut's white-label hiring platform — used by e.g. Cleo.
> Deferred to `constitution.md §2` (public JSON the browser already calls).

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

## Wiring

- `scrapers/ladder.py`: `("revolutpeople", "revolutpeople")` in `detect_ats` markers; a
  dedicated `if ats == "revolutpeople": [(True, RevolutPeopleFetcher), …]` rung (a class
  fetcher, not an `_API_MODULES` module).
- Add by careers URL / `ats_type: revolutpeople` (`discovery` doesn't slug-probe it).

## Tests

`tests/test_revolut_people.py` — network-free: pagination, location composition
(structured `locations[]` incl. remote), posting mapping + public URL, v2 detail fetch.
