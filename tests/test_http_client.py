"""Shared HTTP client: retry/backoff + robots (#8). Network-free via a fake session."""
import pytest
from requests import ConnectionError as ReqConnError, HTTPError

from scrapers.http_client import HttpClient


class _Resp:
    def __init__(self, status=200, text="", json_data=None):
        self.status_code, self.text, self._json = status, text, json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            e = HTTPError(str(self.status_code)); e.response = self; raise e


class _Session:
    def __init__(self, responses):
        self.responses, self.calls, self.headers = list(responses), [], {}

    def request(self, method, url, **kw):
        self.calls.append((method, url))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def get(self, url, **kw):
        return self.request("GET", url, **kw)


class _Limiter:
    def wait(self, url):
        pass


def _client(responses, **settings):
    s = {"retries": 2, "request_timeout": 5, "user_agent": "t", **settings}
    sleeps = []
    c = HttpClient(s, _Limiter(), sleep=sleeps.append)
    c.session = _Session(responses)
    c.sleeps = sleeps
    return c


def test_retry_on_503_then_success():
    c = _client([_Resp(503), _Resp(200, json_data={"ok": 1})])
    assert c.get_json("http://x") == {"ok": 1}
    assert len(c.session.calls) == 2
    assert len(c.sleeps) == 1            # one backoff


def test_no_retry_on_404():
    c = _client([_Resp(404)])
    with pytest.raises(HTTPError):
        c.get("http://x")
    assert len(c.session.calls) == 1     # permanent, not retried


def test_retry_on_connection_error():
    c = _client([ReqConnError("boom"), _Resp(200, json_data={"a": 1})])
    assert c.get_json("http://x") == {"a": 1}
    assert len(c.session.calls) == 2


def test_retries_exhausted_raises():
    c = _client([_Resp(503), _Resp(503), _Resp(503)])  # retries=2 -> 3 attempts
    with pytest.raises(HTTPError):
        c.get("http://x")
    assert len(c.session.calls) == 3
    assert len(c.sleeps) == 2


def test_backoff_is_exponential():
    c = _client([_Resp(503), _Resp(503), _Resp(200, json_data={})])
    c.get_json("http://x")
    assert c.sleeps == [1.0, 2.0]


def test_robots_disallow():
    c = _client([_Resp(200, text="User-agent: *\nDisallow: /private\n")])
    assert c.allowed("http://x.com/jobs") is True
    assert c.allowed("http://x.com/private/x") is False   # cached, no 2nd fetch
    assert len(c.session.calls) == 1


def test_robots_fails_open_on_challenge():
    c = _client([_Resp(403, text="<html>Just a moment</html>")])
    assert c.allowed("http://x.com/anything") is True


def test_respect_robots_off_skips_fetch():
    c = _client([], respect_robots=False)
    assert c.allowed("http://x.com/whatever") is True
    assert len(c.session.calls) == 0
