"""The MD must keep the full ad text, not a truncated summary."""
from datetime import date

from services import pipeline

PROFILE = {"seniority_min": 3, "include_product_owner": True, "exclude_titles": [],
           "locations": ["London"], "allow_remote": True, "employment": ["Full time"],
           "recency_days": 3650, "max_roles_per_company": 10}


class _Fetcher:
    needs_detail = False

    def detail(self, url):
        return ""


def test_full_description_not_truncated():
    long_desc = "About Capsa.\n" + ("Sentence number %d about the role. " % 0) * 400  # ~ many chars
    long_desc = "About Capsa.\n" + " ".join(f"Para {i} of the ad." for i in range(400))
    assert len(long_desc) > 3000
    raw = [{"title": "Head of Product", "location": "London",
            "description": long_desc, "salary_text": "",
            "url": "https://job-boards.greenhouse.io/x/jobs/1", "source_detail": "Greenhouse"}]
    kept = pipeline.process_company({"name": "Capsa", "slug": "capsa"}, PROFILE, raw,
                                    _Fetcher(), {}, None, date(2026, 6, 27))
    assert len(kept) == 1
    assert len(kept[0].description) >= len(long_desc) - 5   # full text retained
    assert "[truncated]" not in kept[0].description
    assert kept[0].description.rstrip().endswith("Para 399 of the ad.")


def test_safety_cap_applies_to_pathological_body():
    huge = "x " * 30000  # 60k chars
    raw = [{"title": "Head of Product", "location": "London",
            "description": huge, "salary_text": "",
            "url": "https://job-boards.greenhouse.io/x/jobs/2", "source_detail": "Greenhouse"}]
    kept = pipeline.process_company({"name": "C", "slug": "c"}, PROFILE, raw,
                                    _Fetcher(), {}, None, date(2026, 6, 27))
    assert "[truncated]" in kept[0].description
    assert len(kept[0].description) < 41000
