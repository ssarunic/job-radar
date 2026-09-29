"""Workable adapter — network-free, against a canned JSON client."""
from scrapers.ats import workable
from scrapers.ats.workable import _location, fetch_detail, fetch_listing, parse_job_url
from scrapers.ladder import _build_rungs, detect_ats
from scrapers.result import EMPTY, OK
from services import discovery


def _loc(country, city="", code=None):
    return {"country": country, "countryCode": code or country[:2].upper(),
            "city": city, "region": None, "hidden": True}


DIRECTOR = {
    "id": 5617553, "shortcode": "4BE1A55963", "title": "Director of Product",
    "remote": True, "workplace": "remote",
    "location": _loc("Spain"),
    "locations": [_loc("Spain"), _loc("Czechia"), _loc("United Kingdom", code="GB"),
                  _loc("Ireland"), _loc("Portugal"), _loc("Netherlands")],
    "state": "published", "isInternal": False, "published": "2026-07-27T00:00:00.000Z",
    "department": ["Product"],
}
ONSITE_PM = {
    "id": 2, "shortcode": "AAA111BBB2", "title": "Senior Product Manager",
    "remote": False, "workplace": "on_site",
    "location": _loc("United Kingdom", city="London", code="GB"),
    "locations": [_loc("United Kingdom", city="London", code="GB")],
    "state": "published", "isInternal": False, "published": "2026-08-25T00:00:00.000Z",
}
DRAFT = {"id": 3, "shortcode": "DRAFT00001", "title": "Draft", "state": "draft",
         "locations": [], "location": {}}
INTERNAL = {"id": 4, "shortcode": "INTERN0001", "title": "Internal", "state": "published",
            "isInternal": True, "locations": [], "location": {}}

DETAIL = {
    "shortcode": "4BE1A55963", "title": "Director of Product", "state": "published",
    "description": ("<p><strong>Remote in Europe</strong></p>"
                    "<h3>The Mission</h3><p>Lead product.</p>"),
    "requirements": "<ul><li>8+ years in product</li></ul>",
    "benefits": "<p>Equity.</p>",
}


class FakeHttp:
    """post_json serves listing pages keyed by the request token; get_json the detail."""
    def __init__(self, pages, detail=None):
        self.pages, self.detail = pages, detail or {}
        self.posts, self.gets = [], []

    def post_json(self, url, **kw):
        self.posts.append((url, kw.get("json")))
        token = (kw.get("json") or {}).get("token")
        return self.pages[token]

    def get_json(self, url, **kw):
        self.gets.append(url)
        return self.detail


def test_listing_maps_fields_and_skips_unlisted():
    http = FakeHttp({None: {"total": 4, "results": [DIRECTOR, ONSITE_PM, DRAFT, INTERNAL]}})
    rows = fetch_listing("cloudtalk", http)
    assert [r["title"] for r in rows] == ["Director of Product", "Senior Product Manager"]
    d = rows[0]
    assert d["url"] == "https://apply.workable.com/cloudtalk/j/4BE1A55963/"
    assert d["posted_date"] == "2026-07-27T00:00:00.000Z"
    assert d["freshness_date"] == d["posted_date"]
    assert d["source_type"] == "ATS" and d["source_detail"] == "Workable"
    assert d["description"] == ""          # body comes from detail
    assert http.posts[0][0] == "https://apply.workable.com/api/v3/accounts/cloudtalk/jobs"
    assert "token" not in http.posts[0][1]


def test_location_remote_lists_every_country():
    assert _location(DIRECTOR) == ("Remote — Spain; Remote — Czechia; Remote — United Kingdom; "
                                   "Remote — Ireland; Remote — Portugal; Remote — Netherlands")
    assert _location(ONSITE_PM) == "London, United Kingdom"
    assert _location({"remote": True, "locations": [], "location": {}}) == "Remote"
    # falls back to the primary location when locations[] is missing
    assert _location({"remote": False, "location": _loc("Ireland", city="Dublin")}) \
        == "Dublin, Ireland"


def test_listing_follows_next_page_token_and_stops_at_total():
    p1 = {"total": 2, "results": [DIRECTOR], "nextPage": "tok1"}
    # the API keeps issuing a token even once every result has been served
    p2 = {"total": 2, "results": [ONSITE_PM], "nextPage": "tok2"}
    http = FakeHttp({None: p1, "tok1": p2})
    rows = fetch_listing("cloudtalk", http)
    codes = [r["url"].rstrip("/").rsplit("/", 1)[-1] for r in rows]
    assert codes == ["4BE1A55963", "AAA111BBB2"]
    assert [t for _, body in http.posts for t in [body.get("token")]] == [None, "tok1"]


def test_listing_stops_on_empty_page():
    http = FakeHttp({None: {"total": 5, "results": [], "nextPage": "tok"}})
    assert fetch_listing("x", http) == []
    assert len(http.posts) == 1


def test_parse_job_url():
    assert parse_job_url("https://apply.workable.com/cloudtalk/j/4BE1A55963/") \
        == ("cloudtalk", "4BE1A55963")
    assert parse_job_url("https://apply.workable.com/cloudtalk/j/4BE1A55963") \
        == ("cloudtalk", "4BE1A55963")
    assert parse_job_url("https://apply.workable.com/cloudtalk/") is None


def test_detail_composes_labelled_sections():
    http = FakeHttp({}, detail=DETAIL)
    md = fetch_detail("https://apply.workable.com/cloudtalk/j/4BE1A55963/", http)
    assert http.gets == ["https://apply.workable.com/api/v2/accounts/cloudtalk/jobs/4BE1A55963"]
    assert "Remote in Europe" in md and "Lead product." in md
    assert "## Requirements" in md and "8+ years in product" in md
    assert "## Benefits" in md and "Equity." in md
    assert fetch_detail("https://example.com/nope", http) == ""


def test_ladder_registers_workable_as_api_rung():
    assert workable.NEEDS_DETAIL is True
    http = FakeHttp({None: {"total": 1, "results": [DIRECTOR]}})
    company = {"slug": "cloudtalk", "ats_slug": "cloudtalk", "ats_type": "workable",
               "careers_url": "https://apply.workable.com/cloudtalk/"}
    rungs = _build_rungs(company, {}, http)
    terminal, factory = rungs[0]
    fetcher = factory()
    assert terminal and fetcher.rung_name == "workable" and fetcher.live_listing
    res = fetcher.listing()
    assert res.status == OK and res.postings[0]["title"] == "Director of Product"
    assert fetcher.detail("https://apply.workable.com/cloudtalk/j/4BE1A55963/") == ""
    http.pages[None] = {"total": 0, "results": []}
    assert fetcher.listing().status == EMPTY


def test_detect_ats_from_url_and_body():
    class Http:
        def get(self, url, **kw):
            return type("R", (), {"text": '<iframe src="https://apply.workable.com/embed/x">'})()
    assert detect_ats({"careers_url": "https://apply.workable.com/cloudtalk/"}, Http()) \
        == "workable"
    assert detect_ats({"careers_url": "https://www.cloudtalk.io/careers"}, Http()) == "workable"


def test_discovery_from_url_forms():
    d = discovery.discover("https://apply.workable.com/cloudtalk/j/4BE1A55963", http=None)
    assert d["ats_type"] == "workable" and d["ats_slug"] == "cloudtalk"
    assert d["careers_url"] == "https://apply.workable.com/cloudtalk/"
    assert d["slug"] == "cloudtalk"
    d = discovery.discover("https://cloudtalk.workable.com/", http=None)
    assert d["ats_type"] == "workable" and d["ats_slug"] == "cloudtalk"
