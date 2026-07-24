"""Shared HTTP client (#8): one place for timeout, retries+backoff, per-domain
rate limiting, a consistent User-Agent, and robots.txt checks (product-spec §10, §17).

All requests-based adapters go through this so the crawler stays polite and
failures are handled consistently. `sleep` is injectable for tests.
"""
from __future__ import annotations

import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

# Retry on transient failures only; 4xx (except 429) are permanent.
_RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(self, settings: dict, limiter, sleep=time.sleep):
        self.settings = settings
        self.limiter = limiter
        self.timeout = settings.get("request_timeout", 20)
        self.retries = settings.get("retries", 2)
        self.respect_robots = settings.get("respect_robots", True)
        self._sleep = sleep
        self.session = requests.Session()
        self.user_agent = settings.get("user_agent", "JobSeekAssistant")
        self.session.headers["User-Agent"] = self.user_agent
        self._robots: dict[str, RobotFileParser | None] = {}

    def wait(self, url: str) -> None:
        self.limiter.wait(url)

    # --- core request with retry/backoff -------------------------------------
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        backoff = 1.0
        last_exc = None
        for attempt in range(self.retries + 1):
            self.wait(url)
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.RequestException as e:
                last_exc = e
                if attempt < self.retries:
                    self._sleep(backoff)
                    backoff *= 2
                    continue
                raise
            if resp.status_code in _RETRY_STATUS and attempt < self.retries:
                self._sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp
        raise last_exc  # pragma: no cover

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def get_json(self, url: str, **kwargs):
        return self.get(url, **kwargs).json()

    def post_json(self, url: str, **kwargs):
        return self.post(url, **kwargs).json()

    # --- robots.txt ----------------------------------------------------------
    def allowed(self, url: str) -> bool:
        """True if our UA may fetch `url`. Fails open: any robots fetch/parse
        error (incl. Cloudflare challenge on robots.txt) -> allowed."""
        if not self.respect_robots:
            return True
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.session.get(origin + "/robots.txt", timeout=self.timeout)
                if r.status_code == 200 and "<html" not in r.text[:200].lower():
                    rp.parse(r.text.splitlines())
                else:
                    rp = None  # missing/!200/challenge -> allow
            except requests.RequestException:
                rp = None
            self._robots[origin] = rp
        rp = self._robots[origin]
        if rp is None:
            return True
        return rp.can_fetch(self.user_agent, url)
