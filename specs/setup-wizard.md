# First-run setup wizard

> **Status:** ✅ implemented. Web-first onboarding so a non-developer can
> configure their search without editing YAML (generalization phase 3;
> phases 1–2 made the data forkable and the profile fields generic).

## Surface

- **`GET /api/profile`** → `{profile, companies_followed}`. The profile is
  `loader.load_profile()` verbatim; `companies_followed` counts active
  registry rows (the frontend's first-run signal).
- **`PUT /api/profile`** — merges a constrained subset into
  `search_profile.yaml`: `search_label`, `seniority_min` (1–9),
  `allow_remote`, `exclude_titles`, and the `location` block keys
  (`home_city`, `home_terms`, `remote_regions` — merged, not replaced).
  Writes via `store.atomic_write_text`. Comments in the shipped YAML are not
  preserved once the wizard saves (machine-written thereafter) — accepted
  trade-off, fields are documented in `docs/configuration.md`.
  Advanced fields (`custom_patterns`, operational knobs) are deliberately
  **not** writable here.
- **`/setup` page** (`webapp/frontend/src/pages/Setup.tsx`) — four questions
  (label, seniority floor, home city/locations, remote regions), pre-filled
  from the current profile; saving navigates to `/companies`.
- **First-run banner** on the Companies page when zero companies are in the
  registry, linking to `/setup`.

## Non-goals

- No auth (single-user tool; same trust model as follow/unfollow).
- No Slack-webhook entry — that's an env var the container can't persist;
  `docs/getting-started.md` covers it.
- Public GHCR image + one-click cloud deploy template: deferred until the
  repo goes public.

## Tests

`webapp/backend/tests/test_api.py` — GET shape, merge + persistence across
requests, partial location merge, validation (rank bounds, empty terms).
Frontend covered by eslint + build (no component-test infra in this repo).
