"""ATS discovery for `follow` — URL parsing (no network) + name probing (fake http)."""
from requests import HTTPError

from services import discovery


class FakeHttp:
    """get_json returns canned data per URL substring, else raises 404."""
    def __init__(self, mapping):
        self.mapping = mapping

    def get_json(self, url, **kw):
        for needle, val in self.mapping.items():
            if needle in url:
                return val
        e = HTTPError("404"); e.response = None; raise e


def test_from_url_ashby():
    d = discovery.discover("https://jobs.ashbyhq.com/openai", http=None)
    assert d["ats_type"] == "ashby" and d["ats_slug"] == "openai"


def test_from_url_greenhouse():
    d = discovery.discover("https://job-boards.greenhouse.io/monzo/jobs/123", http=None)
    assert d["ats_type"] == "greenhouse" and d["ats_slug"] == "monzo"


def test_from_url_workday():
    d = discovery.discover(
        "https://barclays.wd3.myworkdayjobs.com/External_Career_Site_Barclays", http=None)
    assert d["ats_type"] == "workday"
    assert "myworkdayjobs" in d["careers_url"]


def test_from_url_unknown_is_custom():
    d = discovery.discover("https://tessl.io/careers", http=None)
    assert d["ats_type"] == "custom"


def test_from_name_probes_ashby():
    http = FakeHttp({"posting-api/job-board/cohere": {"jobs": [1, 2, 3]}})
    d = discovery.discover("Cohere", http)
    assert d["ats_type"] == "ashby" and d["ats_slug"] == "cohere"
    assert d["careers_url"] == "https://jobs.ashbyhq.com/cohere"
    assert d["slug"] == "cohere"


def test_from_name_greenhouse_wins_first():
    http = FakeHttp({"boards/anthropic/jobs": {"jobs": [1]}})
    d = discovery.discover("Anthropic", http)
    assert d["ats_type"] == "greenhouse"


def test_from_name_no_match_returns_none():
    assert discovery.discover("Nonexistent Co", FakeHttp({})) is None


def test_smartrecruiters_requires_postings():
    # SR returns 200 with totalFound 0 for unknown companies -> must NOT match
    http = FakeHttp({"smartrecruiters.com/v1/companies/ghost": {"totalFound": 0}})
    assert discovery.discover("ghost", http) is None
