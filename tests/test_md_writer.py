"""Markdown canonical store: round-trip + user-note preservation (SPEC §6.3)."""
from outputs import md_writer

FM = {
    "id": "abc12345", "company": "Monzo", "title_raw": "Senior Product Manager",
    "status": "open", "salary": {"min": None, "max": None},
}


def test_render_parse_roundtrip(tmp_path):
    path = md_writer.write_posting(tmp_path, "monzo", "senior-product-manager",
                                   "abc12345", FM, "A description.", "- req one", "")
    fm, body = md_writer.parse_md(path)
    assert fm["id"] == "abc12345"
    assert fm["company"] == "Monzo"
    assert "A description." in body
    assert "## Requirements" in body


def test_notes_preserved_on_rewrite(tmp_path):
    path = md_writer.write_posting(tmp_path, "monzo", "spm", "abc12345", FM,
                                   "desc", "", "Applied 2026-06-27. Spoke to Jane.")
    _, body = md_writer.parse_md(path)
    assert "Spoke to Jane." in md_writer.extract_notes(body)
    # rewrite with fresh scraper data, re-supplying preserved notes
    notes = md_writer.extract_notes(body)
    md_writer.write_posting(tmp_path, "monzo", "spm", "abc12345", FM,
                            "new desc", "", notes)
    _, body2 = md_writer.parse_md(path)
    assert "Spoke to Jane." in body2
    assert "new desc" in body2


def test_extract_notes_empty_when_none(tmp_path):
    path = md_writer.write_posting(tmp_path, "monzo", "spm", "abc12345", FM,
                                   "desc", "", "")
    _, body = md_writer.parse_md(path)
    assert md_writer.extract_notes(body) == ""


def test_update_frontmatter_preserves_body(tmp_path):
    path = md_writer.write_posting(tmp_path, "monzo", "spm", "abc12345", FM,
                                   "desc body", "", "my note here")
    md_writer.update_frontmatter(path, {**FM, "status": "closed"})
    fm, body = md_writer.parse_md(path)
    assert fm["status"] == "closed"
    assert "desc body" in body
    assert "my note here" in body
