"""Push notifications for genuinely-new roles (README §20 / deferred feature).

Fires only when the run's diff contains `added`/`reopened` rows — never for routine
updates or closures. Providers:
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


def notify(diff: list[dict], settings: dict, http, sender=None) -> bool:
    """Send a notification if enabled and there are new/reopened roles.
    Returns True if a notification was sent."""
    cfg = settings.get("notify") or {}
    rows = new_rows(diff)
    if not cfg.get("enabled") or not rows:
        return False
    provider = (cfg.get("provider") or "ntfy").lower()

    if provider == "ntfy":
        topic = cfg.get("ntfy_topic")
        if not topic:
            return False
        title = f"{len(rows)} new PM role(s)"
        (sender or _send_ntfy)(_ntfy_url(topic), title, build_message(diff), http)
        return True

    if provider == "slack":
        webhook = cfg.get("slack_webhook") or os.environ.get("SLACK_WEBHOOK_URL", "")
        if not webhook:
            return False
        web_base_url = settings.get("web_base_url") or os.environ.get("WEB_BASE_URL", "")
        text, blocks = build_slack_blocks(diff, web_base_url)
        (sender or _send_slack)(webhook, text, blocks, http)
        return True

    return False
