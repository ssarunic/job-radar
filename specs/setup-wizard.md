# Settings page & first-run setup

> **Status:** ✅ implemented. Web-first way to see and change the search
> rules without editing YAML (generalization phase 3; phases 1–2 made the
> data forkable and the profile fields generic). Began as a first-run wizard
> (`/setup`); it is now a permanent **Settings** page that the wizard reuses.

## Surface

- **`GET /api/profile`** → `{profile, companies_followed, location}`. The
  profile is `loader.load_profile()` verbatim; `companies_followed` counts
  active registry rows (the frontend's first-run signal); `location` is the
  editable geography *as it applies* — the profile's value, else the default
  from `location_filter.editable_terms` — so the page never carries its own
  copy of the defaults.
- **`PUT /api/profile`** — merges a constrained subset into
  `search_profile.yaml`: `search_label`, `seniority_min` (1–9),
  `include_product_owner`, `include_ai_innovation`, `allow_remote`,
  `exclude_titles`, `employment` (non-empty subset of Full time / Part time /
  Contract), `workplace` (non-empty subset of On site / Hybrid / Remote —
  also sets `allow_remote` to match, so the two never disagree), and the `location` block keys (`home_city`, `home_terms`
  — at least one, `remote_regions` — merged, not replaced). Writes via
  `store.atomic_write_text`. Comments in the shipped YAML are not preserved
  once the page saves (machine-written thereafter) — accepted trade-off,
  fields are documented in `docs/configuration.md`. Advanced fields
  (`custom_patterns`, operational knobs) are deliberately
  **not** writable here.
- **`/settings` page** (`webapp/frontend/src/pages/Settings.tsx`, in the
  nav) — **read-only by default**: Roles, Locations and Companies cards show
  the rules in force, including the file-only ones (per-company cap,
  age limit) and a link to the Companies page. **Edit**
  swaps the cards for a form; **Save** returns to the view, **Cancel**
  discards. The rules drive the daily scan, so a change is always a
  deliberate Edit → Save.
- **Save sends only changed fields.** Untouched fields keep following the
  built-in defaults (nothing is frozen into the file), an unchanged form
  writes nothing (comments survive), and a term the user didn't retype keeps
  its stored form — some defaults carry significant whitespace (`"eu "`).
- With `custom_patterns` set, the Product Owner / AI-Innovation toggles don't
  apply (see `title_normalizer`), so the page hides them and says the custom
  pack is in force.
- **`/setup`** — the same page with `firstRun`: opens straight in the form,
  no Cancel, and saving navigates to `/companies`. Linked from the
  **first-run banners** on the Roles and Companies pages when nothing is
  followed yet.

## Non-goals

- No auth (single-user tool; same trust model as follow/unfollow).
- No Slack-webhook entry — that's an env var the container can't persist;
  `docs/getting-started.md` covers it.
- No re-filtering of already-stored roles on save — changes apply from the
  next scan.
- Public GHCR image + one-click cloud deploy template: deferred until the
  repo goes public.

## Tests

`webapp/backend/tests/test_api.py` — GET shape, effective-location fallback,
merge + persistence across requests, partial location merge, role toggles,
validation (rank bounds, empty terms, empty `home_terms`).
Frontend covered by eslint + build (no component-test infra in this repo).
