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


DESC_WITH_QUALS = """Role summary here.

Required Qualifications, Capabilities and Skills

- Strong **financial services** background, with regulated-environment delivery.
- Proven track record of scaling digital products.
- Demonstrated people leadership across multiple locations.
- Strategic communicator with executive presence.
- Strong understanding of technical architecture.
"""


def test_requirements_skipped_when_already_in_description():
    reqs = ("- Strong **financial services** background, with regulated-environment delivery.\n"
            "- Proven track record of scaling digital products.\n"
            "- Demonstrated people leadership across multiple locations.\n"
            "- Strategic communicator with executive presence.\n"
            "- Strong understanding of technical architecture.")
    body = md_writer.render(FM, DESC_WITH_QUALS, reqs, "")
    assert "## Requirements" not in body
    assert "Required Qualifications" in body    # description untouched


def test_requirements_skipped_despite_formatting_drift():
    # same content, but emphasis stripped, bullets restyled, spacing mangled
    reqs = ("* Strong financial  services background,   with regulated-environment delivery.\n"
            "*  Proven track record of scaling digital products.\n"
            "* Demonstrated people leadership across multiple locations.\n"
            "* Strategic communicator with executive presence.\n"
            "* Strong understanding of technical architecture.")
    body = md_writer.render(FM, DESC_WITH_QUALS, reqs, "")
    assert "## Requirements" not in body


def test_requirements_skipped_when_one_line_edited():
    # 4 of 5 lines identical -> still over the 0.8 overlap threshold
    reqs = ("- Strong **financial services** background, with regulated-environment delivery.\n"
            "- Proven track record of scaling excellent digital products at pace.\n"
            "- Demonstrated people leadership across multiple locations.\n"
            "- Strategic communicator with executive presence.\n"
            "- Strong understanding of technical architecture.")
    body = md_writer.render(FM, DESC_WITH_QUALS, reqs, "")
    assert "## Requirements" not in body


def test_requirements_kept_when_genuinely_different():
    reqs = ("- 10+ years of product management experience.\n"
            "- Deep fintech domain knowledge.\n"
            "- Fluent in SQL and experimentation frameworks.")
    body = md_writer.render(FM, DESC_WITH_QUALS, reqs, "")
    assert "## Requirements" in body


def test_requirements_kept_when_description_empty():
    body = md_writer.render(FM, "", "- req one", "")
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


def test_rename_removes_stale_file(tmp_path):
    """#3: same id, new title slug -> old file is removed, not orphaned."""
    old = md_writer.write_posting(tmp_path, "monzo", "old-title", "abc12345",
                                  FM, "d", "", "")
    assert old.exists()
    new = md_writer.write_posting(tmp_path, "monzo", "new-title", "abc12345",
                                  FM, "d", "", "", prior_path=old)
    assert new.exists()
    assert not old.exists()           # stale file cleaned up
    assert new.name == "new-title--abc12345.md"


def test_no_unlink_when_path_unchanged(tmp_path):
    p1 = md_writer.write_posting(tmp_path, "monzo", "spm", "abc12345", FM, "d", "", "x")
    p2 = md_writer.write_posting(tmp_path, "monzo", "spm", "abc12345", FM, "d2", "", "x",
                                 prior_path=p1)
    assert p1 == p2 and p2.exists()


def test_update_frontmatter_preserves_body(tmp_path):
    path = md_writer.write_posting(tmp_path, "monzo", "spm", "abc12345", FM,
                                   "desc body", "", "my note here")
    md_writer.update_frontmatter(path, {**FM, "status": "closed"})
    fm, body = md_writer.parse_md(path)
    assert fm["status"] == "closed"
    assert "desc body" in body
    assert "my note here" in body
