# Web App — Outcomes

> **Layer:** Outcomes (the *what* and *why*). Governed by [`../constitution.md`](../constitution.md).
> **Status:** proposed.

## Who & why
**Who:** the single job-seeker (you).
**Problem today:** roles live as Markdown files and fly past as Slack/ntfy pings.
There's no single place to *see what's open right now*, drill into a role, and track
where you are with it — and a notification can't take you straight to the role.

**One-line goal:** a private web app to browse current & past roles, drill into the
full ad, manage your application state, and have notifications **deep-link straight to
a role's page** on your phone (over Tailscale).

## Outcomes (what must become true)
1. **See everything in one place.** A list of all roles — current *and* past — with
   filter by status/company/seniority/location and sort by seniority or recency.
2. **Drill into a role.** Full **Markdown-formatted** ad, salary, locations,
   employment, source, dates, status, and your notes — on one page, readable on mobile.
3. **Manage application state from the UI.** Edit notes and set status
   (Applied / Not interested) without touching files; it persists canonically and
   **survives the next scrape**.
4. **Notifications link to the role.** A Slack/ntfy message about a new role contains a
   link that opens *that role's* detail page on your phone via Tailscale.
5. **Understand companies & activity.** See enriched company info (with their open
   roles) and a feed of what changed each run (added/closed/updated).

## Acceptance criteria (how we'll know)
- From a Slack ping I tap a link and land on the correct role's detail page on my
  phone in a couple of seconds (Tailscale).
- I can mark a role **Applied** and add a note; after the next `seek`, both are still
  there and the role isn't re-added as new.
- The list clearly separates **Open** from **Past** (Suspected filled / Closed), and I
  can filter to "Director+ in London" in two clicks.
- A role detail renders headings, bullet lists, and bold from the ad (not flattened).
- Salary shows where the ATS provides it (e.g. Capsa £140–170k).
- The app is reachable only on my tailnet — never the public internet.

## Non-functional outcomes
- **Mobile-first detail page** (it's the Slack deep-link target).
- **Fast**: list renders in well under a second at our scale (tens–hundreds of roles).
- **No data duplication / no drift**: the app reads the canonical store and writes back
  through it; it is not a second source of truth.
- **Zero/again-near-zero running cost**; no public exposure; no new always-on paid infra.

## Out of scope (for this feature)
- Multi-user, real auth/SSO (a single shared token at most, only if exposed).
- Editing the tracked-company list or search profile from the UI (CLI/`follow` already
  does this; could come later).
- Analytics dashboards, fit-scoring, cover-letter drafting.
- Replacing the CLI or the scheduler — the web app is a **view + light write layer**,
  not the engine.
