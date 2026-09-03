"""Workday UK-facet discovery (_pick_uk_facet) — network-free."""
from scrapers.ats.workday import _pick_uk_facet

# NVIDIA-style: nested location facet with a country-level 'United Kingdom'
NVIDIA = [
    {"facetParameter": "jobFamilyGroup", "descriptor": "Job Category",
     "values": [{"id": "eng", "descriptor": "Engineering", "count": 1337}]},
    {"facetParameter": "locationMainGroup", "descriptor": "Location", "values": [
        {"facetParameter": "locationHierarchy1", "descriptor": "Locations", "values": [
            {"id": "uk", "descriptor": "United Kingdom", "count": 42},
            {"id": "us", "descriptor": "United States of America", "count": 1500}]},
        {"facetParameter": "locations", "descriptor": "Sites", "values": [
            {"id": "site", "descriptor": "UK, London", "count": 20}]}]}]

# Barclays-style: only city/site values, no country node
BARCLAYS = [
    {"facetParameter": "locations", "descriptor": "Locations", "values": [
        {"id": "l1", "descriptor": "London, One Canada Square", "count": 1},
        {"id": "l2", "descriptor": "London, Luke Street (Eagle Lab)", "count": 1},
        {"id": "sf", "descriptor": "San Francisco, CA", "count": 9}]}]


def test_prefers_country_level_over_sites():
    param, ids = _pick_uk_facet(NVIDIA)
    assert param == "locationHierarchy1" and ids == ["uk"]   # country, not the 'UK, London' site


def test_site_only_tenant_gets_no_facet():
    # Barclays-style trees have no country node; site names are street addresses
    # ('Canary Wharf, 1 Churchill Place', 'Glasgow Campus') so a UK regex over
    # sites keeps almost nothing. Correct answer: no facet, page unfiltered.
    assert _pick_uk_facet(BARCLAYS) == (None, None)


def test_street_name_london_is_not_a_uk_facet():
    # Real Barclays descriptors (2026-09): the only 'London' matches were a street
    # name and one Eagle Lab; applying them collapsed 778 rows to 2.
    real = [{"facetParameter": "locationMainGroup", "descriptor": None, "values": [
        {"facetParameter": "locations", "descriptor": "Locations", "values": [
            {"id": "a", "descriptor": "Lowestoft, London Road North", "count": 1},
            {"id": "b", "descriptor": "London, Luke Street (Eagle Lab)", "count": 1},
            {"id": "c", "descriptor": "Canary Wharf, 1 Churchill Place", "count": 210},
            {"id": "d", "descriptor": "Glasgow Campus", "count": 60}]}]}]
    assert _pick_uk_facet(real) == (None, None)


def test_no_uk_returns_none():
    assert _pick_uk_facet(
        [{"facetParameter": "locations", "descriptor": "Loc",
          "values": [{"id": "x", "descriptor": "San Francisco, CA", "count": 9}]}]) == (None, None)


def test_excludes_bare_uk_false_positives():
    # 'Ukraine' / 'Dukinfield' must NOT match (bare 'uk' is excluded)
    assert _pick_uk_facet(
        [{"facetParameter": "locations", "descriptor": "Loc", "values": [
            {"id": "u", "descriptor": "Ukraine", "count": 3},
            {"id": "d", "descriptor": "Dukinfield", "count": 1}]}]) == (None, None)
