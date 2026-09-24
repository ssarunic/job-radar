"""Body-stated grades (product-spec §11.7): a bank's Workday ad titles the bare
job family and states the grade in the body ("Vice President Expectations")."""
from datetime import date

from services import pipeline

PROFILE = {"seniority_min": 3, "include_product_owner": True, "exclude_titles": [],
           "locations": ["London"], "allow_remote": True, "employment": ["Full time"],
           "recency_days": 3650, "max_roles_per_company": 10}

BODIES = {
    "u/senior": "Purpose of the role…\nVice President Expectations\nTo contribute or set strategy…",
    "u/payables": "Purpose of the role…\nDirector Expectations\nProvide expert advice…",
    "u/cashflow": "Purpose of the role…\nAssistant Vice President Expectations\n…",
    "u/owner": "Purpose of the role…\nDirector Expectations\n…",
}


class _BankFetcher:
    needs_detail = True
    grades_in_body = True

    def __init__(self):
        self.fetched = []

    def detail(self, url):
        self.fetched.append(url)
        return BODIES[url]


def _raw(title, url):
    return {"title": title, "location": "London", "description": "", "url": url,
            "source_detail": "Workday"}


def _run(fetcher, raw, profile=PROFILE):
    return pipeline.process_company({"name": "Barclays", "slug": "barclays"}, profile, raw,
                                    fetcher, {}, None, date(2026, 9, 24))


def test_body_grade_lifts_rank_and_rescues_below_floor_titles():
    f = _BankFetcher()
    kept = _run(f, [
        _raw("Senior Product & Proposition Manager", "u/senior"),      # rank 3 -> VP 8
        _raw("Product and Proposition Manager - Payables", "u/payables"),  # rank 2 -> Director 7
        _raw("Product and Proposition Manager - Cashflow", "u/cashflow"),  # rank 2, AVP -> dropped
    ])
    by_url = {j.job_ad_url: j for j in kept}
    assert set(by_url) == {"u/senior", "u/payables"}
    senior, payables = by_url["u/senior"], by_url["u/payables"]
    assert (senior.seniority_rank, senior.seniority_level) == (8, "VP")
    assert senior.title_normalised == "VP Product"
    assert (payables.seniority_rank, payables.title_normalised) == (7, "Director of Product")
    # provisional rows are re-judged on the detail text, so each is fetched once
    assert sorted(f.fetched) == ["u/cashflow", "u/payables", "u/senior"]


def test_provisional_rows_rank_last_so_they_are_fetched_after_kept_titles():
    f = _BankFetcher()
    _run(f, [
        _raw("Product and Proposition Manager - Payables", "u/payables"),
        _raw("Senior Product & Proposition Manager", "u/senior"),
    ])
    assert f.fetched == ["u/senior", "u/payables"]


def test_product_owner_exclusion_is_not_overridden_by_body_grade():
    """A user-level opt-out (include_product_owner: false) is not a floor drop, so
    the row is never fetched — no grade can rescue it."""
    f = _BankFetcher()
    kept = _run(f, [_raw("Product Owner", "u/owner")],
                {**PROFILE, "include_product_owner": False})
    assert kept == [] and f.fetched == []


def test_adapters_without_body_grades_are_unchanged():
    class _Plain(_BankFetcher):
        grades_in_body = False

    f = _Plain()
    kept = _run(f, [
        _raw("Senior Product & Proposition Manager", "u/senior"),
        _raw("Product and Proposition Manager - Payables", "u/payables"),
    ])
    assert [j.job_ad_url for j in kept] == ["u/senior"]
    assert kept[0].seniority_rank == 3          # body grade not applied
    assert f.fetched == ["u/senior"]            # below-floor title never fetched
