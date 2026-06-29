"""HTML -> Markdown conversion for job descriptions."""
from scrapers.htmltext import html_to_markdown

HTML = ("<h2>About Capsa</h2><p>The <strong>AI Operating System</strong> for "
        "<em>private capital</em>.</p><h3>The role</h3><ul><li>Own the product</li>"
        "<li>Lead the <a href=\"https://x.com\">team</a></li></ul>")


def test_headings():
    md = html_to_markdown(HTML)
    assert "## About Capsa" in md
    assert "### The role" in md


def test_bold_italic():
    md = html_to_markdown(HTML)
    assert "**AI Operating System**" in md
    assert "*private capital*" in md


def test_bullets_and_links():
    md = html_to_markdown(HTML)
    assert "- Own the product" in md
    assert "[team](https://x.com)" in md


def test_entity_escaped_html_also_works():
    # Greenhouse ships entity-escaped HTML
    escaped = "&lt;h2&gt;Title&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;Item&lt;/li&gt;&lt;/ul&gt;"
    md = html_to_markdown(escaped)
    assert "## Title" in md
    assert "- Item" in md


def test_nested_bold_collapsed():
    # <b><strong> nesting otherwise emits ****text**** which renders oddly
    md = html_to_markdown("<p><b><strong>About Cleo</strong></b></p>")
    assert "**About Cleo**" in md
    assert "****" not in md


def test_empty():
    assert html_to_markdown("") == ""


def test_no_excessive_blank_lines():
    md = html_to_markdown("<p>a</p><p>b</p><p>c</p>")
    assert "\n\n\n" not in md
