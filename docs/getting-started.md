# Getting started

JobRadar runs on your own computer (or a small home server) inside Docker. You
don't need to know Python or JavaScript — if you can install an app and edit a
text file, you can run it.

## 1. Install Docker

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(macOS / Windows) or Docker Engine (Linux). Everything JobRadar needs ships in
one container.

## 2. Get JobRadar

```bash
git clone https://github.com/ssarunic/job-radar
cd job-radar
```

(No git? Download the ZIP from GitHub and unpack it.)

## 3. Configure (optional, but recommended)

```bash
cp .env.example .env
```

Open `.env` in any text editor. The only thing most people set is
`SLACK_WEBHOOK_URL` — a Slack "Incoming Webhook" that lets JobRadar message you
when new roles appear. Skip it if you're happy just checking the web page.

Then look at `config/search_profile.yaml` — this is **what you're searching
for**: role titles, minimum seniority, where you want to work. It ships with a
senior Product Management profile for London/UK; edit it to match your search.
Every field is explained in [Configuration](configuration.md).

## 4. Start it

```bash
docker compose --profile scheduler up -d
```

Then open **http://localhost:8765**. The `--profile scheduler` part runs the
daily scan (08:00 local time by default); without it you get just the web UI
and the manual "↻ Refresh" button.

## 5. Follow your first companies

Click **+ Follow** in the web UI and paste a company's careers-page URL (e.g.
`https://job-boards.greenhouse.io/monzo` or just the careers page you found on
Google). JobRadar detects the job board behind it and scans it immediately —
matching roles appear within seconds.

Mainstream job boards work by pasting any careers URL: Greenhouse, Ashby,
Lever, SmartRecruiters, Workday, Oracle, Recruitee, RevolutPeople. A company
with a fully custom careers site may need a developer — see the
[FAQ](faq.md).

## 6. Done

From here, JobRadar checks every followed company each morning and records
what changed. See [Daily use](using.md) for how to read what it finds.
