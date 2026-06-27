"""Ashby structured compensation extraction + pipeline preference."""
from datetime import date

from scrapers.ats.ashby import _salary
from services import pipeline


def _job(components, summary="£140K – £170K • Offers Equity"):
    return {"compensation": {"compensationTierSummary": summary,
                             "summaryComponents": components}}


SALARY = {"compensationType": "Salary", "currencyCode": "GBP",
          "minValue": 140000, "maxValue": 170000}
EQUITY = {"compensationType": "EquityPercentage", "minValue": None}
BONUS = {"compensationType": "Bonus", "currencyCode": "GBP",
         "minValue": 10000, "maxValue": 20000}


def test_salary_extracted():
    s = _salary(_job([SALARY, EQUITY]))
    assert (s["min"], s["max"], s["currency"]) == (140000, 170000, "GBP")
    assert s["original_text"] == "£140K – £170K • Offers Equity"
    assert s["compensation_type"] == "Base Only"   # equity doesn't change the enum


def test_bonus_sets_base_plus_bonus():
    assert _salary(_job([SALARY, BONUS]))["compensation_type"] == "Base+Bonus"


def test_no_salary_component_returns_none():
    assert _salary(_job([EQUITY])) is None
    assert _salary({}) is None


class _Fetcher:
    needs_detail = False

    def detail(self, url):
        return ""


def test_pipeline_prefers_ats_salary_over_text():
    profile = {"roles": [], "seniority_min": 3, "include_product_owner": True,
               "exclude_titles": [], "locations": ["London"], "allow_remote": True,
               "employment": ["Full time"], "recency_days": 3650,
               "max_roles_per_company": 10}
    raw = [{
        "title": "Head of Product", "location": "London",
        "description": "Comp: top of market. Learning budget £1,000.",
        "salary_text": "Comp: top of market. Learning budget £1,000.",
        "salary": {"min": 140000, "max": 170000, "currency": "GBP",
                   "original_text": "£140K – £170K • Offers Equity",
                   "compensation_type": "Base Only"},
        "url": "https://jobs.ashbyhq.com/capsa/abc", "source_detail": "Ashby",
    }]
    kept = pipeline.process_company({"name": "Capsa", "slug": "capsa"}, profile, raw,
                                    _Fetcher(), {}, None, date(2026, 6, 27))
    assert len(kept) == 1
    jp = kept[0]
    assert (jp.salary.min, jp.salary.max, jp.salary.currency) == (140000, 170000, "GBP")
    assert jp.salary.original_text == "£140K – £170K • Offers Equity"
