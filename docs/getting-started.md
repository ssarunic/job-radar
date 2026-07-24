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

What you're *searching for* (roles, seniority, location) is configured after
start-up: on first run the web UI points you to **Set up your search**
(`/setup`) — four questions, no file editing. (It ships with a senior Product Management profile
for London/UK; power users can edit `config/search_profile.yaml` directly —
every field is explained in [Configuration](configuration.md).)

## 4. Start it

```bash
docker compose --profile scheduler up -d
```

The first start **builds the image locally — expect a few minutes** of build
output; later starts are instant. Then open **http://localhost:8765**.

The `--profile scheduler` part runs the daily scan; without it you get just
the web UI and the manual "↻ Refresh" button. The scan runs at **08:00
Europe/London** by default — if you're elsewhere, set `SEEK_TZ` (e.g.
`Europe/Berlin`) and optionally `SEEK_AT` (e.g. `07:30`) in your `.env`.

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
