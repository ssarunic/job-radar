"""Revolut People adapter — location parsing + paginated listing (Cleo)."""
from scrapers.ats.revolut_people import RevolutPeopleFetcher, _location


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
