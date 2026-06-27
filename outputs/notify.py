"""Push notifications for genuinely-new roles (README §20 / deferred feature).

Fires only when the run's diff contains `added`/`reopened` rows — never for routine
updates or closures. Default provider is ntfy (https://ntfy.sh/<topic>): zero setup,
just pick a hard-to-guess topic and install the ntfy app. Disabled until configured.
The network send is injectable for tests.
"""
from __future__ import annotations

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


def notify(diff: list[dict], settings: dict, http, sender=None) -> bool:
    """Send a notification if enabled and there are new/reopened roles.
    Returns True if a notification was sent."""
    cfg = settings.get("notify") or {}
    rows = new_rows(diff)
    if not cfg.get("enabled") or not rows:
        return False
    provider = (cfg.get("provider") or "ntfy").lower()
    title = f"{len(rows)} new PM role(s)"
    body = build_message(diff)
    if provider == "ntfy":
        topic = cfg.get("ntfy_topic")
        if not topic:
            return False
        (sender or _send_ntfy)(_ntfy_url(topic), title, body, http)
        return True
    return False
