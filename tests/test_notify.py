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
