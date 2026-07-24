"""update_user_fields — user-owned status + notes edits preserve the ad verbatim."""
from outputs import md_writer


def _mk(tmp_path):
    p = tmp_path / "role--abc.md"
    p.write_text("---\nid: abc\nstatus: open\ntitle_raw: Head of Product\n---\n\n"
                 "## Description\n\nThe **ad** text.\n\n## My notes\n\nold note\n")
    return p


def test_status_only_preserves_notes_and_ad(tmp_path):
    p = _mk(tmp_path)
    fm = md_writer.update_user_fields(p, status="applied")
    assert fm["status"] == "applied"
    fm2, body = md_writer.parse_md(p)
    ad, notes = md_writer.split_body(body)
    assert fm2["status"] == "applied" and fm2["title_raw"] == "Head of Product"
    assert "The **ad** text." in ad
    assert notes == "old note"


def test_notes_only_preserves_status(tmp_path):
    p = _mk(tmp_path)
    md_writer.update_user_fields(p, notes="Applied 2026-07-24.")
    fm, body = md_writer.parse_md(p)
    assert fm["status"] == "open"
    assert md_writer.split_body(body)[1] == "Applied 2026-07-24."


def test_empty_notes_clears_section(tmp_path):
    p = _mk(tmp_path)
    md_writer.update_user_fields(p, notes="")
    assert md_writer.split_body(md_writer.parse_md(p)[1])[1] == ""
