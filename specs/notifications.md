# Notifications (Slack / ntfy + daily heartbeat)

> **Status:** ✅ implemented (retrospective spec). Push notifications for new roles,
> plus a daily "all quiet" heartbeat so a silent morning means *broken*, not
> *nothing-new*. Owned by `outputs/notify.py`; deferred to `constitution.md`
> (single-user, local secrets).

## Overview

After each run, the notifier pushes a message **only when the run diff contains
`added`/`reopened` rows** — never for routine updates/closures. The **daily scheduler
additionally fires an "all quiet" heartbeat** on a no-new-roles run, so the absence of
a message is unambiguous. Notifications never fail the run (the call is wrapped) and
the network send is injectable, so providers are unit-tested without network.

## Behaviour

- **New roles** → a message listing the new/reopened roles (max 12, then "…and N more").
- **Heartbeat** (`notify_empty=True`, passed only by the scheduler via `seek --notify-empty`)
  → on an empty diff, send "No new senior PM roles since yesterday" with a trailer:
  `checked N companies, M roles tracked` and, if any failed, `⚠️ K failed to load` — so a
  broken scrape can't masquerade as a quiet day. Manual CLI / web seeks stay **silent** on
  empty (flag defaults off).
- **Fires from** `services/run_service.seek_run(..., notify_empty=..., summary=...)`, where
  `summary = {companies, open_total, failed}` (from the run stats). `main.py seek
  --notify-empty` sets the flag; `scripts/scheduler.py` passes it for the daily run.

## Providers (`notify.provider`, config under `notify:` in `config/settings.yaml`)

- **ntfy** — `https://ntfy.sh/<topic>` (or a full URL). Zero setup; plain-text body /
  heartbeat.
- **slack** — Incoming Webhook (`notify.slack_webhook`, or `$SLACK_WEBHOOK_URL` if blank).
  Block Kit message where **each role title deep-links to its web-app detail page**
  (`web_base_url/jobs/<id>`, from `settings.web_base_url` or `$WEB_BASE_URL`) with an
  "apply ↗" external link. The heartbeat uses a distinct "✅ All quiet — no new roles"
  Block Kit message.

## Interactive scans suppress Slack

The web "scan on follow" and the "Refresh now" seek copy settings with
`notify.enabled=false` — you're already in the UI, so results show in the lists rather
than pinging Slack. See `company-management.md` / `web-refresh-and-activity.md`.

## Tests

`tests/test_notify.py` — network-free via the injected sender: new-rows selection,
Slack/ntfy new-role messages, heartbeat (Slack + ntfy), failed-company flag, and
"off-by-default when `notify_empty` is false".

## Non-goals

- Per-role or per-company notification routing; digest scheduling beyond the single
  daily run; email/SMS providers.
