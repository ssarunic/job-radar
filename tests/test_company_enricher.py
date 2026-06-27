"""Exploratory enrichment: About-blurb extraction, HQ inference, confidence."""
from outputs import company_index
from services import company_enricher

NOW = "2026-06-27T00:00:00+00:00"


class NoClaude:
    def extract_company(self, text, name):
        return None


POSTINGS = [
    {"description": "About Monzo\nMonzo is a UK digital bank on a mission to make money "
                    "work for everyone. We serve millions of customers.\nThe role...",
     "location": "London, United Kingdom"},
    {"description": "Short one.", "location": "London; Remote"},
    {"description": "", "location": "Cardiff"},
]


def test_about_blurb_extracted():
    c = company_enricher.enrich({"name": "Monzo", "slug": "monzo"}, POSTINGS, NoClaude(), NOW)
    assert "digital bank" in c.description.lower()
    assert c.description.count(".") <= 3          # 1-2 sentences


def test_hq_inferred_from_locations():
    c = company_enricher.enrich({"name": "Monzo", "slug": "monzo"}, POSTINGS, NoClaude(), NOW)
    assert c.hq_location == "London"
    assert "approximated" in c.notes


def test_confidence_medium_with_desc_and_hq():
    c = company_enricher.enrich({"name": "Monzo", "slug": "monzo"}, POSTINGS, NoClaude(), NOW)
    assert c.data_confidence == "Medium"


def test_low_confidence_when_no_descriptions():
    postings = [{"description": "", "location": ""}]
    c = company_enricher.enrich({"name": "X", "slug": "x"}, postings, NoClaude(), NOW)
    assert c.data_confidence == "Low"
    assert c.description == ""


def test_claude_path_sets_high_confidence():
    class FakeClaude:
        def extract_company(self, text, name):
            return {"description": "An AI lab.", "industry": "AI",
                    "hq_location": "San Francisco, USA", "year_founded": 2021}
    c = company_enricher.enrich({"name": "Acme", "slug": "acme"},
                                [{"description": "About Acme...", "location": "SF"}],
                                FakeClaude(), NOW)
    assert c.data_confidence == "High"
    assert c.industry == "AI" and c.year_founded == "2021"


def test_company_index_roundtrip(tmp_path):
    c = company_enricher.enrich({"name": "Monzo", "slug": "monzo"}, POSTINGS, NoClaude(), NOW)
    cdir = tmp_path / "companies"
    company_index.write_company(cdir, c)
    n = company_index.rebuild_index(cdir, tmp_path / "data" / "company_index.jsonl")
    assert n == 1
    import json
    row = json.loads((tmp_path / "data" / "company_index.jsonl").read_text())
    assert row["slug"] == "monzo" and row["hq_location"] == "London"


def test_company_notes_preserved_on_re_enrich(tmp_path):
    from outputs import md_writer
    cdir = tmp_path / "companies"
    c = company_enricher.enrich({"name": "Monzo", "slug": "monzo"}, POSTINGS, NoClaude(), NOW)
    path = company_index.write_company(cdir, c)
    # user adds a note
    txt = path.read_text().replace("## My notes\n", "## My notes\n\nGreat culture.\n")
    path.write_text(txt)
    company_index.write_company(cdir, c)          # re-enrich
    _, body = md_writer.parse_md(path)
    assert "Great culture." in body
