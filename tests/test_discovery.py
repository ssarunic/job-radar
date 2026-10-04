"""ATS discovery for `follow` — URL parsing (no network) + name probing (fake http)."""
from requests import HTTPError

from services import discovery


class FakeHttp:
    """get_json/post_json return canned data per URL substring, else raise 404."""
    def __init__(self, mapping):
        self.mapping = mapping

    def get_json(self, url, **kw):
        for needle, val in self.mapping.items():
            if needle in url:
                return val
        e = HTTPError("404")
        e.response = None
        raise e

    post_json = get_json


class _Resp:
    def __init__(self, text):
        self.text = text


class FakeHttpText:
    """get() returns a response with .text (for body-probe)."""
    def __init__(self, text):
        self._text = text

    def get(self, url, **kw):
        return _Resp(self._text)


class FakeHttpRaises:
    """get() raises, like a Cloudflare-blocked fetch."""
    def get(self, url, **kw):
        raise HTTPError("403")


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


def test_from_url_revolutpeople_tenant():
    d = discovery.discover(
        "https://revolutpeople.com/cleo/public/careers/position/abc", http=None)
    assert d["ats_type"] == "revolutpeople" and d["ats_slug"] == "cleo"
    assert d["careers_url"] == "https://revolutpeople.com/cleo/public/careers"


def test_from_url_revolut_own_careers():
    d = discovery.discover(
        "https://www.revolut.com/careers/position/6e84f229-b790/", http=None)
    assert d["ats_type"] == "revolutpeople" and d["ats_slug"] == "revolut"
    assert d["name"] == "Revolut"
    assert d["careers_url"] == "https://www.revolut.com/careers"


def test_from_url_unknown_is_custom():
    d = discovery.discover("https://tessl.io/careers", http=None)
    assert d["ats_type"] == "custom"


def test_from_url_body_probe_detects_talemetry():
    """#2: an unrecognised host whose body mentions Talemetry is detected."""
    http = FakeHttpText("<html>powered by Talemetry, Inc.</html>")
    d = discovery.discover("https://jobs.example.com/", http)
    assert d["ats_type"] == "talemetry"
    assert d["careers_url"] == "https://jobs.example.com"


def test_from_url_cloudflare_falls_back_to_custom():
    http = FakeHttpRaises()
    d = discovery.discover("https://jobs.natwestgroup.com/", http)
    assert d["ats_type"] == "custom"


def test_from_url_names_company_not_generic_subdomain():
    """careers.expediagroup.com was saved as "Careers" — unfindable in the list."""
    d = discovery.discover("https://careers.expediagroup.com/jobs/", FakeHttpRaises())
    assert d["name"] == "Expediagroup" and d["slug"] == "expediagroup"
    assert discovery._host_name("jobs.natwestgroup.com") == "Natwestgroup"
    assert discovery._host_name("www.tessl.io") == "Tessl"
    assert discovery._host_name("careers.acme.co.uk") == "Acme"


def test_from_url_body_probe_resolves_workday_board():
    """A branded careers page linking to Workday resolves to the Workday board —
    the adapter derives its cxs endpoint from that host, not the branded one."""
    link = "https://expedia.wd108.myworkdayjobs.com/en-US/search/introduceYourself"
    http = FakeHttpText(f'<a href="{link}">Join</a><a href="{link}">Join</a>')
    d = discovery.discover("https://careers.expediagroup.com/jobs/", http)
    assert d["ats_type"] == "workday"
    assert d["careers_url"] == "https://expedia.wd108.myworkdayjobs.com/search"
    assert d["name"] == "Expedia" and d["slug"] == "expedia"


def test_from_url_workday_job_link_collapses_to_board():
    d = discovery.discover(
        "https://expedia.wd108.myworkdayjobs.com/search/job/UK---London/"
        "Senior-Product-Manager--EG-Advertising_R-103969/apply", http=None)
    assert d["careers_url"] == "https://expedia.wd108.myworkdayjobs.com/search"
    assert d["name"] == "Expedia"


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


def test_from_name_probes_workable_last():
    http = FakeHttp({"workable.com/api/v3/accounts/cloudtalk/jobs": {"total": 7, "results": []}})
    d = discovery.discover("CloudTalk", http)
    assert d["ats_type"] == "workable" and d["ats_slug"] == "cloudtalk"
    assert d["careers_url"] == "https://apply.workable.com/cloudtalk/"


def test_workable_requires_postings():
    # Workable 200s some dormant accounts with total 0 -> must NOT match
    http = FakeHttp({"workable.com/api/v3/accounts/ghost/jobs": {"total": 0, "results": []}})
    assert discovery.discover("ghost", http) is None
