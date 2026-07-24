"""Push notifications for genuinely-new roles (product-spec §20 / deferred feature).

Fires when the run's diff contains `added`/`reopened` rows — never for routine
updates or closures. The daily scheduler additionally passes `notify_empty=True`
so a quiet run still sends an **"all quiet" heartbeat** (so a silent morning means
"checked, nothing new" rather than "maybe broken"); manual/web seeks stay silent
when there's nothing new. Providers:
- **ntfy** (https://ntfy.sh/<topic>): zero setup, plain-text body.
- **slack**: Incoming Webhook, Block Kit message where each role title **deep-links
  to its web-app detail page** (`web_base_url/jobs/<id>`) so you can open it in the
  tracker from your phone, plus an "apply ↗" link to the external posting.

Disabled until configured. The network send is injectable for tests.
"""
from __future__ import annotations

import os

NEW_CHANGES = ("added", "reopened")


def new_rows(diff: list[dict]) -> list[dict]:
    return [d for d in diff if d.get("change") in NEW_CHANGES]


def build_message(diff: list[dict], max_items: int = 12) -> str:
    rows = new_rows(diff)
    lines = []
    for d in rows[:max_items]:
        loc = d.get("location") or ""
        lines.append(f"• {d.get('company','')}: {d.get('title','')}"
                     + (f" ({loc})" if loc else ""))
    if len(rows) > max_items:
        lines.append(f"…and {len(rows) - max_items} more")
    return "\n".join(lines)


def _ntfy_url(topic: str) -> str:
    return topic if topic.startswith("http") else f"https://ntfy.sh/{topic}"


def _send_ntfy(url: str, title: str, body: str, http) -> None:
    http.post(url, data=body.encode("utf-8"),
              headers={"Title": title, "Tags": "briefcase"})


# --- Slack (Incoming Webhook + Block Kit, deep-linked to the web app) -----------

def _detail_url(web_base_url: str, row: dict) -> str:
    """Web-app detail link for a role, falling back to the external posting URL."""
    if web_base_url and row.get("id"):
        return f"{web_base_url.rstrip('/')}/jobs/{row['id']}"
    return row.get("url") or ""


def _slack_line(row: dict, web_base_url: str) -> str:
    title = row.get("title") or "(role)"
    detail = _detail_url(web_base_url, row)
    label = f"<{detail}|{title}>" if detail else title   # Slack mrkdwn link
    loc = row.get("location")
    line = f"• *{label}* — {row.get('company', '')}" + (f" ({loc})" if loc else "")
    ext = row.get("url")
    if ext and ext != detail:                            # also offer the external apply link
        line += f"  ·  <{ext}|apply ↗>"
    return line


def build_slack_blocks(diff: list[dict], web_base_url: str = "", max_items: int = 12):
    """Return (fallback_text, Block Kit blocks) for the new/reopened roles."""
    rows = new_rows(diff)
    text = f"{len(rows)} new senior PM role{'s' if len(rows) != 1 else ''}"
    lines = [_slack_line(r, web_base_url) for r in rows[:max_items]]
    if len(rows) > max_items:
        lines.append(f"_…and {len(rows) - max_items} more_")
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"🎯 {text}", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
    ]
    return text, blocks


def _send_slack(webhook: str, text: str, blocks: list, http) -> None:
    http.post(webhook, json={"text": text, "blocks": blocks})


# --- "All quiet" heartbeat (no new roles; daily scheduler only) -----------------

def _heartbeat_tail(summary: dict | None) -> str:
    """Shared trailer: 'checked N companies' plus a failure flag if any failed."""
    s = summary or {}
    bits = []
    if s.get("companies"):
        bits.append(f"checked {s['companies']} companies")
    if s.get("open_total"):
        bits.append(f"{s['open_total']} roles tracked")
    line = ", ".join(bits)
    if s.get("failed"):                                   # don't disguise a broken scrape
        line += (" — " if line else "") + f"⚠️ {s['failed']} failed to load"
    return line


def build_heartbeat_message(summary: dict | None = None) -> str:
    tail = _heartbeat_tail(summary)
    return "No new senior PM roles since yesterday." + (f" ({tail})" if tail else "")


def build_slack_heartbeat(summary: dict | None = None):
    """Return (fallback_text, Block Kit blocks) for a no-new-roles heartbeat."""
    text = "No new senior PM roles since yesterday"
    body = "No new or reopened roles since yesterday."
    tail = _heartbeat_tail(summary)
    if tail:
        body += f"\n_{tail}._"
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": "✅ All quiet — no new roles", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": body}},
    ]
    return text, blocks


def notify(diff: list[dict], settings: dict, http, sender=None,
           *, notify_empty: bool = False, summary: dict | None = None) -> bool:
    """Send a notification if enabled and there are new/reopened roles.

    With `notify_empty=True` (the daily scheduler), also send an "all quiet"
    heartbeat when there are no new roles. `summary` supplies the heartbeat's
    counts (companies checked, roles tracked, companies that failed to load).
    Returns True if a notification was sent."""
    cfg = settings.get("notify") or {}
    rows = new_rows(diff)
    if not cfg.get("enabled"):
        return False
    if not rows and not notify_empty:
        return False
    provider = (cfg.get("provider") or "ntfy").lower()

    if provider == "ntfy":
        topic = cfg.get("ntfy_topic")
        if not topic:
            return False
        if rows:
            title, body = f"{len(rows)} new PM role(s)", build_message(diff)
        else:
            title, body = "No new PM roles", build_heartbeat_message(summary)
        (sender or _send_ntfy)(_ntfy_url(topic), title, body, http)
        return True

    if provider == "slack":
        webhook = cfg.get("slack_webhook") or os.environ.get("SLACK_WEBHOOK_URL", "")
        if not webhook:
            return False
        web_base_url = settings.get("web_base_url") or os.environ.get("WEB_BASE_URL", "")
        if rows:
            text, blocks = build_slack_blocks(diff, web_base_url)
        else:
            text, blocks = build_slack_heartbeat(summary)
        (sender or _send_slack)(webhook, text, blocks, http)
        return True

    return False
