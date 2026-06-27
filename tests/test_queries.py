"""CLI read-side queries: grouping, open/new filters, marker."""
import json

from services import queries

ROWS = [
    {"id": "a", "company": "Wise", "title_raw": "Principal PM", "seniority_rank": 5,
     "location": "London", "status": "open", "first_seen": "2026-06-20"},
    {"id": "a", "company": "Wise", "title_raw": "Principal PM", "seniority_rank": 5,
     "location": "Remote (UK)", "status": "open", "first_seen": "2026-06-20"},
    {"id": "b", "company": "Monzo", "title_raw": "Senior PM", "seniority_rank": 3,
     "location": "London", "status": "open", "first_seen": "2026-06-27"},
    {"id": "c", "company": "Monzo", "title_raw": "Group PM", "seniority_rank": 4,
     "location": "London", "status": "closed", "first_seen": "2026-05-01"},
]


def test_group_roles_collapses_locations():
    roles = queries.group_roles(ROWS)
    a = next(r for r in roles if r["id"] == "a")
    assert sorted(a["locations"]) == ["London", "Remote (UK)"]
    assert len(roles) == 3            # a, b, c


def test_open_roles_excludes_closed():
    res = queries.open_roles(ROWS)
    assert {r["id"] for r in res} == {"a", "b"}


def test_open_roles_min_rank_and_company():
    assert [r["id"] for r in queries.open_roles(ROWS, min_rank=5)] == ["a"]
    assert {r["id"] for r in queries.open_roles(ROWS, company="monzo")} == {"b"}


def test_new_roles_since():
    res = queries.new_roles(ROWS, since="2026-06-25")
    assert [r["id"] for r in res] == ["b"]     # only the 06-27 open role


def test_new_roles_strict_excludes_marker_day():
    # auto-marker path: same-day roles were already seen at last check
    assert queries.new_roles(ROWS, since="2026-06-27", strict=True) == []
    # inclusive --since path still shows them
    assert [r["id"] for r in queries.new_roles(ROWS, since="2026-06-27")] == ["b"]


def test_new_roles_excludes_closed_even_if_recent():
    res = queries.new_roles(ROWS, since="2026-01-01")
    assert "c" not in {r["id"] for r in res}   # closed filtered out


def test_marker_roundtrip(tmp_path):
    p = tmp_path / "last_checked.txt"
    assert queries.read_marker(p) is None
    queries.write_marker(p, "2026-06-27")
    assert queries.read_marker(p) == "2026-06-27"


def test_load_index(tmp_path):
    p = tmp_path / "jobs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in ROWS[:2]) + "\n")
    assert len(queries.load_index(p)) == 2
