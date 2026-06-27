---
name: job-tracker
description: Track target companies and their senior PM roles via the job-search CLI. Use when the user asks what companies they're tracking, to follow/start tracking or unfollow/stop tracking a company, what open roles there are, or what's new since yesterday / since they last checked. Trigger on "what companies am I tracking", "follow <company>", "unfollow <company>", "what are the open roles", "any new roles", "what's new since last time".
---

# Job Tracker

This repo is a CLI that scrapes target companies' careers pages for senior Product
Manager roles. Drive it by running the CLI with the project's virtualenv. Always run
from the repo root using `.venv/bin/python main.py <command>`.

Relay the command output to the user in plain language — summarise, don't dump raw rows
unless they ask for detail. Quote the role title, company, location, and the job URL.

## Command mapping

| User intent | Command |
| --- | --- |
| "what companies am I tracking" | `.venv/bin/python main.py companies` |
| "follow / track <name or careers URL>" | `.venv/bin/python main.py follow "<name-or-url>"` |
| "unfollow / stop tracking <company>" | `.venv/bin/python main.py unfollow <slug>` |
| "what are the open roles" | `.venv/bin/python main.py roles` |
| "open roles at <company> / senior ones" | `.venv/bin/python main.py roles --company <name> --min-rank 5` |
| "what's new since last time" | `.venv/bin/python main.py new` |
| "what's new since <date>" | `.venv/bin/python main.py new --since YYYY-MM-DD` |
| "go fetch the latest roles now" | `.venv/bin/python main.py seek` (or `--only <slug>`) |

## Notes

- **follow** auto-detects the ATS (Greenhouse/Ashby/Lever/SmartRecruiters) from a company
  name. For Workday pass the careers URL. **Cloudflare-protected sites (e.g. NatWest/Talemetry)
  can't be detected from a URL** — `follow` records them as `custom`; tell the user to set
  `ats_type` (e.g. `talemetry`) in `config/companies.csv` afterwards. After following, offer to
  run `seek --only <slug>` to fetch that company's roles.
- **unfollow** takes the company *slug* (shown by `companies`), not the display name. If the
  user gives a name, look up the slug from `companies` first.
- **new** advances a "last checked" marker each time it runs (no `--since`), so the next
  call shows only what appeared since. Use `--since` for an explicit window without moving
  the marker.
- **roles**/**new** read the local index (`data/jobs.jsonl`); they don't hit the network.
  Only `seek` scrapes. If the user wants fresh data first, run `seek` then the query.
- Seniority ranks: CPO 9, VP 8, Director 7, Head 6, Principal 5, Group 4, Senior 3. So
  "senior leadership roles" ≈ `--min-rank 6`.
