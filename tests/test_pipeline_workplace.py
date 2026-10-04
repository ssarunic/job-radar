"""Work-type filter: a role that *states* an unticked work type is dropped; one
that doesn't say is always kept."""
from datetime import date

from scrapers.ats import ashby
from services import pipeline

PROFILE = {"seniority_min": 3, "include_product_owner": True, "exclude_titles": [],
           "employment": ["Full time"], "recency_days": 3650, "max_roles_per_company": 10}


class _Fetcher:
    needs_detail = False

    def detail(self, url):
        return ""


def _row(n, **kw):
    return {"title": f"Senior Product Manager {n}", "location": "London", "description": "",
            "employment_type": "Full time", "salary_text": "", "url": f"https://x/jobs/{n}",
            "source_detail": "Ashby", **kw}


RAW = [_row("onsite", workplace="OnSite"),
       _row("hybrid", workplace="Hybrid"),
       _row("remote", workplace="Remote", location="London; Remote"),
       _row("texthybrid", description="We have a hybrid working policy."),
       _row("silent", description="hybrid cloud platforms; work remotely for 3 months a year")]


def _run(profile):
    kept = pipeline.process_company({"name": "X", "slug": "x"}, profile, RAW,
                                    _Fetcher(), {}, None, date(2026, 10, 4))
    return {k.title_raw.split()[-1]: k.workplace_model for k in kept}


def test_default_keeps_every_work_type():
    assert _run(PROFILE) == {"onsite": "On site", "hybrid": "Hybrid", "remote": "Remote",
                             "texthybrid": "Hybrid", "silent": "Not stated"}


def test_unticked_work_types_are_dropped_but_not_stated_is_kept():
    assert _run({**PROFILE, "workplace": ["Remote"]}) == {
        "remote": "Remote", "silent": "Not stated"}
    assert _run({**PROFILE, "workplace": ["On site", "Hybrid"]}) == {
        "onsite": "On site", "hybrid": "Hybrid", "texthybrid": "Hybrid", "silent": "Not stated"}


def test_allow_remote_false_still_drops_remote_roles():
    assert "remote" not in _run({**PROFILE, "allow_remote": False})


def test_contract_roles_kept_when_ticked():
    raw = [_row("perm"), _row("ftc", employment_type="Contract")]
    def titles(profile):
        return sorted(k.title_raw.split()[-1] for k in pipeline.process_company(
            {"name": "X", "slug": "x"}, profile, raw, _Fetcher(), {}, None, date(2026, 10, 4)))
    assert titles(PROFILE) == ["perm"]
    assert titles({**PROFILE, "employment": ["Full time", "Contract"]}) == ["ftc", "perm"]


def test_ashby_hybrid_role_is_not_labelled_remote():
    # Ashby sets isRemote on Hybrid roles too; only a Remote workplaceType (or the
    # flag with no type at all) may add the "Remote" location label.
    loc = ashby._locations
    assert loc({"location": "London", "isRemote": True, "workplaceType": "Hybrid"}) == "London"
    assert loc({"location": "London", "isRemote": True,
                "workplaceType": "Remote"}) == "London; Remote"
    assert loc({"location": "London", "isRemote": True}) == "London; Remote"
    assert loc({"location": "London", "isRemote": False, "workplaceType": "OnSite"}) == "London"
