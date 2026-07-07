"""cvMail adapter — network-free, against canned board/detail HTML."""
from scrapers.ats.cvmail import CvMailFetcher, board_url, normalize_job_url
from scrapers.ladder import detect_ats
from scrapers.result import EMPTY, OK
from services import discovery

BASE = "https://fsr.cvmailuk.com/mishcon/main.cfm?page=jobBoard"


def _board(rows, pages=1, token="tok-1"):
    """Board page: header (Job Title/Department/Location), rows, optional paging."""
    header = """
    <table><tr class="cvmJobBoardHeader">
      <td class="jbTableHeaderCaptionStyle"><table><tr><td>
        <a href="main.cfm?page=jobboard&sortField=1">Job Title</a></td></tr></table></td>
      <td class="jbTableHeaderCaptionStyle">Department</td>
      <td class="jbTableHeaderCaptionStyle">Location</td>
    </tr>"""
    body = ""
    for i, (title, dept, loc) in enumerate(rows):
        href = (f"main.cfm?page=jobSpecific&amp;jobId={1000 + i}"
                "&amp;rcd=559311&amp;queryString=srxksl&#x25;3D1")
        body += f"""
        <tr class="{'odd' if i % 2 else 'even'}">
          <td class="jbTableTextStyle">
            <a href="{href}" class="jobMoreDetailCaptionStyle">{title}</a></td>
          <td class="jbTableTextStyle">{dept}</td>
          <td class="jbTableTextStyle">{loc}</td>
        </tr>"""
    paging = ""
    if pages > 1:
        options = "".join(f'<option value="{p}">{p}</option>' for p in range(1, pages + 1))
        paging = f"""
        <form name="paging" method="post"
              action="main.cfm?page=jobBoard&amp;rcd=559311&amp;filter=">
          <input type="hidden" name="start_row" value="1">
          <input type="hidden" name="jump_to" value="1">
          <input type="hidden" name="x-token" value="{token}">
          <select name="jump_page">{options}</select>
          <input type="submit" name="next_page" value="Next &gt;&gt;">
        </form>"""
    return header + body + "</table>" + paging


DETAIL = """
<table>
  <tr><td class="jobFieldStyle">Job Title</td><td width="15"></td>
      <td class="jobValueStyle">AI &amp; Innovation Lead</td></tr>
  <tr><td class="jobFieldStyle">Location</td><td width="15"></td>
      <td class="jobValueStyle">London</td></tr>
  <tr><td class="jobFieldStyle">Duration</td><td width="15"></td>
      <td class="jobValueStyle">6 month FTC</td></tr>
  <tr><td colspan="3" class="jobFieldStyle">
    <table><tr><td class="jobFieldStyle show">Description</td></tr>
      <tr><td class="jobValueStyle" id="firm-jobdescription">
        <p><strong>The Role</strong></p><p>Shape the AI agenda.</p>
        <ul><li>Full time position</li></ul>
      </td></tr></table>
  </td></tr>
</table>"""


class FakeHttp:
    def __init__(self, get_pages, post_pages=None):
        self.get_pages = dict(get_pages)     # url -> html
        self.post_pages = list(post_pages or [])   # consumed in order
        self.posts = []                      # (url, data) log

    def get(self, url, **kw):
        return type("R", (), {"text": self.get_pages[url]})()

    def post(self, url, data=None, **kw):
        self.posts.append((url, dict(data or {})))
        return type("R", (), {"text": self.post_pages.pop(0)})()


COMPANY = {"slug": "mishcon", "careers_url": BASE}


def test_board_url_from_deep_link():
    deep = "https://fsr.cvmailuk.com/mishcon/main.cfm?page=jobSpecific&jobId=78477&rcd=607833"
    assert board_url(deep) == BASE
    assert board_url("https://fsr.cvmailuk.com/mishcon/") == BASE


def test_normalize_job_url_drops_volatile_params():
    href = ("main.cfm?page=jobSpecific&amp;jobId=78477"
            "&amp;rcd=607833&amp;queryString=srxksl&#x25;3D1")
    assert normalize_job_url(href, BASE) == \
        "https://fsr.cvmailuk.com/mishcon/main.cfm?page=jobSpecific&jobId=78477"


def test_listing_maps_title_location_url():
    html = _board([("AI & Innovation Lead", "Technology", "London"),
                   ("Data Architect", "Technology", "Hong Kong")])
    f = CvMailFetcher(COMPANY, FakeHttp({BASE: html}))
    res = f.listing()
    assert res.status == OK and len(res.postings) == 2
    first = res.postings[0]
    assert first["title"] == "AI & Innovation Lead"
    assert first["location"] == "London"
    assert first["url"].endswith("main.cfm?page=jobSpecific&jobId=1000")
    assert first["posted_date"] is None
    assert first["source_detail"] == "cvMail"
    assert res.postings[1]["location"] == "Hong Kong"


def test_listing_location_falls_back_to_last_cell():
    html = _board([("Product Lead", "London", "")]).replace(
        '<td class="jbTableHeaderCaptionStyle">Location</td>', "")
    html = html.replace('<td class="jbTableTextStyle"></td>', "")
    f = CvMailFetcher(COMPANY, FakeHttp({BASE: html}))
    assert f.listing().postings[0]["location"] == "London"


def test_listing_paginates_via_form_post():
    p1 = _board([("Role A", "Tech", "London")], pages=2, token="tok-1")
    p2 = _board([("Role B", "Tech", "Leeds")])
    http = FakeHttp({BASE: p1}, post_pages=[p2])
    res = CvMailFetcher(COMPANY, http).listing()
    assert [p["title"] for p in res.postings] == ["Role A", "Role B"]
    (url, data), = http.posts
    assert url == "https://fsr.cvmailuk.com/mishcon/main.cfm?page=jobBoard&rcd=559311&filter="
    assert data["jump_to"] == "2" and data["x-token"] == "tok-1"


def test_empty_board_is_empty():
    res = CvMailFetcher(COMPANY, FakeHttp({BASE: _board([])})).listing()
    assert res.status == EMPTY and res.postings == []


def test_detail_markdown_and_extra_fields():
    url = "https://fsr.cvmailuk.com/mishcon/main.cfm?page=jobSpecific&jobId=78477"
    f = CvMailFetcher(COMPANY, FakeHttp({BASE: "", url: DETAIL}))
    body = f.detail(url)
    assert "**Duration:** 6 month FTC" in body
    assert "**The Role**" in body and "Shape the AI agenda." in body
    assert "- Full time position" in body
    assert "Job Title" not in body and "London" not in body   # captured in listing


def test_detect_ats_marker():
    assert detect_ats({"careers_url": BASE}, http=None) == "cvmail"


def test_discovery_from_deep_job_link():
    deep = "https://fsr.cvmailuk.com/mishcon/main.cfm?page=jobSpecific&jobId=78477&rcd=607833&srxksl=1"
    info = discovery._from_url(deep)
    assert info["ats_type"] == "cvmail"
    assert info["ats_slug"] == "mishcon"
    assert info["name"] == "Mishcon"
    assert info["careers_url"] == BASE
