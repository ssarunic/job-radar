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


def test_add_duplicate_rejected(tmp_path):
    p = _csv(tmp_path)
    assert registry.add_company({"name": "Monzo", "slug": "monzo", "careers_url": "",
                                 "ats_type": "greenhouse", "ats_slug": "monzo",
                                 "priority": "low", "active": True}, p) is False
    assert len(registry.list_companies(p)) == 1


def test_set_active_toggle(tmp_path):
    p = _csv(tmp_path)
    assert registry.set_active("monzo", False, p) is True
    assert registry.list_companies(p)[0]["active"] is False
    assert registry.set_active("nope", False, p) is False
