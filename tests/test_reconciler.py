"""Run-to-run reconciliation + lifecycle (SPEC §8, README §15)."""
from pathlib import Path

from models.job_posting import JobPosting
from services import reconciler

TODAY = "2026-06-27"


def _jp():
    return JobPosting(company="Monzo", company_slug="monzo",
                      title_raw="Senior Product Manager", locations=["London"],
                      job_ad_url="https://job-boards.greenhouse.io/monzo/jobs/123")


def _existing(jp, body="## My notes\n\n", **fm_over):
    fm = jp.to_frontmatter()
    fm.update({"first_seen": "2026-01-01", "last_seen": "2026-01-01",
               "last_checked": "2026-01-01", "missing_runs": 0, "status": "open"})
    fm.update(fm_over)
    return {jp.id: {"fm": fm, "body": body, "path": Path("/tmp/x.md")}}


def test_new_posting_added():
    jp = _jp()
    current, missing, diff = reconciler.reconcile({}, [jp], TODAY)
    assert len(current) == 1
    _, fm, notes, _ = current[0]
    assert fm["status"] == "open"
    assert fm["first_seen"] == TODAY and fm["last_seen"] == TODAY
    assert fm["missing_runs"] == 0
    assert any(d["change"] == "added" for d in diff)


def test_seen_again_preserves_first_seen_bumps_last_seen():
    jp = _jp()
    current, _, diff = reconciler.reconcile(_existing(jp), [jp], TODAY)
    _, fm, _, _ = current[0]
    assert fm["first_seen"] == "2026-01-01"   # preserved
    assert fm["last_seen"] == TODAY           # bumped
    assert fm["status"] == "open"
    assert not diff                           # 'updated' not emitted (current behaviour)


def test_updated_diff_on_salary_change():
    """#7: a salary change on a seen-again role emits an 'updated' diff row."""
    jp = _jp()
    existing = _existing(jp)
    existing[jp.id]["fm"]["salary"] = {"min": 100000, "max": 120000, "currency": "GBP"}
    jp.salary.min, jp.salary.max, jp.salary.currency = 130000, 150000, "GBP"
    _, _, diff = reconciler.reconcile(existing, [jp], TODAY)
    upd = [d for d in diff if d["change"] == "updated"]
    assert len(upd) == 1
    assert "salary" in upd[0]["changes"]
    assert upd[0]["changes"]["salary"][1]["min"] == 130000


def test_updated_diff_on_title_and_location_change():
    jp = _jp()
    existing = _existing(jp)
    existing[jp.id]["fm"]["title_raw"] = "Product Manager"
    existing[jp.id]["fm"]["locations"] = ["Manchester"]
    _, _, diff = reconciler.reconcile(existing, [jp], TODAY)  # jp is SPM / London
    upd = [d for d in diff if d["change"] == "updated"][0]
    assert set(upd["changes"]) >= {"title_raw", "locations"}


def test_no_updated_diff_when_content_unchanged():
    jp = _jp()
    _, _, diff = reconciler.reconcile(_existing(jp), [jp], TODAY)
    assert [d for d in diff if d["change"] == "updated"] == []


def test_lifecycle_fields_do_not_trigger_updated():
    """Bumping last_seen/last_checked alone must not count as an update."""
    jp = _jp()
    existing = _existing(jp, last_seen="2026-01-01", last_checked="2026-01-01")
    _, _, diff = reconciler.reconcile(existing, [jp], TODAY)
    assert diff == []


def test_applied_status_preserved():
    jp = _jp()
    current, _, _ = reconciler.reconcile(_existing(jp, status="applied"), [jp], TODAY)
    _, fm, _, _ = current[0]
    assert fm["status"] == "applied"


def test_notes_carried_through():
    jp = _jp()
    body = "## Description\n\nx\n\n## My notes\n\nCalled recruiter.\n"
    current, _, _ = reconciler.reconcile(_existing(jp, body=body), [jp], TODAY)
    _, _, notes, _ = current[0]
    assert "Called recruiter." in notes


def test_missing_one_run_stays_open():
    jp = _jp()
    _, missing, diff = reconciler.reconcile(_existing(jp, missing_runs=0), [], TODAY)
    _, fm = missing[0]
    assert fm["missing_runs"] == 1
    assert fm["status"] == "open"
    assert not diff


def test_missing_two_runs_suspected_filled():
    jp = _jp()
    _, missing, diff = reconciler.reconcile(_existing(jp, missing_runs=1), [], TODAY)
    _, fm = missing[0]
    assert fm["missing_runs"] == 2
    assert fm["status"] == "suspected_filled"
    assert any(d["change"] == "suspected_filled" for d in diff)


def test_missing_three_runs_closed():
    jp = _jp()
    _, missing, diff = reconciler.reconcile(
        _existing(jp, missing_runs=2, status="suspected_filled"), [], TODAY)
    _, fm = missing[0]
    assert fm["missing_runs"] == 3
    assert fm["status"] == "closed"
    assert any(d["change"] == "closed" for d in diff)


def test_applied_never_auto_advances():
    jp = _jp()
    _, missing, diff = reconciler.reconcile(
        _existing(jp, missing_runs=5, status="applied"), [], TODAY)
    _, fm = missing[0]
    assert fm["status"] == "applied"
    assert not diff


def test_reopened_when_closed_role_reappears():
    jp = _jp()
    current, _, diff = reconciler.reconcile(
        _existing(jp, status="closed", missing_runs=3), [jp], TODAY)
    _, fm, _, _ = current[0]
    assert fm["status"] == "open"
    assert fm["missing_runs"] == 0
    assert any(d["change"] == "reopened" for d in diff)


def test_load_existing_roundtrip(tmp_path):
    from outputs import md_writer
    jp = _jp()
    fm = jp.to_frontmatter()
    fm.update({"first_seen": TODAY, "last_seen": TODAY, "status": "open"})
    md_writer.write_posting(tmp_path, "monzo", "spm", jp.id, fm, "d", "", "note")
    loaded = reconciler.load_existing(tmp_path)
    assert jp.id in loaded
    assert loaded[jp.id]["fm"]["company"] == "Monzo"
