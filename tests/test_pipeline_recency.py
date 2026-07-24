"""Recency cutoff vs live ATS feeds (false-closure fix, 2026-07-24 audit).

A role present in an ATS board's listing is open by definition — the recency
cutoff must not drop it, or a still-open role silently ages out mid-tracking
and the lifecycle falsely closes it (Monzo/Spotify/Hostaway/Airwallex all
closed on exactly day 46). The cutoff still applies to discovery rungs
(playwright/static), where a stale page can render long-filled roles.
"""
from datetime import date

from services import pipeline

PROFILE = {"seniority_min": 3, "include_product_owner": True, "exclude_titles": [],
           "locations": ["London"], "allow_remote": True, "employment": ["Full time"],
           "recency_days": 45, "max_roles_per_company": 10}

TODAY = date(2026, 7, 24)


def _raw(posted):
    return [{"title": "Product Director, Flex", "location": "London",
             "employment_type": "Full time", "description": "Job description body.",
             "salary_text": "", "url": "https://x/jobs/1",
             "source_detail": "Greenhouse", "posted_date": posted}]


class _LiveFetcher:
    needs_detail = False
    live_listing = True


class _DiscoveryFetcher:
    needs_detail = False
    live_listing = False


def test_live_feed_keeps_role_older_than_recency_cutoff():
    # posted 113 days ago but present in the ATS feed -> still open, keep
    kept = pipeline.process_company({"name": "X", "slug": "x"}, PROFILE,
                                    _raw("2026-04-02"), _LiveFetcher(), {}, None, TODAY)
    assert [k.title_raw for k in kept] == ["Product Director, Flex"]


def test_discovery_rung_still_applies_recency_cutoff():
    kept = pipeline.process_company({"name": "X", "slug": "x"}, PROFILE,
                                    _raw("2026-04-02"), _DiscoveryFetcher(), {}, None, TODAY)
    assert kept == []


def test_discovery_rung_keeps_recent_role():
    kept = pipeline.process_company({"name": "X", "slug": "x"}, PROFILE,
                                    _raw("2026-07-10"), _DiscoveryFetcher(), {}, None, TODAY)
    assert [k.title_raw for k in kept] == ["Product Director, Flex"]
