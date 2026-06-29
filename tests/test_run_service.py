"""run_service: company selection + a seek_run orchestration smoke (review P2)."""
from services.run_service import RunResult, seek_run, select_companies

ROWS = [{"slug": "a", "active": True}, {"slug": "b", "active": True},
        {"slug": "c", "active": False}]


def test_select_filters_active():
    assert {c["slug"] for c in select_companies(ROWS)} == {"a", "b"}


def test_select_only_and_limit_and_max():
    assert [c["slug"] for c in select_companies(ROWS, only="b")] == ["b"]
    assert len(select_companies(ROWS, limit=1)) == 1
    assert len(select_companies(ROWS, max_companies=1)) == 1


def test_seek_run_empty_is_clean(tmp_path, monkeypatch):
    """No companies → a valid RunResult, index rebuilt to 0, summary written."""
    monkeypatch.setenv("JSA_ROOT", str(tmp_path))
    res = seek_run({"rate_limit_per_sec": 1, "runtime_budget_min": 30}, {}, [],
                   progress=lambda _m: None)
    assert isinstance(res, RunResult)
    assert res.n_index == 0 and res.outcomes == [] and res.stats["companies"] == 0
    assert res.run_dir.exists() and (res.run_dir / "summary.txt").exists()
    assert res.notified is False
