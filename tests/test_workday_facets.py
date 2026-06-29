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


def test_falls_back_to_city_sites():
    param, ids = _pick_uk_facet(BARCLAYS)
    assert param == "locations" and set(ids) == {"l1", "l2"}


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
