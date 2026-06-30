#!/usr/bin/env python3
"""Daily scheduler for the scraper container.

Runs `main.py seek` once a day at a fixed local time (default **08:00
Europe/London**) rather than every 24h from container start. Override via env:
`SEEK_AT=HH:MM`, `SEEK_TZ=Area/City`. DST-aware via zoneinfo (the `tzdata` wheel
ships the database, so it works on the slim image).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py<3.9
    ZoneInfo = None


def next_run(now: datetime, hour: int, minute: int) -> datetime:
    """The next occurrence of hour:minute at/after `now` (same tz as `now`)."""
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def main() -> None:
    at = os.environ.get("SEEK_AT", "08:00")
    tzname = os.environ.get("SEEK_TZ", "Europe/London")
    hour, minute = (int(x) for x in at.split(":", 1))
    tz = ZoneInfo(tzname) if ZoneInfo else None
    print(f"[scheduler] daily seek at {at} {tzname}", flush=True)
    while True:
        now = datetime.now(tz)
        target = next_run(now, hour, minute)
        wait = (target - now).total_seconds()
        print(f"[scheduler] next run {target.isoformat()} (in {wait / 3600:.1f}h)", flush=True)
        time.sleep(max(1.0, wait))
        print(f"[scheduler] running seek {datetime.now(tz).isoformat()}", flush=True)
        # --notify-empty: the daily run reports "all quiet" when nothing is new,
        # so a silent morning means broken, not just nothing-to-report.
        rc = subprocess.run([sys.executable, "main.py", "seek", "--notify-empty"]).returncode
        # Keep the daily cadence on a transient failure, but make a bad run loud
        # (visible in `docker logs`) instead of looking like a normal scheduled run.
        if rc != 0:
            print(f"[scheduler] WARNING: seek exited {rc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
