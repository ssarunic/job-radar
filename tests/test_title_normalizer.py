"""Title classification + seniority ranking (README §11)."""
import pytest

from services.title_normalizer import classify

PROFILE = {
    "exclude_titles": ["marketing", "growth marketing", "brand", "design",
                       "hr", "talent", "people ops", "recruit"],
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
    ("Group Product Manager", 4, "Group Product Manager"),
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
])
def test_excluded_titles(title):
    assert classify(title, PROFILE).kept is False


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
