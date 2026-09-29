# Scheduling `seek`

> **Production (Raspberry Pi) uses the in-container scheduler** — `scripts/scheduler.py`
> runs `seek` daily at 08:00 Europe/London inside the `scraper` container. See
> **`specs/deploy.md`**. The launchd/cron setup below is for running `seek` directly
> on a macOS/Linux host **without** Docker.

Run the one-shot on a schedule with the OS scheduler (no long-running Python loop).
A run emits a push notification only when it finds **new/reopened** roles
(configure `notify` in `config/settings.yaml` first — `provider: slack` or `ntfy`).

## macOS — launchd (recommended)

```bash
chmod +x scripts/run_seek.sh
cp scripts/com.jobsearch.seek.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jobsearch.seek.plist   # enable
# launchctl unload ~/Library/LaunchAgents/com.jobsearch.seek.plist  # disable
launchctl start com.jobsearch.seek                                # run once now to test
```

Default: daily at 08:00. Edit `StartCalendarInterval` in the plist to change it.
Logs: `data/runs/cron.log` (run output) and `data/runs/launchd.{out,err}.log`.

> The plist needs absolute paths: replace `/ABSOLUTE/PATH/TO/job-radar` with your
> checkout location (three occurrences) before loading it.

## Linux / cron alternative

```cron
0 8 * * *  /ABSOLUTE/PATH/TO/job-radar/scripts/run_seek.sh
```

## Notifications

Set in `config/settings.yaml`:

```yaml
notify:
  enabled: true
  provider: ntfy
  ntfy_topic: "jobradar-roles-q7x2k9"   # any hard-to-guess string
```

Install the **ntfy** app (iOS/Android) and subscribe to the same topic. Each run
that surfaces new roles pushes a message listing them. Test end-to-end with
`scripts/run_seek.sh` (or `python main.py seek`).
