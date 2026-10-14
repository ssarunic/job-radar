"""Location acceptance + multi-location expansion (product-spec §12)."""
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
    ("London", "We have a hybrid working policy.", "Hybrid"),
    ("London", "Location: London, UK (Hybrid, in-person 4 days per week)", "Hybrid"),
    ("London", "We expect employees to be in the office at least three days per week.", "Hybrid"),
    ("London", "expected to be in the London office two days per week", "Hybrid"),
    ("London", "You'll spend around 3 days per week in the office.", "Hybrid"),
    ("London", "You'll work from home some of the time", "Hybrid"),
    ("London", "We work 5 days a week in the office.", "On site"),
    ("London", "This is an office-based role.", "On site"),
    ("London", "Come take off with us! #LI-Remote", "Remote"),
    ("London", "This is a fully remote position.", "Remote"),
    ("London", "London or Remote in the UK | £100,000", "Remote"),
    ("Remote (UK)", "", "Remote"),
    ("UK - Remote", "If you live in London we have a hybrid approach", "Remote"),
    ("London ; Remote", "", "Remote"),
    ("London ; UK - Remote", "(this is a hybrid role)", "Hybrid"),
    # most ads never say — and that is not the same as on site
    ("London", "based in our office", "Not stated"),
    ("London", "", "Not stated"),
    # "hybrid" / "remote" used for something other than the working arrangement
    ("London", "platforms operating across hybrid cloud and on-premise environments", "Not stated"),
    ("London", "moving to a higher-contribution model (federated or hybrid)", "Not stated"),
    ("London", "experience working in hybrid technology environments", "Not stated"),
    ("London", '"Mobile Wise" — work remotely for 3 months each year', "Not stated"),
    ("London", "people working around the world, from our offices and remotely", "Not stated"),
    ("London", "Openness to periodic on-site embedding with business teams", "Not stated"),
])
def test_workplace_model(loc, desc, model):
    assert L.workplace_model(loc, desc) == model


@pytest.mark.parametrize("structured,model", [
    ("OnSite", "On site"), ("on-site", "On site"), ("on_site", "On site"),
    ("Hybrid", "Hybrid"), ("remote", "Remote"), ("TELECOMMUTE", "Remote"),
    ("Fully Remote", "Remote"),
])
def test_workplace_model_structured_value_wins(structured, model):
    # the ATS's own field beats both the location labels and the ad copy
    assert L.workplace_model("London ; Remote", "remote-first team", structured) == model
    assert L.normalise_workplace(structured) == model


def test_workplace_model_reads_detail_header_line():
    body = "Employment type: Full time\nWorkplace type: Hybrid\nLocation: LONDON\n\nAd."
    assert L.workplace_model("London", body) == "Hybrid"
    # an empty header (tenant doesn't fill the field) must not swallow the next line
    body = "Employment type: Full time\nWorkplace type: \nLocation: Remote hub\n\nAd."
    assert L.workplace_model("London", body) == "Not stated"
    assert L.normalise_workplace("unspecified") == ""


def test_allowed_workplaces_and_remote_gate():
    assert L.allowed_workplaces({}) == ["On site", "Hybrid", "Remote"]
    assert L.allowed_workplaces({"allow_remote": False}) == ["On site", "Hybrid"]
    assert L.allowed_workplaces({"workplace": ["Remote", "Hybrid"]}) == ["Hybrid", "Remote"]
    assert not L.remote_allowed({"workplace": ["On site", "Hybrid"]})
    # unticking Remote behaves exactly like allow_remote: false
    assert L.expand("London; Remote (UK)", {"workplace": ["On site", "Hybrid"]}) == ["London"]
    assert L.expand("Remote (UK)", {"workplace": ["On site"]}) == []


def test_split_locations_dedupes():
    assert L.split_locations("London; London") == ["London"]


def test_named_ineligible_remote_rejected_amid_uk_context():
    """#3 regression: 'Remote (USA)' must not ride in on a sibling London office."""
    assert L.expand("London; Remote (USA)", PROFILE) == ["London"]
    assert L.expand("London / Remote (Canada)", PROFILE) == ["London"]
    # an explicitly UK/EU remote alongside London is still kept
    assert "Remote (UK)" in L.expand("London; Remote (UK)", PROFILE)


# --- profile-driven geography (non-UK seekers) -----------------------------------

BERLIN = {"allow_remote": True, "location": {
    "home_terms": ["berlin", "germany", "munich"],
    "home_word_terms": ["de"],
    "home_generic": ["germany", "deutschland"],
    "home_city": "berlin",
    "remote_regions": ["germany", "europe", "emea", "eu "],
}}


def test_expand_home_terms_override():
    assert L.expand("Berlin; San Francisco", BERLIN) == ["Berlin"]
    assert L.expand("London", BERLIN) == []          # London is foreign to a Berlin profile


def test_expand_remote_regions_override():
    assert L.expand("Remote (Germany)", BERLIN) == ["Remote (Germany)"]
    assert L.expand("Remote (USA)", BERLIN) == []


def test_expand_generic_collapse_uses_profile():
    # country label collapses when the home city is present
    assert L.expand("Berlin; Germany", BERLIN) == ["Berlin"]


def test_defaults_unchanged_without_location_block():
    assert L.expand("London; New York", {"allow_remote": True}) == ["London"]


@pytest.mark.parametrize("raw,expected", [
    # Hopper (Ashby): every label is "<place> - Remote"; a remote pinned to a
    # non-UK/Europe place is not region-less and must be dropped.
    ("US - Remote; New York - Remote; Austin - Remote; Seattle - Remote", []),
    ("Brazil - Remote; Rio de Janeiro - Remote; São Paulo - Remote", []),
    ("Ontario - Remote; Toronto - Remote; Vancouver - Remote", []),
    ("Montréal - Remote", []),
    ("England - Remote; London - Remote", ["England - Remote", "London - Remote"]),
    ("Spain - Remote; Madrid - Remote; Barcelona - Remote", ["Spain - Remote"]),
    ("London; Austin - Remote", ["London"]),
    ("Remote - Denmark", ["Remote - Denmark"]),              # any EU country, not just the big five
    ("Poland - Remote OR Romania - Remote", ["Poland - Remote", "Romania - Remote"]),
    ("Remote - Georgia; Remote - Texas", []),                # US state, not the country
    ("Fully Remote", ["Fully Remote"]),
    ("Remote - Anywhere", ["Remote - Anywhere"]),
    ("Remote (Global)", ["Remote (Global)"]),
])
def test_remote_pinned_to_a_place(raw, expected):
    assert L.expand(raw, PROFILE) == expected
