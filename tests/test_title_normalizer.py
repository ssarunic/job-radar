"""Title classification + seniority ranking (product-spec §11)."""
import pytest

from services.title_normalizer import classify, grade_from_body

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
    # area named before "product" — the qualifier bridge (_QUAL)
    ("Head of International Platforms Product", 6, "Head of Product"),
    ("Head of Digital Product", 6, "Head of Product"),
    ("Director of International Platforms Product", 7, "Director of Product"),
    ("VP Digital Commerce Product", 8, "VP Product"),
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
    # 'design' shouldn't exclude a real PM title (product-spec §11.5)
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


@pytest.mark.parametrize("title", [
    "Head of Engineering, Product Platform",   # comma blocks the bridge — a non-PM head
    "Head of Engineering",
    "Head of Sales",
])
def test_qualifier_bridge_does_not_promote_non_pm_heads(title):
    """The _QUAL bridge must not let a non-PM discipline reach a later 'product'."""
    assert classify(title, PROFILE).kept is False


def test_qualifier_bridge_still_respects_exclusions():
    assert not classify("Head of Product Marketing", PROFILE).kept
    assert not classify("Head of Digital Product Design", PROFILE).kept


def test_markets_vp_not_a_product_role():
    """Real NatWest case: 'Structured Product Vice President' is markets, not PM."""
    assert classify("Structured Product Vice President", PROFILE).kept is False


def test_marketing_kept_when_distinct_pm_title_present():
    """product-spec §11: marketing/brand dropped UNLESS a distinct segment is a PM title."""
    c = classify("Product Marketing Manager / Senior Product Manager", PROFILE)
    assert c.kept and c.rank == 3 and c.normalised == "Senior Product Manager"


def test_marketing_alone_still_excluded():
    assert not classify("Product Marketing Manager", PROFILE).kept
    assert not classify("Brand Manager", PROFILE).kept


# --- corporate-grade titles (bank/enterprise "<function> - <grade>") ------------------

@pytest.mark.parametrize("title,rank,norm", [
    # real Barclays case: the grade is the seniority signal, not "Product Manager"
    ("Product Manager - Director", 7, "Director of Product"),
    ("Product Manager – Vice President", 8, "VP Product"),          # en dash
    ("Product Manager, VP", 8, "VP Product"),
    ("Product Manager: Vice President", 8, "VP Product"),
    ("Product Manager (Director)", 7, "Director of Product"),       # brackets -> space
    ("Product Owner - Vice President", 8, "VP Product"),
    ("Digital Product Manager - Director", 7, "Director of Product"),
    ("Product Manager - Managing Director", 7, "Director of Product"),
    ("Product Management Director", 7, "Director of Product"),
    ("Director, Product Manager", 7, "Director of Product"),        # grade first
    ("Director - Product Owner", 7, "Director of Product"),
])
def test_corporate_grade_titles(title, rank, norm):
    c = classify(title, PROFILE)
    assert (c.rank, c.normalised, c.kept) == (rank, norm, True)


@pytest.mark.parametrize("title,norm", [
    # a grade attached to another function must not leak onto the PM segment
    ("Director of Engineering, Product Manager", "Product Manager"),
    ("Product Manager - Directory Services", "Product Manager"),
    # AVP has no rung on the ladder: ranks on the function, so still below the floor
    ("Product Manager - AVP", "Product Manager"),
])
def test_grade_does_not_leak(title, norm):
    c = classify(title, PROFILE)
    assert c.normalised == norm and c.rank == 2 and c.kept is False


# --- UK-bank "Product & Proposition" job family (Barclays) ---------------------------

@pytest.mark.parametrize("title,rank,norm,kept", [
    ("Senior Product & Proposition Manager", 3, "Senior Product Manager", True),
    ("Senior Product and Proposition Manager", 3, "Senior Product Manager", True),
    ("Product & Proposition Manager - Director", 7, "Director of Product", True),
    ("Lead Segment and Propositions Manager", 2, "Product Manager", False),   # "Lead" is not a rung
    ("Loans Product and Proposition Manager", 2, "Product Manager", False),
    ("Product and Proposition Manager - Payables", 2, "Product Manager", False),
])
def test_proposition_manager_alias(title, rank, norm, kept):
    c = classify(title, PROFILE)
    assert (c.rank, c.normalised, c.kept) == (rank, norm, kept)


def test_proposition_alias_keeps_exclusions():
    assert classify("Propositions Marketing Manager", PROFILE).kept is False


def test_proposition_alias_is_product_pack_only():
    assert classify("Senior Product & Proposition Manager", DESIGN_PROFILE).kept is False


@pytest.mark.parametrize("body,expected", [
    ("…\nVice President Expectations\nTo contribute or set strategy…", ("VP Product", "VP", 8)),
    ("Senior Vice President Expectations", ("VP Product", "VP", 8)),
    ("Director Expectations\nProvide expert advice…", ("Director of Product", "Director", 7)),
    ("Managing Director Expectations", ("Director of Product", "Director", 7)),
    ("Assistant Vice President Expectations", None),      # AVP has no rung
    ("Analyst Expectations", None),
    ("We have high expectations of our Directors.", None),   # not the template phrase
    ("", None),
])
def test_grade_from_body(body, expected):
    assert grade_from_body(body) == expected


# --- combined product + engineering titles (product-spec §11.10) ----------------------

@pytest.mark.parametrize("title,rank,norm", [
    # conjoined C-suite: product merged with technology/engineering at C level
    ("Chief Product and Technology Officer", 9, "Chief Product & Technology Officer"),
    ("Chief Product & Technology Officer", 9, "Chief Product & Technology Officer"),
    ("Chief Technology and Product Officer", 9, "Chief Product & Technology Officer"),
    ("Chief Product & Engineering Officer", 9, "Chief Product & Technology Officer"),
    ("Chief Digital and Product Officer", 9, "Chief Product & Technology Officer"),
    ("Chief Product, Technology & Data Officer", 9, "Chief Product & Technology Officer"),
    ("CPTO", 9, "Chief Product & Technology Officer"),
    ("CTPO", 9, "Chief Product & Technology Officer"),
    # the rest of the ladder already bridges "product & engineering" via _QUAL
    ("VP, Product & Engineering Coda & FP&A", 8, "VP Product"),   # real Unit4 case
    ("VP Engineering & Product", 8, "VP Product"),
    ("Director of Product and Engineering", 7, "Director of Product"),
    ("Director, Product & Technology", 7, "Director of Product"),  # comma form, was missed
    ("Senior Director, Product & Engineering", 7, "Director of Product"),
    ("Payments - Director, Product", 7, "Director of Product"),
    ("Head of Product & Engineering", 6, "Head of Product"),
    ("Head of Engineering and Product", 6, "Head of Product"),
])
def test_product_engineering_titles_kept(title, rank, norm):
    c = classify(title, PROFILE)
    assert (c.rank, c.normalised, c.kept) == (rank, norm, True)


@pytest.mark.parametrize("title", [
    # engineering/other C-suite without product is still not a product role
    "Chief Technology Officer",
    "CTO",
    "Chief Information Officer",
    "Chief Data Officer",
    "Chief Operating Officer",
    "Chief People Officer",
    "VP Engineering",
    "Head of Engineering",
    "Director of Engineering",
    # the comma form needs Director to lead its segment — not another function's director
    "Sales Director, Product Specialists",
    "Account Director Product Sales",
    "Art Director, Product",
])
def test_engineering_only_titles_dropped(title):
    c = classify(title, PROFILE)
    assert c.kept is False and c.reason == "not a product role"


# --- AI / Innovation leadership family (product-spec §11.9) ---------------------------

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


# --- custom pattern packs (non-PM disciplines) -----------------------------------

DESIGN_PROFILE = {
    "seniority_min": 3,
    "exclude_titles": ["marketing", "internship"],
    "custom_patterns": [
        {"pattern": r"\bhead of design\b", "normalised": "Head of Design",
         "level": "Head", "rank": 6},
        {"pattern": r"\bsenior product designer\b", "normalised": "Senior Product Designer",
         "level": "Senior", "rank": 3},
        {"pattern": r"\bproduct designer\b", "normalised": "Product Designer",
         "level": "Mid", "rank": 2},
    ],
}


def test_custom_pack_replaces_pm_ladder():
    c = classify("Head of Design", DESIGN_PROFILE)
    assert (c.normalised, c.rank, c.kept) == ("Head of Design", 6, True)
    # PM titles are unknown to a custom pack
    assert classify("Head of Product", DESIGN_PROFILE).kept is False


def test_custom_pack_order_and_floor():
    assert classify("Senior Product Designer", DESIGN_PROFILE).rank == 3
    c = classify("Product Designer", DESIGN_PROFILE)
    assert c.rank == 2 and c.kept is False        # below seniority_min


def test_custom_pack_ignores_product_owner_bump():
    p = {**DESIGN_PROFILE, "custom_patterns": DESIGN_PROFILE["custom_patterns"] + [
        {"pattern": r"\bproduct owner\b", "normalised": "Product Owner",
         "level": "Other", "rank": 2}]}
    # no senior/lead bump outside the product pack
    assert classify("Senior Product Owner", p).rank == 2


def test_custom_pack_still_honours_exclusions():
    assert classify("Design Marketing Lead", DESIGN_PROFILE).kept is False
