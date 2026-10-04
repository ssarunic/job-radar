# Configuration

The basics (what roles, seniority floor, excluded title words, location,
remote preference) are shown on the web UI's **Settings** page — press
**Edit** there to change them, no file editing needed. Everything below is
for going deeper. Note: once you save a change from the UI, the profile file
is rewritten without its explanatory comments (this page is the reference).

Three files control JobRadar. After the first run they live in the Docker
volume (the container copies defaults there on first boot); edit them there —
or before first boot, edit them in the repo's `config/` folder.

## `config/search_profile.yaml` — what you're looking for

```yaml
seniority_min: 3          # keep roles ranked at or above this
                          # 9 CPO · 8 VP · 7 Director · 6 Head · 5 Principal/Staff
                          # 4 Group/Lead · 3 Senior · 2 mid-level
include_product_owner: true    # also keep "Product Owner" titles (rank 2)
include_ai_innovation: true    # rank AI/Innovation leadership titles too

exclude_titles:           # drop any title containing these words
  - "marketing"
  - "graduate"            # entry-level programmes
  - "internship"

employment: ["Full time", "Part time"]   # add "Contract" to also keep fixed-term,
                                          # interim, temporary and freelance roles
workplace: ["On site", "Hybrid", "Remote"]   # work types to keep; a role that
                          # doesn't say how it works is always kept. Remote roles
                          # must also be open to your region (see `location` below)
recency_days: 45          # ignore postings older than this
max_roles_per_company: 10 # keep the N most senior per company
# advanced: detail_fetch_cap: 50   # bounds full-ad fetches per company per scan
```

Two more blocks make the search fully yours:

```yaml
search_label: "senior PM"   # used in notifications: "3 new senior PM roles"

location:                   # searching from somewhere other than London/UK?
  home_terms: ["berlin", "germany", "munich"]  # concrete locations you accept
  home_city: "berlin"                          # kept when a posting lists >5 locations
  remote_regions: ["germany", "europe", "emea"] # remote labels that include you
# omit the block entirely to keep the London/UK defaults

custom_patterns:            # searching a different discipline? Replace the
  # built-in Product-Management seniority ladder (first match wins, most
  # senior first). rank feeds seniority_min and the UI's seniority filter.
  - {pattern: "\\bhead of design\\b",          normalised: "Head of Design",          level: "Head",   rank: 6}
  - {pattern: "\\bsenior product designer\\b", normalised: "Senior Product Designer", level: "Senior", rank: 3}
```

With `custom_patterns` set, the PM-specific extras (`include_product_owner`,
`include_ai_innovation`) don't apply; `exclude_titles` and `seniority_min`
still do. The built-in PM ladder is documented in `specs/product-spec.md` §11.

## Notifications — Slack or ntfy

Two providers, chosen by `notify.provider` in `config/settings.yaml`:

- **Slack** (the default): create an Incoming Webhook and put it in
  `SLACK_WEBHOOK_URL` in `.env`. Done.
- **[ntfy](https://ntfy.sh)** — simpler if you don't use Slack: set
  `notify.provider: ntfy` and `ntfy_topic: <a-hard-to-guess-topic>` in
  `settings.yaml`, then subscribe to that topic in the ntfy phone app. No
  account or webhook needed.

Leave both unset for no notifications — the web UI works regardless.

## `.env` — secrets and addresses

| Variable | What it does |
|---|---|
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook for daily notifications. Leave empty for none. |
| `WEB_BASE_URL` | The address your dashboard is reachable at, used for links in Slack messages (e.g. `http://localhost:8765`). |
| `ANTHROPIC_API_KEY` | Optional. Lets Claude help with fuzzy parsing (title edge cases, salary extraction, company summaries). Everything works without it — regex fallbacks are built in. |
| `SEEK_AT` / `SEEK_TZ` | Daily scan time and timezone (default `08:00` / `Europe/London`). |

## `config/settings.yaml` — operational knobs

Three things live here that you might actually touch:

- the **notify block** (provider Slack/ntfy — see above),
- **`web_base_url`** — same job as the `WEB_BASE_URL` env var (links in
  notifications), and
- **`use_claude`** — the Claude API on/off switch.

The rest is operational tuning — timeouts, per-domain rate limit (1
request/second — please keep it polite), retries, and pagination caps. The
defaults are sensible; you rarely need to touch them.

## Advanced: per-company overrides

`config/overrides/<slug>.yaml` can pin scraping details for a stubborn company
(e.g. a specific ATS type for a custom careers domain). See
`specs/company-management.md` in the dev docs.
