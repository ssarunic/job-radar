"""Location acceptance + multi-location expansion (README §12)."""
import pytest

from services import location_filter as L

PROFILE = {"allow_remote": True}


@pytest.mark.parametrize("raw,expected", [
    ("London, , United Kingdom", ["London"]),               # country collapsed
    ("London, , United Kingdom; Hybrid", ["London"]),
    ("Barcelona; London", ["London"]),                       # foreign city dropped
    ("Singapore, , Singapore", []),
    ("San Francisco; Remote", []),                           # US-remote rejected
    ("New York; Remote", []),
    ("US; Remote", []),
    ("Remote", ["Remote"]),                                  # region-less remote kept
    ("Remote (UK)", ["Remote (UK)"]),
    ("London; Remote (EMEA)", ["London", "Remote (EMEA)"]),
])
def test_expand(raw, expected):
    assert L.expand(raw, PROFILE) == expected


def test_remote_disabled():
    assert L.expand("Remote (UK)", {"allow_remote": False}) == []


def test_expand_caps_at_five_keeping_london_and_remote():
    raw = "London; Manchester; Edinburgh; Bristol; Leeds; Glasgow; Remote (UK)"
    out = L.expand(raw, PROFILE)
    assert len(out) <= 5
    assert any("london" in x.lower() for x in out)
    assert any("remote" in x.lower() for x in out)


@pytest.mark.parametrize("loc,desc,model", [
    ("London", "hybrid working", "Hybrid"),
    ("Remote (UK)", "", "Remote"),
    ("London", "based in our office", "On site"),
])
def test_workplace_model(loc, desc, model):
    assert L.workplace_model(loc, desc) == model


def test_split_locations_dedupes():
    assert L.split_locations("London; London") == ["London"]
