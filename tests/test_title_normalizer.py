"""Title classification + seniority ranking (README §11)."""
import pytest

from services.title_normalizer import classify

PROFILE = {
    "exclude_titles": ["marketing", "growth marketing", "brand", "design",
                       "hr", "talent", "people ops", "recruit",
                       "graduate", "internship"],
    "seniority_min": 3,
    "include_product_owner": True,
}


@pytest.mark.parametrize("title,rank,norm", [
    ("Chief Product Officer", 9, "Chief Product Officer"),
    ("CPO", 9, "Chief Product Officer"),
    ("VP Product", 8, "VP Product"),
    ("VP of Product", 8, "VP Product"),                       # #6: was missed
    ("Vice President, Product", 8, "VP Product"),
    ("SVP Product Management", 8, "VP Product"),
    ("Director of Product", 7, "Director of Product"),
    ("Product Director", 7, "Director of Product"),
    ("Director, Product Management", 7, "Director of Product"),  # #6: was missed
    ("Head of Product", 6, "Head of Product"),
    ("Head, Product", 6, "Head of Product"),                  # #6: was missed
    ("Head of Product Management", 6, "Head of Product"),
    ("Principal Product Manager", 5, "Principal Product Manager"),
    ("Staff Product Manager", 5, "Staff Product Manager"),          # Staff = Principal tier
    ("Staff Product Manager - AI - Remote EMEA", 5, "Staff Product Manager"),
    ("Group Product Manager", 4, "Group Product Manager"),
    ("Product Lead, EMEA Payments", 4, "Product Lead"),             # bare Lead = Group tier
    ("Product Leader - Payments", 4, "Product Lead"),
    ("Principal Product Lead", 5, "Principal Product Manager"),
    # seniority word not adjacent to "product" — still caught by prefix
    ("Executive Director, Product Lead – Merchant Services", 7, "Director of Product"),
    ("Payments - Product Lead - Merchant services EMEA - Vice President", 8, "VP Product"),
    ("Senior Product Manager", 3, "Senior Product Manager"),
    ("Sr. Product Manager", 3, "Senior Product Manager"),
])
def test_seniority_ranks(title, rank, norm):
    c = classify(title, PROFILE)
    assert c.rank == rank
    assert c.normalised == norm
    assert c.kept is True


def test_principal_group_ordering():
    """#6: 'Principal Group Product Manager' must rank Principal (5), not Group (4)."""
    c = classify("Principal Group Product Manager", PROFILE)
    assert c.rank == 5
    assert c.normalised == "Principal Product Manager"


def test_mid_pm_below_threshold_dropped():
    c = classify("Product Manager", PROFILE)
    assert c.rank == 2
    assert c.kept is False


def test_product_owner_kept_when_enabled():
    c = classify("Product Owner", PROFILE)
    assert c.normalised == "Product Owner"
    assert c.rank == 2
    assert c.kept is True


def test_product_owner_dropped_when_disabled():
    prof = {**PROFILE, "include_product_owner": False}
    c = classify("Product Owner", prof)
    assert c.kept is False


def test_senior_product_owner_bumped_to_rank_3():
    c = classify("Senior Product Owner", PROFILE)
    assert c.rank == 3
    assert c.kept is True


@pytest.mark.parametrize("title", [
    "Product Marketing Manager",
    "Senior Product Designer",
    "Head of Talent",
    "HR Business Partner",
    "Brand Manager, Product",
    "Graduate Programme 2027: Product Owner (UX)",
    "Internship Programme 2027: Product Owner (Technical)",
    "Graduate Product Manager",
])
def test_excluded_titles(title):
    assert classify(title, PROFILE).kept is False


def test_internship_term_not_matching_internal():
    """'internship' (not 'intern') so 'Internal…' titles survive the word-start match."""
    c = classify("Senior Product Manager, Internal Tools", PROFILE)
    assert c.kept is True
    assert c.rank == 3


def test_design_kept_when_clearly_pm():
    # 'design' shouldn't exclude a real PM title (README §11.5)
    c = classify("Senior Product Manager, Design Systems", PROFILE)
    assert c.kept is True
    assert c.rank == 3


def test_hr_substring_not_excluded():
    """Word-boundary fix: 'hr' must not match inside 'Threat'."""
    c = classify("Senior Product Manager, Threat Detection", PROFILE)
    assert c.kept is True
    assert c.rank == 3


def test_non_product_role_dropped():
    assert classify("Software Engineer", PROFILE).kept is False


def test_markets_vp_not_a_product_role():
    """Real NatWest case: 'Structured Product Vice President' is markets, not PM."""
    assert classify("Structured Product Vice President", PROFILE).kept is False


def test_marketing_kept_when_distinct_pm_title_present():
    """README §11: marketing/brand dropped UNLESS a distinct segment is a PM title."""
    c = classify("Product Marketing Manager / Senior Product Manager", PROFILE)
    assert c.kept and c.rank == 3 and c.normalised == "Senior Product Manager"


def test_marketing_alone_still_excluded():
    assert not classify("Product Marketing Manager", PROFILE).kept
    assert not classify("Brand Manager", PROFILE).kept


# --- AI / Innovation leadership family (README §11.9) ---------------------------

@pytest.mark.parametrize("title,rank,norm", [
    ("AI & Innovation Lead", 4, "AI/Innovation Lead"),          # real Mishcon case
    ("Innovation Lead", 4, "AI/Innovation Lead"),
    ("GenAI Lead", 4, "AI/Innovation Lead"),
    ("AI Leader, Legal Practice", 4, "AI/Innovation Lead"),
    ("Head of AI", 6, "Head of AI/Innovation"),
    ("Head of Innovation", 6, "Head of AI/Innovation"),
    ("Head of AI & Innovation", 6, "Head of AI/Innovation"),
    ("Director of AI & Innovation", 7, "Director of AI/Innovation"),
    ("Innovation Director", 7, "Director of AI/Innovation"),
    ("VP of AI", 8, "VP AI/Innovation"),
    ("Vice President, Innovation", 8, "VP AI/Innovation"),
    ("Chief AI Officer", 9, "Chief AI Officer"),
    ("Chief Innovation Officer", 9, "Chief AI Officer"),
])
def test_ai_innovation_leadership_kept(title, rank, norm):
    c = classify(title, PROFILE)
    assert c.kept is True
    assert c.rank == rank
    assert c.normalised == norm


@pytest.mark.parametrize("title", [
    "AI Engineer Lead",            # engineer between domain and lead — IC track
    "Lead AI Engineer",
    "AI Research Lead",
    "Head of AI Research",         # IC-track qualifier after the domain
    "VP AI Engineering",
    "Machine Learning Lead",       # ML alone is not the AI/Innovation domain
    "Innovation Manager",          # no manager tier in the family
    "AI Scientist",
])
def test_ai_ic_track_and_manager_tier_dropped(title):
    assert classify(title, PROFILE).kept is False


def test_ai_family_disabled_by_config():
    prof = {**PROFILE, "include_ai_innovation": False}
    c = classify("AI & Innovation Lead", prof)
    assert c.kept is False
    assert c.reason == "not a product role"


def test_pm_patterns_win_over_ai_family():
    c = classify("VP Product & AI", PROFILE)
    assert c.normalised == "VP Product"
    assert c.rank == 8
