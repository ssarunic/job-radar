"""Derived JSONL index: one row per (role, location) (#3, product-spec §12)."""
import json

from outputs import index_builder, md_writer

FM = {"id": "abc12345", "company": "Wise", "title_raw": "Principal Product Manager",
      "locations": ["London", "Remote (UK)"], "status": "open"}


def _read(path):
    return [json.loads(l) for l in path.read_text().splitlines()]


def test_index_expands_locations_into_rows(tmp_path):
    jobs = tmp_path / "jobs"
    md_writer.write_posting(jobs, "wise", "ppm", "abc12345", FM, "desc", "", "")
    idx = tmp_path / "data" / "jobs.jsonl"
    n = index_builder.rebuild(jobs, idx)
    rows = _read(idx)
    assert n == 2                                   # one row per location
    locs = sorted(r["location"] for r in rows)
    assert locs == ["London", "Remote (UK)"]
    for r in rows:
        assert r["id"] == "abc12345"                # same canonical id
        assert "locations" not in r                 # collapsed to singular
        assert r["_path"].endswith("ppm--abc12345.md")


def test_index_single_row_when_one_location(tmp_path):
    jobs = tmp_path / "jobs"
    fm = {**FM, "locations": ["London"]}
    md_writer.write_posting(jobs, "wise", "ppm", "abc12345", fm, "d", "", "")
    idx = tmp_path / "data" / "jobs.jsonl"
    assert index_builder.rebuild(jobs, idx) == 1
    assert _read(idx)[0]["location"] == "London"


def test_index_empty_when_no_jobs(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    idx = tmp_path / "data" / "jobs.jsonl"
    assert index_builder.rebuild(jobs, idx) == 0
    assert idx.read_text() == ""
