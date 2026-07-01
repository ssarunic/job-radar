# Oracle Recruiting Cloud (ORC) adapter

> **Status:** proposed → building. Adds an 8th ATS adapter for **Oracle Fusion HCM
> "Candidate Experience"** (`*.fa.*.oraclecloud.com/hcmUI/CandidateExperience/...`),
> used by large enterprises (e.g. JP Morgan). Defers to `constitution.md §2` (public
> JSON the browser already calls) and mirrors the Workday adapter's shape.

## Why

The scraping ladder supports 7 ATS (Greenhouse, Ashby, Lever, SmartRecruiters,
Workday, Talemetry, RevolutPeople) — **not Oracle**. JP Morgan's careers site
(`https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs`)
is Oracle ORC, so today `follow` can't detect it and nothing can fetch it.

## The API (verified against JPMC)

Oracle CE is a JS SPA backed by a **public REST endpoint** the page itself calls
(no auth). Two resources under `https://{host}/hcmRestApi/resources/latest/`:

- **List:** `recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={SITE},limit=100,offset=N,sortBy=POSTING_DATES_DESC`
  → `items[0].requisitionList[]` of `{Id, Title, PrimaryLocation, PrimaryLocationCountry, PostedDate, ShortDescriptionStr, JobSchedule, JobType, ...}`; `items[0].TotalJobsCount` for paging. `{host}` and `{SITE}` (`CX_1001`) come from the careers URL.
- **Detail:** `recruitingCEJobRequisitionDetails?onlyData=true&expand=all&finder=ById;Id="{Id}",siteNumber={SITE}`
  → `ExternalDescriptionStr` (full HTML body).
- **Public posting URL:** `https://{host}/hcmUI/CandidateExperience/en/sites/{SITE}/job/{Id}`.

## UK location facet (the volume fix)

JPMC has **7005** open reqs globally. The list call returns a flat
`items[0].locationsFacet` of `{Name, Id}` nodes including a **country-level
`United Kingdom`** (id `300000000289276`) alongside city nodes (`LONDON, United
Kingdom` → 527). Mirroring the Workday adapter: one cheap `facetsList=LOCATIONS`
call, pick the UK facet **preferring the country-level node**, then constrain the
search with `selectedLocationsFacet={id}`. This collapses 7005 → UK-only before the
classifier applies the precise senior-PM + London/UK + recency filtering. Falls back
to unconstrained paging if no UK facet exists (small tenants).

## Adapter shape (`scrapers/ats/oracle.py`, mirrors `workday.py`)

`OracleFetcher` — `needs_detail = True`, `rung_name = "oracle"`, `check_robots = False`
(documented JSON API). `__init__` parses `host` + `SITE` (`/sites/([^/]+)/`) from the
careers URL. `listing()` discovers the UK facet then pages `requisitionList` into the
standard posting dict (`title/location/url/posted_date/description/employment_type/...`).
`detail(url)` pulls the `Id` from `/job/{Id}` and returns the markdownified
`ExternalDescriptionStr` with an employment/date/location header (so the generic
parsers pick them up). Same two-stage (list → detail-for-survivors) contract as the
others.

## Wiring

- `scrapers/ladder.py`: add `("oraclecloud", "oracle")` to `detect_ats` markers and an
  `if ats == "oracle": [(True, OracleFetcher), playwright, static]` rung in `_build_rungs`.
- `services/discovery.py`: `_from_url` gains an `oraclecloud` host branch (name derived
  from the tenant subdomain; the user renames on `follow`/web-add). **Name-probe can't
  find Oracle** (it's tenant-URL-specific, like Workday/Talemetry) — add via the careers URL.

## Limitations

- Employment-type: Oracle exposes `JobSchedule`/`JobType`/`ContractType`; the adapter
  passes `JobSchedule` and embeds the others in the detail body so the body-scan catches
  Contract/Part-time. Some tenants under-populate these.
- `siteNumber` and host are tenant-specific and read from the careers URL — a wrong
  `CX_####` yields an empty list, not an error.

## Tests

`tests/test_oracle.py`, network-free: a fake `http` returning canned facet/list/detail
JSON asserts (a) UK country facet is picked over city, (b) requisitions map to the
posting dict + public URL, (c) pagination stops at `TotalJobsCount`, (d) `detail()`
extracts the Id and markdownifies the body.
