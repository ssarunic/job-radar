"""Claude trust-boundary validation (review P2) — no network; _ask_json faked."""
from services.claude_service import ClaudeService, _COMPANY_KEYS


def _svc(resp):
    s = ClaudeService({"use_claude": False})
    s.enabled = True                 # force the path on without a real client
    s._ask_json = lambda prompt: resp
    return s


def test_salary_rejects_bad_enum():
    assert _svc({"compensation_type": "weird", "currency": "GBP"}).extract_salary("x") is None
    assert _svc({"compensation_type": "Base Only", "currency": "BTC"}).extract_salary("x") is None


def test_salary_coerces_types():
    out = _svc({"salary_min": 100000, "salary_max": "oops", "currency": "GBP",
                "compensation_type": "Base+Bonus", "original_text": "£100k"}).extract_salary("x")
    assert out["salary_min"] == 100000 and out["salary_max"] is None
    assert out["currency"] == "GBP" and out["compensation_type"] == "Base+Bonus"


def test_company_projects_to_schema_and_drops_hallucinated_keys():
    out = _svc({"description": "A UK bank", "industry": "Fintech",
                "hq_location": "London, UK", "year_founded": 2015,
                "evil_injected": "rm -rf"}).extract_company("x", "Monzo")
    assert set(out) == set(_COMPANY_KEYS)        # exactly the known keys
    assert "evil_injected" not in out
    assert out["year_founded"] == 2015 and out["sub_industry"] == ""


def test_company_rejects_empty_description():
    assert _svc({"description": "   "}).extract_company("x", "Y") is None
