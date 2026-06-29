"""Pipeline must not let a run of contract roles bury an eligible one (review P2)."""
from datetime import date

from services import pipeline

PROFILE = {"seniority_min": 3, "include_product_owner": True, "exclude_titles": [],
           "locations": ["London"], "allow_remote": True, "employment": ["Full time"],
           "recency_days": 3650, "max_roles_per_company": 10}


class _DetailFetcher:
    needs_detail = True

    def detail(self, url):
        return "Job description body."


def test_contract_roles_do_not_bury_eligible_one():
    # 30 contract Senior PM roles (ranked first, alphabetically), then 1 Full time.
    raw = [{"title": f"Senior Product Manager A{i:02d}", "location": "London",
            "employment_type": "Contract", "description": "", "salary_text": "",
            "url": f"https://x/jobs/{i}", "source_detail": "Greenhouse"} for i in range(30)]
    raw.append({"title": "Senior Product Manager Zzz", "location": "London",
                "employment_type": "Full time", "description": "", "salary_text": "",
                "url": "https://x/jobs/eligible", "source_detail": "Greenhouse"})
    kept = pipeline.process_company({"name": "X", "slug": "x"}, PROFILE, raw,
                                    _DetailFetcher(), {}, None, date(2026, 6, 27))
    assert [k.title_raw for k in kept] == ["Senior Product Manager Zzz"]


def test_detail_fetch_cap_bounds_and_logs(capsys):
    # 200 contract roles, all detail-fetch -> bounded by detail_fetch_cap, logged.
    raw = [{"title": f"Senior Product Manager A{i:03d}", "location": "London",
            "employment_type": "Contract", "description": "", "salary_text": "",
            "url": f"https://x/jobs/{i}", "source_detail": "Greenhouse"} for i in range(200)]
    prof = {**PROFILE, "detail_fetch_cap": 25}
    kept = pipeline.process_company({"name": "X", "slug": "x"}, prof, raw,
                                    _DetailFetcher(), {}, None, date(2026, 6, 27))
    assert kept == []
    assert "detail-fetch cap (25)" in capsys.readouterr().out
