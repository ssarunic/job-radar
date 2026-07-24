"""Per-domain rate limiting (product-spec §10, §17)."""
from __future__ import annotations

import time
from urllib.parse import urlsplit


class RateLimiter:
    def __init__(self, per_sec: float = 1.0):
        self.min_interval = 1.0 / per_sec if per_sec > 0 else 0.0
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> None:
        host = urlsplit(url).netloc.lower()
        now = time.monotonic()
        last = self._last.get(host)
        if last is not None:
            elapsed = now - last
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        self._last[host] = time.monotonic()
