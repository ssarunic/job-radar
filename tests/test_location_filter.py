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
    ("Remote (USA)", []),                                    # #3 named non-eligible region
    ("Remote - United States", []),
    ("Remote (Canada)", []),
    ("Remote (APAC)", []),
    ("Remote (India)", []),
])
def test_expand(raw, expected):
    assert L.expand(raw, PROFILE) == expected


def test_remote_with_eligible_region_named_is_kept():
    # explicit UK eligibility present -> kept even though a non-eligible region exists
    assert L.expand("Remote in the UK", PROFILE) == ["Remote in the UK"]
    assert L.expand("Remote (Europe)", PROFILE) == ["Remote (Europe)"]


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


def test_named_ineligible_remote_rejected_amid_uk_context():
    """#3 regression: 'Remote (USA)' must not ride in on a sibling London office."""
    assert L.expand("London; Remote (USA)", PROFILE) == ["London"]
    assert L.expand("London / Remote (Canada)", PROFILE) == ["London"]
    # an explicitly UK/EU remote alongside London is still kept
    assert "Remote (UK)" in L.expand("London; Remote (UK)", PROFILE)
