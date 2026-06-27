# Scheduling `seek`

Run the one-shot on a schedule with the OS scheduler (no long-running Python loop).
A run emits a push notification only when it finds **new/reopened** roles
(configure `notify` in `config/settings.yaml` first).

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

> The plist uses absolute paths for this repo. If you move the repo, update the
> three paths inside it.

## Linux / cron alternative

```cron
0 8 * * *  /Users/sasasarunic/_Sources/job-search-assistant/scripts/run_seek.sh
```

## Notifications

Set in `config/settings.yaml`:

```yaml
notify:
  enabled: true
  provider: ntfy
  ntfy_topic: "ssarunic-pm-roles-7x2k9"   # any hard-to-guess string
```

Install the **ntfy** app (iOS/Android) and subscribe to the same topic. Each run
that surfaces new roles pushes a message listing them. Test end-to-end with
`scripts/run_seek.sh` (or `python main.py seek`).
