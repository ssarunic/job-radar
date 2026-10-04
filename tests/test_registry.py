"""Company registry read/write (follow / unfollow / list)."""
from services import registry

HEADER = "name,slug,careers_url,ats_type,ats_slug,priority,active\n"
ROW = "Monzo,monzo,https://job-boards.greenhouse.io/monzo,greenhouse,monzo,medium,true\n"


def _csv(tmp_path):
    p = tmp_path / "companies.csv"
    p.write_text(HEADER + ROW)
    return p


def test_list(tmp_path):
    rows = registry.list_companies(_csv(tmp_path))
    assert len(rows) == 1 and rows[0]["slug"] == "monzo" and rows[0]["active"] is True


def test_add_company(tmp_path):
    p = _csv(tmp_path)
    ok = registry.add_company(
        {"name": "Cohere", "slug": "cohere", "careers_url": "https://jobs.ashbyhq.com/cohere",
         "ats_type": "ashby", "ats_slug": "cohere", "priority": "high", "active": True}, p)
    assert ok is True
    rows = registry.list_companies(p)
    assert {r["slug"] for r in rows} == {"monzo", "cohere"}


def test_find_by_name_matches_slug_or_name_loosely(tmp_path):
    p = _csv(tmp_path)
    assert registry.find_by_name("monzo", p)["slug"] == "monzo"
    assert registry.find_by_name("  MONZO ", p)["slug"] == "monzo"
    assert registry.find_by_name("Cohere", p) is None
    assert registry.find_by_name("", p) is None


def test_add_duplicate_rejected(tmp_path):
    p = _csv(tmp_path)
    assert registry.add_company({"name": "Monzo", "slug": "monzo", "careers_url": "",
                                 "ats_type": "greenhouse", "ats_slug": "monzo",
                                 "priority": "low", "active": True}, p) is False
    assert len(registry.list_companies(p)) == 1


def test_dedup_by_ats_slug_despite_different_company_slug(tmp_path):
    """#3: same ATS board, different generated slug -> not a duplicate company."""
    p = tmp_path / "companies.csv"
    p.write_text(HEADER +
                 "Black Forest Labs,black-forest-labs,"
                 "https://job-boards.greenhouse.io/blackforestlabs,greenhouse,blackforestlabs,medium,true\n")
    dup = {"name": "Blackforestlabs", "slug": "blackforestlabs",
           "careers_url": "https://job-boards.greenhouse.io/blackforestlabs",
           "ats_type": "greenhouse", "ats_slug": "blackforestlabs",
           "priority": "medium", "active": True}
    assert registry.add_company(dup, p) is False
    assert len(registry.list_companies(p)) == 1


def test_dedup_by_careers_url(tmp_path):
    p = _csv(tmp_path)
    dup = {"name": "Monzo Bank", "slug": "monzo-bank",
           "careers_url": "https://job-boards.greenhouse.io/monzo/",  # trailing slash
           "ats_type": "", "ats_slug": "", "priority": "low", "active": True}
    assert registry.add_company(dup, p) is False


def test_set_active_toggle(tmp_path):
    p = _csv(tmp_path)
    assert registry.set_active("monzo", False, p) is True
    assert registry.list_companies(p)[0]["active"] is False
    assert registry.set_active("nope", False, p) is False


def test_missing_file_means_nothing_followed(tmp_path):
    """companies.csv is user-owned and not shipped: absent = empty, and the first
    follow creates it."""
    p = tmp_path / "config" / "companies.csv"
    assert registry.list_companies(p) == []
    assert registry.find_by_name("monzo", p) is None
    assert registry.set_active("monzo", False, p) is False
    assert registry.add_company({"name": "Monzo", "slug": "monzo", "careers_url": "",
                                 "ats_type": "greenhouse", "ats_slug": "monzo",
                                 "priority": "medium", "active": True}, p) is True
    assert [r["slug"] for r in registry.list_companies(p)] == ["monzo"]
