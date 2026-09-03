"""Workday resolve_location (pipeline Stage A hook) — network-free.

Barclays' listing rows carry only a site label ("2 Locations", or a street address
like "Canary Wharf, 1 Churchill Place"); the detail record has the country.
"""
from scrapers.ats.workday import WorkdayFetcher

COMPANY = {"name": "Barclays", "slug": "barclays",
           "careers_url": "https://barclays.wd3.myworkdayjobs.com/External_Career_Site_Barclays"}

TARGET = {"jobPostingInfo": {
    "title": "Product Manager - Director",
    "location": "Canary Wharf, 1 Churchill Place",
    "additionalLocations": ["Glasgow, Clyde Place"],
    "country": {"descriptor": "United Kingdom", "id": "2924"},
    "jobRequisitionLocation": {"descriptor": "Canary Wharf, 1 Churchill Place",
                               "country": {"descriptor": "United Kingdom", "id": "2924"}},
    "startDate": "2026-09-02", "timeType": "Full time",
    "jobDescription": "<p>Own the product.</p>"}}


class _Http:
    settings = {}

    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get_json(self, url, **kw):
        self.calls.append(url)
        return self.payload


def _fetcher(payload=TARGET):
    http = _Http(payload)
    return WorkdayFetcher(COMPANY, http), http


def test_resolves_site_plus_country_and_additional_sites():
    f, http = _fetcher()
    url = f"{f.base}/{f.site}/job/Canary-Wharf-1-Churchill-Place/Product-Manager---Director_JR-1"
    assert f.resolve_location(url) == \
        "Canary Wharf, 1 Churchill Place, United Kingdom; Glasgow, Clyde Place"
    assert len(http.calls) == 1 and http.calls[0].endswith(
        "/job/Canary-Wharf-1-Churchill-Place/Product-Manager---Director_JR-1")


def test_detail_reuses_the_resolve_fetch():
    f, http = _fetcher()
    url = f"{f.base}/{f.site}/job/x/y_JR-1"
    f.resolve_location(url)
    body = f.detail(url)
    assert len(http.calls) == 1                       # one request, two consumers
    assert "Location: Canary Wharf, 1 Churchill Place" in body and "Own the product." in body


def test_single_site_and_missing_country():
    f, _ = _fetcher({"jobPostingInfo": {"location": "Glasgow Campus",
                                         "country": {"descriptor": "United Kingdom"}}})
    assert f.resolve_location(f"{f.base}/{f.site}/job/g/p") == "Glasgow Campus, United Kingdom"
    f, _ = _fetcher({"jobPostingInfo": {"location": "Somewhere"}})
    assert f.resolve_location(f"{f.base}/{f.site}/job/s/p") == "Somewhere"
    f, _ = _fetcher({})
    assert f.resolve_location(f"{f.base}/{f.site}/job/s/p") == ""
    assert f.resolve_location("") == ""
