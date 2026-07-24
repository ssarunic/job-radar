# JobRadar

**A private, self-hosted radar for your job search.** Follow the companies you
care about, and JobRadar checks their careers pages every morning, tracks every
matching role over time (new → open → suspected filled → closed), and pings you
on Slack when something worth seeing appears — deep-linked into your own web
dashboard.

Built for one person's search for senior Product Management roles; designed so
you can point it at *your* roles, *your* city, *your* companies.

## How it works

- **You follow companies** — paste a careers-page URL into the web UI; JobRadar
  auto-detects the ATS (Greenhouse, Ashby, Lever, SmartRecruiters, Workday,
  Oracle, Recruitee, RevolutPeople, Talemetry, cvMail) and scrapes politely
  (public data only, rate-limited, robots.txt honoured — see
  [`specs/constitution.md`](specs/constitution.md)).
- **A daily scan** filters roles by title, seniority, and location, ranks them,
  and records every change. Nothing is ever silently lost — each posting has a
  lifecycle you can audit.
- **Everything is yours** — a single-user tool with a local Markdown + JSONL
  store, no accounts, no third-party services beyond the optional Slack webhook
  and optional Claude API for fuzzy parsing.
- **Talks to Claude** — an optional [MCP server](docs/claude-mcp.md) lets Claude
  query your tracked roles, judge fit against your CV, and follow new companies
  for you.

## Quick start

```bash
git clone https://github.com/ssarunic/job-radar && cd job-radar
cp .env.example .env                        # add your Slack webhook (optional)
docker compose --profile scheduler up -d    # web UI + daily 08:00 scan
open http://localhost:8765                  # follow your first companies from the UI
```

That's it — omit `--profile scheduler` if you only want the web UI and the
manual "↻ Refresh" button; the scheduler service is what runs the daily scan
and sends Slack notifications. To tune *what* you're searching for (roles, seniority
floor, location), edit `config/search_profile.yaml` — every field is explained
in the [configuration guide](docs/configuration.md).

## Documentation

**Using JobRadar** (no development experience needed):

- [Getting started](docs/getting-started.md) — install & first run
- [Daily use](docs/using.md) — following companies, reading the list, statuses
- [Configuration](docs/configuration.md) — the search profile, `.env`, advanced overrides
- [FAQ](docs/faq.md) — "why isn't job X showing?" and friends
- [Claude / MCP](docs/claude-mcp.md) — connect Claude to your JobRadar

**Developing & self-hosting** (for forks and contributions to your own copy):

- [`specs/README.md`](specs/README.md) — the dev-docs index: architecture,
  storage, the scraping ladder, ATS adapters, deployment
- [`CLAUDE.md`](CLAUDE.md) — working-agreement for AI coding agents in this repo

## Status

Personal project, actively used and maintained. Forks welcome; this repo does
not accept external contributions.
