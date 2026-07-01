"""Oracle ORC adapter — network-free, against a canned REST client."""
import re

from scrapers.ats.oracle import OracleFetcher, _pick_uk_location
from scrapers.ladder import detect_ats
from scrapers.result import EMPTY, OK
from services import discovery

CAREERS = ("https://acme.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/"
           "en/sites/CX_1001/jobs")

FACET = {"items": [{"locationsFacet": [
    {"Name": "United States", "Id": "1"},
    {"Name": "LONDON, United Kingdom", "Id": "323"},
    {"Name": "United Kingdom", "Id": "999"},            # country-level → preferred
]}]}

DETAIL = {"items": [{"ExternalDescriptionStr": "<p>Great <b>PM</b> role</p>",
                     "PostedDate": "2026-07-01", "PrimaryLocation": "LONDON, United Kingdom",
                     "JobSchedule": "Full time"}]}


def _req(i, title="Senior Product Manager"):
    return {"Id": str(1000 + i), "Title": title, "PrimaryLocation": "LONDON, United Kingdom",
            "PostedDate": "2026-07-01", "ShortDescriptionStr": "short", "JobSchedule": "Full time"}


class FakeHttp:
    def __init__(self, total, per_page):
        self.settings = {"ats_max_pages": 25}
        self.total, self.per_page = total, per_page
        self.calls = []

    def get_json(self, url, **kw):
        self.calls.append(url)
        if "facetsList=LOCATIONS" in url:
            return FACET
        if "recruitingCEJobRequisitionDetails" in url:
            return DETAIL
        off = int(re.search(r"offset=(\d+)", url).group(1))
        page = [_req(i) for i in range(off, min(off + self.per_page, self.total))]
        return {"items": [{"TotalJobsCount": self.total, "requisitionList": page}]}


def _company():
    return {"slug": "acme", "careers_url": CAREERS}


def test_pick_uk_prefers_country_level():
    picked = _pick_uk_location(FACET["items"][0]["locationsFacet"])
    assert picked == ("999", "United Kingdom")          # not the London city node


def test_pick_uk_none_when_no_uk():
    assert _pick_uk_location([{"Name": "United States", "Id": "1"}]) is None


def test_site_and_host_parsed_from_url():
    f = OracleFetcher(_company(), FakeHttp(0, 100))
    assert f.site == "CX_1001"
    assert f.host == "acme.fa.us2.oraclecloud.com"


def test_listing_maps_and_applies_uk_facet():
    http = FakeHttp(total=2, per_page=100)
    res = OracleFetcher(_company(), http).listing()
    assert res.status == OK and len(res.postings) == 2
    p = res.postings[0]
    assert p["title"] == "Senior Product Manager"
    assert p["location"] == "LONDON, United Kingdom"
    assert p["url"].endswith("/sites/CX_1001/job/1000") and "CandidateExperience" in p["url"]
    assert p["source_detail"] == "Oracle" and p["employment_type"] == "Full time"
    # the country-level UK facet was applied to the list query
    assert any("selectedLocationsFacet=999" in c for c in http.calls)


def test_pagination_stops_at_total():
    http = FakeHttp(total=5, per_page=2)
    res = OracleFetcher(_company(), http).listing()
    assert len(res.postings) == 5                        # 2 + 2 + 1, then stop
    assert {p["url"].rsplit("/", 1)[-1] for p in res.postings} == {str(1000 + i) for i in range(5)}


def test_empty_listing():
    res = OracleFetcher(_company(), FakeHttp(total=0, per_page=100)).listing()
    assert res.status == EMPTY and res.postings == []


def test_detail_extracts_id_and_markdownifies():
    body = OracleFetcher(_company(), FakeHttp(0, 100)).detail(
        "https://acme.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210")
    assert "Great" in body and "PM" in body               # HTML → markdown
    assert "Employment type: Full time" in body and "2026-07-01" in body


def test_detail_no_id_returns_empty():
    assert OracleFetcher(_company(), FakeHttp(0, 100)).detail("https://x/no-job-here") == ""


def test_detect_ats_recognises_oracle():
    assert detect_ats({"careers_url": CAREERS}, http=None) == "oracle"


def test_discovery_from_oracle_url():
    info = discovery._from_url(CAREERS)
    assert info["ats_type"] == "oracle" and info["careers_url"] == CAREERS
