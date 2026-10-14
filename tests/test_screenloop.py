"""Screenloop adapter — network-free, against canned board/job HTML."""
import html as _html
import json

from scrapers.ats.screenloop import (
    ScreenloopFetcher,
    _location,
    board_url,
    parse_board,
    parse_job,
    react_props,
    slug_from_url,
)
from scrapers.ladder import _build_rungs, detect_ats
from scrapers.result import EMPTY, OK
from services import discovery

BOARD = "https://app.screenloop.com/careers/homesearch"
JOB = "https://app.screenloop.com/careers/homesearch/job_posts/8985"


def _page(component: str, props: dict) -> str:
    """A Screenloop page: Rails HTML whose React root is hydrated from an
    entity-escaped JSON attribute (exactly how the live pages ship)."""
    return (f'<html><body><div data-react-class="{component}" '
            f'data-react-props="{_html.escape(json.dumps(props), quote=True)}" '
            'data-react-cache-id="x-0"></div></body></html>')


LONDON = {"id": 1306, "name": "London - HQ", "address": None, "city": "London",
          "country": "United Kingdom of Great Britain and Northern Ireland",
          "countryCode": "GB", "state": "England", "stateCode": "GB-ENG"}

BOARD_PROPS = {
    "companyInfo": {"organizationId": 469, "name": "Homesearch", "subdomain": "homesearch"},
    "jobPosts": [
        {"id": 8985, "name": "Head of Product", "location": LONDON,
         "job": {"id": 14961, "name": "Head of Product", "department": {"name": "Product"}}},
        {"id": 8971, "name": "Backend Engineer", "location": LONDON,
         "job": {"id": 14947, "name": "Backend Engineer", "department": {"name": "Tech"}}},
        {"id": 7430, "name": "Join Our Talent Pool",
         "location": {"id": 783, "name": "Head Office", "city": None,
                      "country": "United Kingdom of Great Britain and Northern Ireland",
                      "countryCode": "GB"},
         "job": {"id": 13381, "name": "Join Our Talent Pool"}},
    ],
}

JOB_PROPS = {
    "previewMode": False,
    "companyInfo": {"name": "Homesearch", "subdomain": "homesearch"},
    "previewJobPost": {"name": "Head of Product", "department": "Product",
                       "location": "London - HQ", "locationType": "Hybrid",
                       "employmentType": "Full time", "jobPostId": 8985,
                       "status": "published", "salary": None},
    "jobPostHtmlString": ('<p dir="ltr"><b><strong>👋 About Us</strong></b></p>'
                          '<p>We&#39;re a team of around 40.</p>'
                          '<h2><b><strong>😊 About You</strong></b></h2>'
                          '<ul><li value="1"><span>You&#39;ve owned product strategy.</span></li>'
                          '<li value="2"><span>You&#39;ve led people.</span></li></ul>'),
}


class FakeHttp:
    """get() serves canned HTML per URL substring, else raises like a 404."""
    def __init__(self, pages):
        self.pages, self.gets = pages, []

    def get(self, url, **kw):
        self.gets.append(url)
        for needle, text in self.pages.items():
            if needle in url:
                return type("R", (), {"text": text})()
        raise RuntimeError("404")


def test_urls():
    assert slug_from_url(JOB) == "homesearch"
    assert slug_from_url(BOARD + "/") == "homesearch"
    assert slug_from_url("https://app.screenloop.com/") == ""
    assert board_url(JOB) == BOARD
    assert board_url(JOB + "?tab=overview") == BOARD


def test_react_props_round_trips_escaped_json():
    assert react_props(_page("x/Y", {"a": "it&#39;s <b>"}), "x/Y") == {"a": "it&#39;s <b>"}
    assert react_props("<html></html>", "x/Y") is None
    assert react_props('<div data-react-class="x/Y" data-react-props="{nope">', "x/Y") is None


def test_location_short_names_the_country_and_falls_back_to_office_label():
    assert _location(LONDON) == "London, United Kingdom"
    assert _location({"name": "Head Office", "city": None, "countryCode": "GB"}) \
        == "Head Office, United Kingdom"
    assert _location({"city": "Lisbon", "country": "Portugal", "countryCode": "PT"}) \
        == "Lisbon, Portugal"
    assert _location(None) == ""


def test_board_maps_fields():
    rows = parse_board(_page("applicant_tracking/Careers/CareersPage", BOARD_PROPS), "homesearch")
    assert [r["title"] for r in rows] == ["Head of Product", "Backend Engineer",
                                          "Join Our Talent Pool"]
    head = rows[0]
    assert head["url"] == JOB
    assert head["location"] == "London, United Kingdom"
    assert head["posted_date"] is None and head["description"] == ""
    assert head["source_type"] == "ATS" and head["source_detail"] == "Screenloop"
    assert rows[2]["location"] == "Head Office, United Kingdom"
    assert parse_board("<html></html>", "homesearch") == []


def test_job_page_prepends_header_lines_and_converts_body():
    md = parse_job(_page("applicant_tracking/Jobs/JobPostPage", JOB_PROPS))
    assert md.startswith("Employment type: Full time\nWorkplace type: Hybrid\n\n")
    assert "Salary:" not in md
    assert "**👋 About Us**" in md and "We're a team of around 40." in md
    assert "## **😊 About You**" in md
    assert "- You've owned product strategy." in md
    assert parse_job("<html></html>") == ""


def test_job_page_salary_line_when_present():
    props = {**JOB_PROPS, "previewJobPost": {**JOB_PROPS["previewJobPost"],
                                             "salary": "£120,000 - £140,000"}}
    md = parse_job(_page("applicant_tracking/Jobs/JobPostPage", props))
    assert "Salary: £120,000 - £140,000\n" in md


def test_fetcher_listing_and_detail():
    http = FakeHttp({"/job_posts/8985": _page("applicant_tracking/Jobs/JobPostPage", JOB_PROPS),
                     "/careers/homesearch": _page("applicant_tracking/Careers/CareersPage",
                                                  BOARD_PROPS)})
    company = {"slug": "homesearch", "ats_slug": "", "ats_type": "screenloop",
               "careers_url": JOB}
    with ScreenloopFetcher(company, http) as f:
        assert f.careers_url == BOARD          # deep link collapses to the board
        res = f.listing()
        assert res.status == OK and res.postings[0]["title"] == "Head of Product"
        assert http.gets == [BOARD]
        assert "Workplace type: Hybrid" in f.detail(JOB)
        assert f.detail("") == ""
    empty = FakeHttp({"/careers/homesearch": _page("applicant_tracking/Careers/CareersPage",
                                                   {"jobPosts": []})})
    assert ScreenloopFetcher(company, empty).listing().status == EMPTY


def test_ladder_registers_screenloop_as_terminal_html_rung():
    company = {"slug": "homesearch", "ats_slug": "homesearch", "ats_type": "screenloop",
               "careers_url": BOARD}
    rungs = _build_rungs(company, {}, FakeHttp({}))
    terminal, factory = rungs[0]
    f = factory()
    assert terminal and f.rung_name == "screenloop"
    assert f.live_listing and f.check_robots and f.needs_detail
    assert len(rungs) == 3                      # playwright + static fallbacks


def test_detect_ats_from_url_and_body():
    class Http:
        def get(self, url, **kw):
            return type("R", (), {"text": '<a href="https://app.screenloop.com/careers/x">'})()
    assert detect_ats({"careers_url": BOARD}, Http()) == "screenloop"
    assert detect_ats({"careers_url": "https://www.homesearch.co.uk/careers"}, Http()) \
        == "screenloop"


def test_discovery_from_url_forms():
    for url in (BOARD, BOARD + "/", JOB, JOB + "?tab=overview"):
        d = discovery.discover(url, http=None)
        assert d["ats_type"] == "screenloop" and d["ats_slug"] == "homesearch", url
        assert d["careers_url"] == BOARD and d["slug"] == "homesearch"
        assert d["name"] == "Homesearch"


def test_discovery_by_name_probes_the_board_html_last():
    class Http(FakeHttp):
        def get_json(self, url, **kw):
            raise RuntimeError("404")
        post_json = get_json
    http = Http({"/careers/homesearch": _page("applicant_tracking/Careers/CareersPage",
                                              BOARD_PROPS)})
    d = discovery.discover("Homesearch", http)
    assert d["ats_type"] == "screenloop" and d["ats_slug"] == "homesearch"
    assert d["careers_url"] == BOARD
    # a board that exists but lists nothing must not match
    dormant = Http({"/careers/ghost": _page("applicant_tracking/Careers/CareersPage",
                                            {"jobPosts": []})})
    assert discovery.discover("ghost", dormant) is None
