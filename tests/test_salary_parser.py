"""Salary detection + employment classification (product-spec §13, §10)."""
import pytest

from services import salary_parser


def test_range_gbp():
    sal, comp = salary_parser.parse("Salary: £105,000 - £135,000 plus bonus")
    assert (sal.min, sal.max, sal.currency) == (105000, 135000, "GBP")
    assert comp == "Base+Bonus"
    assert sal.original_text  # preserved (product-spec §13)


def test_single_usd_per_year():
    sal, comp = salary_parser.parse("Compensation is $120,000 per year")
    assert (sal.min, sal.max, sal.currency) == (120000, 120000, "USD")
    assert comp == "Base Only"


def test_k_suffix():
    sal, _ = salary_parser.parse("Base salary £90k–£110k")
    assert (sal.min, sal.max) == (90000, 110000)


def test_learning_budget_rejected():
    """The first £amount isn't the salary — 'Learning budget of £1,000' must not win."""
    sal, comp = salary_parser.parse(
        "Salary dependent on experience. Learning budget of £1,000 a year.")
    assert sal.min is None and sal.max is None
    assert comp == "Not Stated"


def test_age_range_not_salary():
    sal, comp = salary_parser.parse("accounts for 16-17 year olds")
    assert sal.min is None
    assert comp == "Not Stated"


def test_europe_not_eur_currency():
    """'EUR' must not be matched inside 'Europe'."""
    sal, _ = salary_parser.parse("Remote across Europe. No salary listed.")
    assert sal.currency is None


def test_remote_not_ote():
    """'ote' must not be matched inside 'remote'."""
    _, comp = salary_parser.parse("This is a remote role.")
    assert comp == "Not Stated"


def test_picks_salary_context_over_other_amount():
    text = ("Pension contributions apply. Salary: £140,000 - £160,000. "
            "Charity match up to £500.")
    sal, _ = salary_parser.parse(text)
    assert (sal.min, sal.max) == (140000, 160000)


@pytest.mark.parametrize("raw,body,expected", [
    ("FullTime", "", "Full time"),
    ("PartTime", "", "Part time"),
    ("Contractor", "", "Contract"),
    ("Fixed-term", "", "Contract"),
    ("Temporary", "", "Contract"),
    ("Permanent", "", "Full time"),
    ("", "This is a 12 month contract role", "Contract"),
    ("", "Contract type: Full Time", "Full time"),   # 'contract' word w/o context
    ("", "no signal here", "Full time"),
])
def test_classify_employment(raw, body, expected):
    assert salary_parser.classify_employment(raw, body) == expected
