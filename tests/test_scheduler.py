"""scripts/scheduler.next_run — fixed daily-time logic (network-free)."""
from datetime import datetime

from scripts.scheduler import next_run


def test_today_when_before_target():
    assert next_run(datetime(2026, 6, 29, 6, 30), 8, 0) == datetime(2026, 6, 29, 8, 0)


def test_tomorrow_when_after_target():
    assert next_run(datetime(2026, 6, 29, 9, 15), 8, 0) == datetime(2026, 6, 30, 8, 0)


def test_exact_time_rolls_to_tomorrow():
    assert next_run(datetime(2026, 6, 29, 8, 0, 0), 8, 0) == datetime(2026, 6, 30, 8, 0)
