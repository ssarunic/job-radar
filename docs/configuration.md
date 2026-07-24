# Configuration

Three files control JobRadar. After the first run they live in the Docker
volume (the container copies defaults there on first boot); edit them there —
or before first boot, edit them in the repo's `config/` folder.

## `config/search_profile.yaml` — what you're looking for

```yaml
roles:                    # titles you're interested in (informational labels)
  - "Senior Product Manager"
  - "Head of Product"

seniority_min: 3          # keep roles ranked at or above this
                          # 9 CPO · 8 VP · 7 Director · 6 Head · 5 Principal/Staff
                          # 4 Group/Lead · 3 Senior · 2 mid-level
include_product_owner: true    # also keep "Product Owner" titles (rank 2)
include_ai_innovation: true    # rank AI/Innovation leadership titles too

exclude_titles:           # drop any title containing these words
  - "marketing"
  - "graduate"            # entry-level programmes
  - "internship"

locations:                # where you want to work (title/location match terms)
  - "London"
  - "UK"
allow_remote: true        # accept remote roles eligible for your region
remote_keywords: ["remote", "uk remote", "emea remote"]

employment: ["Full time", "Part time"]   # Contract is always excluded
recency_days: 45          # ignore postings older than this
max_roles_per_company: 10 # keep the N most senior per company
```

The seniority ladder itself (which words rank where) is currently tuned for
Product Management roles. Editing `exclude_titles`, `locations`, and
`seniority_min` covers most customization; deeper changes to the ladder are a
dev-docs topic (`specs/product-spec.md` §11).

## `.env` — secrets and addresses

| Variable | What it does |
|---|---|
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook for daily notifications. Leave empty for none. |
| `WEB_BASE_URL` | The address your dashboard is reachable at, used for links in Slack messages (e.g. `http://localhost:8765`). |
| `ANTHROPIC_API_KEY` | Optional. Lets Claude help with fuzzy parsing (title edge cases, salary extraction, company summaries). Everything works without it — regex fallbacks are built in. |
| `SEEK_AT` / `SEEK_TZ` | Daily scan time and timezone (default `08:00` / `Europe/London`). |

## `config/settings.yaml` — operational knobs

Timeouts, per-domain rate limit (1 request/second — please keep it polite),
retries, and the Claude on/off switch. The defaults are sensible; you rarely
need to touch this file.

## Advanced: per-company overrides

`config/overrides/<slug>.yaml` can pin scraping details for a stubborn company
(e.g. a specific ATS type for a custom careers domain). See
`specs/company-management.md` in the dev docs.
