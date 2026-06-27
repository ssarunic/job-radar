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


def test_new_roles_excludes_closed_even_if_recent():
    res = queries.new_roles(ROWS, since="2026-01-01")
    assert "c" not in {r["id"] for r in res}   # closed filtered out


def test_unseen_roles_filters_by_id():
    assert {r["id"] for r in queries.unseen_roles(ROWS, seen_ids=set())} == {"a", "b"}
    assert [r["id"] for r in queries.unseen_roles(ROWS, seen_ids={"a"})] == ["b"]
    assert queries.unseen_roles(ROWS, seen_ids={"a", "b"}) == []


def test_unseen_roles_shows_same_day_role_discovered_after_check(tmp_path):
    """#1 regression: a role discovered the same day after a check still appears."""
    # first check: only 'a' existed and was marked seen
    seen = {"a"}
    # later same day 'b' (first_seen today) appears -> must be unseen
    res = queries.unseen_roles(ROWS, seen_ids=seen)
    assert [r["id"] for r in res] == ["b"]


def test_seen_roundtrip(tmp_path):
    p = tmp_path / "seen_roles.json"
    assert queries.read_seen(p) == set()
    queries.write_seen(p, {"a", "b"})
    assert queries.read_seen(p) == {"a", "b"}


def test_load_index(tmp_path):
    p = tmp_path / "jobs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in ROWS[:2]) + "\n")
    assert len(queries.load_index(p)) == 2
