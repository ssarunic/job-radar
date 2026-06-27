"""Ladder attempt loop + rung planning (#1)."""
from scrapers.ladder import _attempt, _build_rungs
from scrapers.result import ListingResult, OK, EMPTY, BLOCKED, ERROR


class FakeHttp:
    def __init__(self, allowed=True):
        self._allowed = allowed

    def allowed(self, url):
        return self._allowed

    def wait(self, url):
        pass


class FakeFetcher:
    def __init__(self, result, name="r", check_robots=False):
        self.result, self.rung_name, self.check_robots = result, name, check_robots
        self.careers_url = "http://x"
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.closed = True
        return False

    def listing(self):
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _factory(result, **kw):
    created = []

    def make():
        f = FakeFetcher(result, **kw)
        created.append(f)
        return f
    make.created = created
    return make


def test_primary_ok_skips_fallbacks():
    fb = _factory(ListingResult(OK, [{}], "fb"))
    f, res = _attempt(FakeHttp(), [(True, _factory(ListingResult(OK, [{"t": 1}], "primary"))),
                                   (False, fb)])
    assert res.status == OK and res.rung == "primary"
    assert fb.created == []          # fallback never constructed
    assert f is not None and not f.closed   # winner left open for detail


def test_blocked_primary_falls_through():
    prim = _factory(ListingResult(BLOCKED, [], "primary"))
    f, res = _attempt(FakeHttp(), [(True, prim),
                                   (False, _factory(ListingResult(OK, [{}], "fb")))])
    assert res.status == OK and res.rung == "fb"
    assert prim.created[0].closed   # failed primary was closed


def test_error_primary_falls_through():
    f, res = _attempt(FakeHttp(), [(True, _factory(RuntimeError("boom"), name="primary")),
                                   (False, _factory(ListingResult(OK, [{}], "fb")))])
    assert res.status == OK and res.rung == "fb"


def test_ats_empty_is_terminal():
    fb = _factory(ListingResult(OK, [{}], "fb"))
    f, res = _attempt(FakeHttp(), [(True, _factory(ListingResult(EMPTY, [], "primary"))),
                                   (False, fb)])
    assert res.status == EMPTY and res.rung == "primary"
    assert fb.created == []          # trusted empty -> no fallback
    assert f is None


def test_discovery_empty_continues():
    f, res = _attempt(FakeHttp(), [(False, _factory(ListingResult(EMPTY, [], "playwright"))),
                                   (False, _factory(ListingResult(OK, [{}], "static")))])
    assert res.status == OK and res.rung == "static"


def test_all_empty_returns_empty():
    f, res = _attempt(FakeHttp(), [(False, _factory(ListingResult(EMPTY, [], "playwright"))),
                                   (False, _factory(ListingResult(EMPTY, [], "static")))])
    assert res.status == EMPTY and f is None


def test_robots_disallow_blocks_rung():
    f, res = _attempt(FakeHttp(allowed=False),
                      [(False, _factory(ListingResult(OK, [{}], "static"), check_robots=True))])
    assert res.status == BLOCKED and "robots" in res.error.lower()


def test_no_rungs_returns_error():
    f, res = _attempt(FakeHttp(), [])
    assert res.status == ERROR and f is None


def test_build_rungs_ats_has_fallbacks_terminal_on_empty():
    rungs = _build_rungs({"ats_type": "greenhouse", "slug": "x", "careers_url": "u"},
                         {}, FakeHttp())
    assert len(rungs) == 3
    assert rungs[0][0] is True        # ATS primary: empty is terminal


def test_build_rungs_custom_is_discovery_only():
    rungs = _build_rungs({"ats_type": "custom", "slug": "x", "careers_url": "u"},
                         {}, FakeHttp())
    assert len(rungs) == 2
    assert rungs[0][0] is False       # discovery: keep trying on empty
