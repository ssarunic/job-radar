# FAQ

**Why isn't a job I can see on the company's site showing in JobRadar?**
The usual reasons, in order of likelihood:

1. **Seniority floor** — its title ranks below your `seniority_min` (a plain
   "Product Manager" ranks 2; the default floor is 3).
2. **Excluded words** — the title contains something in `exclude_titles`
   (marketing, graduate, internship, …).
3. **Location** — it isn't in your configured locations and isn't
   remote-eligible for your region (US-only remote is skipped).
4. **Too old** — posted longer ago than `recency_days` (live job boards are
   exempt from this; it mainly affects scraped HTML pages).
5. **Per-company cap** — the company already has `max_roles_per_company`
   more-senior roles tracked.

The Activity page shows exactly what each scan found and kept.

**A role shows "suspected filled" but it's still on their site.**
Job boards occasionally fail to respond or briefly hide postings; JobRadar
needs two consecutive misses before suspecting and a third before closing. If
the posting is really still live it will re-open automatically on the next
successful scan.

**Can I track companies with weird careers sites?**
Paste the URL and try — JobRadar recognises ten job-board systems and can
often detect one embedded in a custom page. If it says "not a recognised ATS
job board", that company needs developer attention (see
`specs/README.md` → adding an adapter).

**Is this scraping polite/legal?**
JobRadar only reads public careers pages and the same public data feeds your
browser uses, at max 1 request/second per site, honouring robots.txt for page
scraping. No logins, no paywalls, no personal data — see
`specs/constitution.md` for the exact policy.

**Do I need a Claude/Anthropic API key?**
No. It's optional and off by default — it improves parsing of odd titles and
salary text. Expect roughly $15–30 per ~300 companies if enabled.

**How do I add notes to a role, or mark it as applied?**
Open the role's Markdown file in your data volume
(`jobs/<company>/<role>--<id>.md`): write anything under the `## My notes`
heading, and set `status: applied` in the frontmatter at the top. JobRadar
displays both in the UI and never overwrites either, even when the ad changes
or the posting closes. (In-UI editing isn't built yet.)

**Where is my data?**
In a Docker volume, as human-readable Markdown files (one per role) plus a
JSONL index. Your notes and applied-statuses live in those files. Backing up
the volume backs up everything, e.g.:

```bash
docker run --rm -v job-radar_jsa-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/jobradar-backup.tgz -C / data
```

**How do I update JobRadar?**
`git pull && docker compose build && docker compose --profile scheduler up -d`.
Your data and config live in the volume, so updates don't touch them.
