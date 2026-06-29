"""Talemetry adapter (curl_cffi + JSON-LD) — network-free via faked _get."""
from scrapers.ats import talemetry
from scrapers.ats.talemetry import TalemetryFetcher

# note the trailing comma before } — these JSON-LD blocks often have one
SAMPLE_HTML = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"JobPosting","title":"Head of Product",
 "employmentType":"FULL_TIME","datePosted":"2026-06-19",
 "description":"<h2>About</h2><ul><li>Own the <strong>product</strong></li></ul>",}
</script></head><body>nav noise</body></html>"""


class FakeHttp:
    def __init__(self):
        self.settings = {"request_timeout": 20}

    def wait(self, url):
        pass


class FakeResp:
    def __init__(self, status=200, json_data=None, text=""):
        self.status_code, self._json, self.text = status, json_data, text

    def json(self):
        return self._json


def _fetcher():
    return TalemetryFetcher({"name": "X", "slug": "x",
                             "careers_url": "https://x.com/"}, FakeHttp())


def test_jobposting_ld_tolerates_trailing_comma():
    ld = talemetry.jobposting_ld(SAMPLE_HTML)
    assert ld["title"] == "Head of Product"
    assert ld["employmentType"] == "FULL_TIME"


def test_jobposting_ld_none_when_absent():
    assert talemetry.jobposting_ld("<html><body>no ld</body></html>") is None


def test_detail_header_and_markdown():
    f = _fetcher()
    f._get = lambda url: FakeResp(text=SAMPLE_HTML)
    body = f.detail("https://x.com/jobs/1-head")
    assert "Employment type: Full time" in body     # FULL_TIME -> mapped
    assert "Date posted: 2026-06-19" in body
    assert "## About" in body
    assert "- Own the **product**" in body           # clean Markdown


def test_listing_builds_rows():
    f = _fetcher()
    f._get = lambda url: FakeResp(json_data={
        "total_entries": 1, "per_page": 100,
        "entries": [{"id": "abc", "permalink": "head-of-product",
                     "title": "Head of Product", "location": {"name": "London, United Kingdom"}}]})
    res = f.listing()
    assert res.status == "ok" and len(res.postings) == 1
    p = res.postings[0]
    assert p["url"] == "https://x.com/jobs/abc-head-of-product"
    assert p["location"] == "London,  United Kingdom" or "London" in p["location"]
    assert p["source_detail"] == "Talemetry"


def test_listing_blocked_on_403():
    f = _fetcher()
    f._get = lambda url: FakeResp(status=403)
    assert f.listing().status == "blocked"
