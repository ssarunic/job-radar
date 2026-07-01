"""Recruitee adapter — network-free, against a canned JSON client."""
from scrapers.ats.recruitee import (
    RecruiteeFetcher,
    _employment,
    _location,
    _salary_text,
)
from scrapers.ladder import detect_ats
from scrapers.result import EMPTY, OK
from services import discovery


class FakeHttp:
    def __init__(self, offers, expect_api=None):
        self.payload = {"offers": offers}
        self.expect_api = expect_api
        self.body = ""

    def get_json(self, url, **kw):
        if self.expect_api:
            assert url == self.expect_api, url
        return self.payload

    def get(self, url, **kw):
        return type("R", (), {"text": self.body})()


REMOTE_PM = {
    "id": 1, "title": "Staff Product Manager - AI - Remote EMEA",
    "careers_url": "https://careers.hostaway.com/o/staff-pm-ai",
    "location": "Remote job", "city": "Barcelona", "country": "Spain", "remote": True,
    "description": "<p>Build <b>AI</b> products.</p>", "requirements": "<ul><li>7+ years</li></ul>",
    "employment_type_code": "fulltime_permanent", "published_at": "2026-06-18 10:22:34 UTC",
    "status": "published",
}
LONDON_ROLE = {
    "id": 2, "title": "Product Manager", "careers_url": "https://x/o/pm",
    "location": "London", "city": "London", "country": "United Kingdom", "remote": False,
    "description": "<p>desc</p>", "employment_type_code": "contract", "status": "published",
}
DRAFT = {"id": 3, "title": "Draft role", "careers_url": "https://x/o/d", "status": "draft"}


def _company(url="https://careers.hostaway.com/o/staff-pm-ai"):
    return {"slug": "hostaway", "careers_url": url}


def test_listing_uses_careers_origin_and_maps():
    # custom domain: API is the careers-URL origin, not a recruitee subdomain
    http = FakeHttp([REMOTE_PM], expect_api="https://careers.hostaway.com/api/offers/")
    res = RecruiteeFetcher(_company(), http).listing()
    assert res.status == OK and len(res.postings) == 1
    p = res.postings[0]
    assert p["title"] == "Staff Product Manager - AI - Remote EMEA"
    assert p["url"] == "https://careers.hostaway.com/o/staff-pm-ai"
    assert p["employment_type"] == "Full time" and p["source_detail"] == "Recruitee"
    assert "AI" in p["description"] and "## Requirements" in p["description"]


def test_listing_direct_recruitee_origin():
    http = FakeHttp([REMOTE_PM], expect_api="https://acme.recruitee.com/api/offers/")
    res = RecruiteeFetcher(_company("https://acme.recruitee.com/"), http).listing()
    assert res.status == OK


def test_remote_location_keeps_country():
    assert _location(REMOTE_PM) == "Remote — Spain"       # filter can accept EU-remote


def test_onsite_location_composed_from_city_country():
    assert _location(LONDON_ROLE) == "London, United Kingdom"


def test_salary_dict_coerced_to_string():
    assert _salary_text({"max": None, "min": None, "period": None, "currency": None}) == ""
    assert _salary_text({"min": 50000, "max": 70000, "currency": "EUR"}) == "EUR 50000–70000"
    assert _salary_text("£90k") == "£90k"


def test_employment_code_mapping():
    assert _employment("fulltime_permanent") == "Full time"
    assert _employment("parttime") == "Part time"
    assert _employment("contract") == "Contract"
    assert _employment("temporary") == "Contract"


def test_non_published_dropped():
    res = RecruiteeFetcher(_company(), FakeHttp([REMOTE_PM, DRAFT])).listing()
    assert [p["title"] for p in res.postings] == ["Staff Product Manager - AI - Remote EMEA"]


def test_empty_listing():
    res = RecruiteeFetcher(_company(), FakeHttp([])).listing()
    assert res.status == EMPTY and res.postings == []


def test_detect_ats_direct_host():
    assert detect_ats({"careers_url": "https://hostaway.recruitee.com/"}, http=None) == "recruitee"


def test_discovery_direct_recruitee_url():
    info = discovery._from_url("https://acme.recruitee.com/")
    assert info["ats_type"] == "recruitee" and info["careers_url"] == "https://acme.recruitee.com/"


def test_discovery_custom_domain_detects_recruitee_no_slug_needed():
    http = FakeHttp([])
    http.body = '<script src="https://careers-analytics.recruitee.com/x.js"></script>'
    info = discovery._from_url("https://careers.hostaway.com/o/staff-pm-ai", http)
    assert info["ats_type"] == "recruitee"
    assert info["careers_url"] == "https://careers.hostaway.com/o/staff-pm-ai"
    assert info["name"] == "Hostaway"                     # SLD, not the "careers" subdomain
