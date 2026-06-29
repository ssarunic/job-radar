"""Notifications: fire only on new/reopened roles; provider send is injectable."""
from outputs import notify

DIFF = [
    {"change": "added", "company": "Monzo", "title": "Senior PM", "location": "London"},
    {"change": "reopened", "company": "Wise", "title": "Principal PM", "location": "London"},
    {"change": "updated", "company": "Cohere", "title": "Director", "location": "London"},
    {"change": "closed", "company": "Stripe", "title": "Group PM", "location": "London"},
]


def _sender():
    calls = []

    def send(url, title, body, http):
        calls.append({"url": url, "title": title, "body": body})
    send.calls = calls
    return send


def test_new_rows_only_added_and_reopened():
    rows = notify.new_rows(DIFF)
    assert {r["change"] for r in rows} == {"added", "reopened"}


def test_build_message_lists_new_roles():
    msg = notify.build_message(DIFF)
    assert "Monzo: Senior PM (London)" in msg
    assert "Wise: Principal PM (London)" in msg
    assert "Cohere" not in msg            # updates aren't new
    assert "Stripe" not in msg            # closures aren't new


def test_build_message_truncates():
    big = [{"change": "added", "company": f"C{i}", "title": "PM", "location": "London"}
           for i in range(20)]
    msg = notify.build_message(big, max_items=12)
    assert "…and 8 more" in msg


def test_notify_disabled_does_not_send():
    s = _sender()
    settings = {"notify": {"enabled": False, "provider": "ntfy", "ntfy_topic": "t"}}
    assert notify.notify(DIFF, settings, http=None, sender=s) is False
    assert s.calls == []


def test_notify_sends_on_new_roles():
    s = _sender()
    settings = {"notify": {"enabled": True, "provider": "ntfy", "ntfy_topic": "my-topic"}}
    assert notify.notify(DIFF, settings, http=None, sender=s) is True
    assert len(s.calls) == 1
    assert s.calls[0]["url"] == "https://ntfy.sh/my-topic"
    assert s.calls[0]["title"] == "2 new PM role(s)"
    assert "Monzo" in s.calls[0]["body"]


def test_notify_no_send_when_no_new_rows():
    s = _sender()
    only_updates = [{"change": "updated", "company": "X", "title": "PM", "location": ""},
                    {"change": "closed", "company": "Y", "title": "PM", "location": ""}]
    settings = {"notify": {"enabled": True, "provider": "ntfy", "ntfy_topic": "t"}}
    assert notify.notify(only_updates, settings, http=None, sender=s) is False
    assert s.calls == []


def test_notify_requires_topic():
    s = _sender()
    settings = {"notify": {"enabled": True, "provider": "ntfy", "ntfy_topic": ""}}
    assert notify.notify(DIFF, settings, http=None, sender=s) is False


def test_ntfy_url_accepts_bare_topic_and_full_url():
    assert notify._ntfy_url("abc") == "https://ntfy.sh/abc"
    assert notify._ntfy_url("https://ntfy.example.com/abc") == "https://ntfy.example.com/abc"


# --- Slack provider (deep links to the web app) ---------------------------------

SLACK_DIFF = [
    {"change": "added", "id": "abc123", "company": "Monzo", "title": "Senior PM",
     "location": "London", "url": "https://boards.greenhouse.io/monzo/jobs/abc"},
    {"change": "reopened", "id": "def456", "company": "Wise", "title": "Principal PM",
     "location": "", "url": "https://wise.com/jobs/def"},
    {"change": "updated", "company": "Cohere", "title": "Director", "location": "London"},
]


def _slack_sender():
    calls = []

    def send(webhook, text, blocks, http):
        calls.append({"webhook": webhook, "text": text, "blocks": blocks})
    send.calls = calls
    return send


def test_slack_blocks_deep_link_to_web_app():
    text, blocks = notify.build_slack_blocks(SLACK_DIFF, web_base_url="http://pi:8765/")
    section = blocks[1]["text"]["text"]
    assert text == "2 new senior PM roles"
    assert blocks[0]["type"] == "header" and "2 new senior PM roles" in blocks[0]["text"]["text"]
    # title links to the web-app detail page; external posting offered as "apply"
    assert "<http://pi:8765/jobs/abc123|Senior PM>" in section
    assert "<https://boards.greenhouse.io/monzo/jobs/abc|apply ↗>" in section
    assert "Cohere" not in section        # updates aren't new


def test_slack_blocks_fall_back_to_external_when_no_web_base_url():
    _text, blocks = notify.build_slack_blocks(SLACK_DIFF, web_base_url="")
    section = blocks[1]["text"]["text"]
    assert "<https://boards.greenhouse.io/monzo/jobs/abc|Senior PM>" in section
    assert "apply ↗" not in section       # no duplicate link when title already is the posting


def test_notify_slack_sends_with_webhook():
    s = _slack_sender()
    settings = {"web_base_url": "http://pi:8765",
                "notify": {"enabled": True, "provider": "slack",
                           "slack_webhook": "https://hooks.slack.com/services/XXX"}}
    assert notify.notify(SLACK_DIFF, settings, http=None, sender=s) is True
    assert s.calls[0]["webhook"] == "https://hooks.slack.com/services/XXX"
    assert s.calls[0]["text"] == "2 new senior PM roles"


def test_notify_slack_reads_webhook_from_env(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/ENV")
    s = _slack_sender()
    settings = {"notify": {"enabled": True, "provider": "slack", "slack_webhook": ""}}
    assert notify.notify(SLACK_DIFF, settings, http=None, sender=s) is True
    assert s.calls[0]["webhook"] == "https://hooks.slack.com/services/ENV"


def test_notify_slack_requires_webhook(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    s = _slack_sender()
    settings = {"notify": {"enabled": True, "provider": "slack", "slack_webhook": ""}}
    assert notify.notify(SLACK_DIFF, settings, http=None, sender=s) is False
