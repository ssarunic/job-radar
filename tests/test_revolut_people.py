"""Revolut People adapter — location parsing + paginated listing (Cleo), and the
__NEXT_DATA__ web variant for Revolut's own board (network-free via faked _get)."""
import json

from scrapers.ats.revolut_people import (
    RevolutPeopleFetcher,
    RevolutWebFetcher,
    _location,
    make_fetcher,
    next_data,
)


def test_location_joins_names_and_marks_remote():
    job = {"locations": [
        {"name": "United Kingdom", "type": "office", "country": {"name": "United Kingdom"}},
        {"name": "UK - Remote", "type": "remote", "country": {"name": "United Kingdom"}},
        {"name": "Spain", "type": "remote", "country": {"name": "Spain"}},
    ]}
    loc = _location(job)
    assert "United Kingdom" in loc
    assert "UK - Remote" in loc
    assert "Spain (remote)" in loc          # remote flag appended when not already named


class _Http:
    """Returns two pages of postings; pages.total drives pagination."""
    def __init__(self):
        self.calls = []

    def get_json(self, url, **kw):
        self.calls.append(url)
        page = int(url.rsplit("page=", 1)[1])
        if page == 1:
            return {"pages": {"total": 2, "page_size": 1}, "count": 2,
                    "results": [{"id": "a", "title": "Head of Product",
                                 "locations": [{"name": "United Kingdom", "type": "office"}]}]}
        return {"pages": {"total": 2, "page_size": 1}, "count": 2,
                "results": [{"id": "b", "title": "Director of Product",
                             "locations": [{"name": "UK - Remote", "type": "remote"}]}]}


def test_listing_paginates_and_shapes_rows():
    company = {"name": "Cleo AI", "slug": "cleo-ai", "ats_slug": "cleo",
               "careers_url": "https://revolutpeople.com/cleo/public/careers"}
    http = _Http()
    with RevolutPeopleFetcher(company, http) as f:
        res = f.listing()
    assert res.status == "ok"
    assert len(res.postings) == 2                 # both pages fetched
    assert len(http.calls) == 2
    titles = [p["title"] for p in res.postings]
    assert titles == ["Head of Product", "Director of Product"]
    assert res.postings[0]["url"].endswith("/cleo/public/careers/position/a")
    assert res.postings[0]["source_detail"] == "RevolutPeople"


def test_tenant_from_careers_url_when_no_ats_slug():
    f = RevolutPeopleFetcher(
        {"slug": "x", "careers_url": "https://revolutpeople.com/cleo/public/careers"}, None)
    assert f.tenant == "cleo"


class _DetailHttp:
    def get_json(self, url, **kw):
        assert "/external/v2/postings/" in url        # uses the v2 by-id endpoint
        return {"id": "abc", "title": "Head of Product",
                "description": "<h3>About</h3><ul><li>Own the <strong>product</strong></li></ul>"}


def test_detail_fetches_and_converts_to_markdown():
    f = RevolutPeopleFetcher(
        {"slug": "cleo-ai", "ats_slug": "cleo",
         "careers_url": "https://revolutpeople.com/cleo/public/careers"}, _DetailHttp())
    md = f.detail("https://revolutpeople.com/cleo/public/careers/position/abc")
    assert "### About" in md
    assert "- Own the **product**" in md


def test_detail_empty_url():
    f = RevolutPeopleFetcher({"slug": "x", "ats_slug": "cleo",
                              "careers_url": "https://revolutpeople.com/cleo/public/careers"}, None)
    assert f.detail("") == ""


# --- web variant (www.revolut.com/careers) --------------------------------------

def _next_page(page_props: dict) -> str:
    blob = json.dumps({"props": {"pageProps": page_props}})
    return ('<html><head><script id="__NEXT_DATA__" type="application/json">'
            f"{blob}</script></head><body></body></html>")


class _FakeHttp:
    def __init__(self):
        self.settings = {"request_timeout": 20}
        self.waited = []

    def wait(self, url):
        self.waited.append(url)


class _FakeResp:
    def __init__(self, status=200, text=""):
        self.status_code, self.text = status, text


def _web_fetcher():
    return RevolutWebFetcher({"name": "Revolut", "slug": "revolut",
                              "careers_url": "https://www.revolut.com/careers"},
                             _FakeHttp())


def test_make_fetcher_picks_class_by_host():
    api = make_fetcher({"slug": "cleo-ai", "ats_slug": "cleo",
                        "careers_url": "https://revolutpeople.com/cleo/public/careers"},
                       _FakeHttp())
    web = make_fetcher({"slug": "revolut",
                        "careers_url": "https://www.revolut.com/careers"}, _FakeHttp())
    assert isinstance(api, RevolutPeopleFetcher)
    assert isinstance(web, RevolutWebFetcher)


def test_next_data_absent_or_invalid_is_empty():
    assert next_data("<html><body>no data</body></html>") == {}
    assert next_data('<script id="__NEXT_DATA__" type="application/json">'
                     "{broken</script>") == {}


def test_web_listing_maps_positions():
    f = _web_fetcher()
    f._get = lambda url: _FakeResp(text=_next_page({"positions": [
        {"id": "6e84f229", "text": "Entrepreneur in Residence",
         "locations": [{"name": "London", "type": "office", "country": "United Kingdom"},
                       {"name": "UK - Remote", "type": "remote", "country": "United Kingdom"}]},
        {"id": None, "text": "ghost entry"},          # no id -> dropped
    ]}))
    res = f.listing()
    assert res.status == "ok"
    assert len(res.postings) == 1
    row = res.postings[0]
    assert row["title"] == "Entrepreneur in Residence"
    assert row["location"] == "London; UK - Remote"
    assert row["url"] == "https://www.revolut.com/careers/position/6e84f229/"
    assert row["source_detail"] == "RevolutPeople"


def test_web_listing_403_is_blocked_and_500_is_error():
    f = _web_fetcher()
    f._get = lambda url: _FakeResp(status=403)
    assert f.listing().status == "blocked"
    f._get = lambda url: _FakeResp(status=500)
    assert f.listing().status == "error"


def test_web_listing_no_positions_is_empty():
    f = _web_fetcher()
    f._get = lambda url: _FakeResp(text=_next_page({"positions": []}))
    assert f.listing().status == "empty"


def test_web_detail_markdown_and_string_country_location():
    f = _web_fetcher()
    f._get = lambda url: _FakeResp(text=_next_page({"position": {
        "id": "abc", "text": "Entrepreneur in Residence",
        "description": "<h3>About</h3><ul><li>Own the <strong>bet</strong></li></ul>"}}))
    md = f.detail("https://www.revolut.com/careers/position/abc/")
    assert "### About" in md
    assert "- Own the **bet**" in md
    # plain-string country (web shape) must not crash _location
    assert _location({"locations": [{"type": "remote", "country": "Spain"}]}) == \
        "Spain (remote)"


def test_web_detail_error_paths_return_empty():
    f = _web_fetcher()
    assert f.detail("") == ""
    f._get = lambda url: _FakeResp(status=404)
    assert f.detail("https://www.revolut.com/careers/position/abc/") == ""
    def _boom(url):
        raise RuntimeError("net down")
    f._get = _boom
    assert f.detail("https://www.revolut.com/careers/position/abc/") == ""
