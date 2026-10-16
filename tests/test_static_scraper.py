"""Static-HTML rung — link resolution when the job card is itself the anchor."""
import yaml

from scrapers import static_scraper

BASE = "https://www.daytona.io/careers"


def _framer_card(title, dept, loc, href):
    """A Daytona-style Framer card: the <a> is the card; three 'Job Title' blocks."""
    return f"""
    <a data-framer-name="Variant 1" href="{href}" target="_blank">
      <div data-framer-name="Job Title"><p>{title}</p></div>
      <div>
        <div><div><img></div><div data-framer-name="Job Title"><p>{dept}</p></div></div>
        <div><div><img></div><div data-framer-name="Job Title"><p>{loc}</p></div></div>
        <div><div data-framer-name="Job Title"><p></p></div></div>
      </div>
    </a>"""


class FakeHttp:
    def __init__(self, html):
        self.html = html

    def get(self, url, **kw):
        return type("R", (), {"text": self.html})()


def _daytona_selectors():
    with open("config/overrides/daytona.yaml") as f:
        return yaml.safe_load(f)["selectors"]


def test_anchor_card_uses_its_own_href():
    html = (_framer_card("Product Manager, GPU Sandboxes", "Product", "SF or Croatia",
                         "https://app.notion.com/p/Product-Manager-GPU-Sandboxes-3b22?pvs=21")
            + _framer_card("Team Lead, GPU Sandboxes", "Engineering", "SF",
                           "https://app.notion.com/p/Team-Lead-GPU-Sandboxes-3b22?pvs=21"))
    rows, status = static_scraper.listing(BASE, _daytona_selectors(), FakeHttp(html))
    assert status == "ok" and len(rows) == 2
    pm = rows[0]
    assert pm["title"] == "Product Manager, GPU Sandboxes"
    assert pm["location"] == "SF or Croatia"
    assert pm["url"] == "https://app.notion.com/p/Product-Manager-GPU-Sandboxes-3b22?pvs=21"
    assert pm["source_type"] == "CompanySite" and pm["source_detail"] == "StaticHTML"
    assert rows[1]["location"] == "SF"


def test_nested_anchor_still_preferred_and_link_selector_honoured():
    html = """<div class="job"><h3>Head of Product</h3><span class="loc">London</span>
              <a class="other" href="/share">share</a>
              <a class="apply" href="/jobs/1">Apply</a></div>"""
    sel = {"job_card": ".job", "title": "h3", "location": ".loc"}
    rows, _ = static_scraper.listing(BASE, sel, FakeHttp(html))
    assert rows[0]["url"] == "https://www.daytona.io/share"      # first nested <a>
    rows, _ = static_scraper.listing(BASE, {**sel, "link": "a.apply"}, FakeHttp(html))
    assert rows[0]["url"] == "https://www.daytona.io/jobs/1"
    # an explicit link selector that matches nothing yields no URL, even on an anchor card
    html = '<a class="job" href="/x"><h3>Head of Product</h3></a>'
    sel = {"job_card": "a.job", "title": "h3", "link": ".nope"}
    rows, _ = static_scraper.listing(BASE, sel, FakeHttp(html))
    assert rows[0]["url"] == ""


def test_empty_listing_reports_empty():
    http = FakeHttp("<html></html>")
    assert static_scraper.listing(BASE, _daytona_selectors(), http) == ([], "empty")
