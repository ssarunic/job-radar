"""Workday listing-location resolution (_listing_location) — network-free."""
from scrapers.ats.workday import _listing_location


def test_prefers_locations_text():
    assert _listing_location(
        {"locationsText": "London, United Kingdom",
         "bulletFields": ["MANCHESTER, , UNITED KINGDOM", "JR1"]}) == "London, United Kingdom"


def test_falls_back_to_bullet_fields():
    # Worldpay-style: no locationsText at all, location in bulletFields[0]
    assert _listing_location(
        {"title": "Head of International Platforms Product",
         "bulletFields": ["LONDON, , UNITED KINGDOM", "JR0609782"]}) == "LONDON, , UNITED KINGDOM"


def test_skips_req_id_bullet_fields():
    # req id first: the location must still win, not the id
    assert _listing_location(
        {"bulletFields": ["JR0609782", "LONDON, , UNITED KINGDOM"]}) == "LONDON, , UNITED KINGDOM"
    assert _listing_location({"bulletFields": ["R-12345", "Remote, UK"]}) == "Remote, UK"
    assert _listing_location({"bulletFields": ["2024-1234", "Edinburgh"]}) == "Edinburgh"


def test_blank_locations_text_falls_through():
    assert _listing_location(
        {"locationsText": "   ", "bulletFields": ["Leeds, UK"]}) == "Leeds, UK"


def test_no_location_available():
    assert _listing_location({"title": "x"}) == ""
    assert _listing_location({"locationsText": None, "bulletFields": ["JR0609782"]}) == ""
