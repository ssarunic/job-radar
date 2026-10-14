"""Screenloop ATS adapter — e.g. Homesearch (SPEC: screenloop-adapter.md).

Screenloop careers pages (`app.screenloop.com/careers/{slug}`) are server-rendered
Rails views: the React board is hydrated from a `data-react-props` JSON attribute,
so the plain HTML already carries the whole listing (`jobPosts[]`) and, on each
job page, the posting (`previewJobPost` + `jobPostHtmlString`). There is no public
JSON endpoint (the `/api/...` routes want a sign-in), so this is an HTML-scraping
rung and robots-checked (constitution §2): one GET for the board, one per kept
posting for the body. Listing rows carry no date, description or employment type;
the job page carries employment type, work type and salary, which are prepended to
the Markdown body as header lines (the Workday/Oracle convention) so the downstream
classifiers see them. No posted date exists anywhere ⇒ None (recency-exempt via
`live_listing`).
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from scrapers.htmltext import html_to_markdown
from scrapers.result import EMPTY, OK, ListingResult

HOST = "https://app.screenloop.com"
BOARD = HOST + "/careers/{slug}"
JOB_URL = HOST + "/careers/{slug}/job_posts/{id}"
BOARD_COMPONENT = "applicant_tracking/Careers/CareersPage"
JOB_COMPONENT = "applicant_tracking/Jobs/JobPostPage"

# Screenloop stores ISO long-form country names; the location filter keys on the
# short forms people write in ads.
_COUNTRY_BY_CODE = {"GB": "United Kingdom", "US": "United States"}


def slug_from_url(url: str) -> str:
    """`…screenloop.com/careers/{slug}[/job_posts/N]` -> slug ('' if not a careers link)."""
    parts = [p for p in urlsplit(url).path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "careers":
        return parts[1]
    return ""


def board_url(careers_url: str) -> str:
    """Any Screenloop link for a company (deep job link included) -> its board URL."""
    slug = slug_from_url(careers_url)
    return BOARD.format(slug=slug) if slug else careers_url


def react_props(html: str, component: str) -> dict | None:
    """The JSON a page hands to the named React component, or None if absent."""
    soup = BeautifulSoup(html or "", "lxml")
    tag = soup.find(attrs={"data-react-class": component})
    if tag is None:
        return None
    try:
        props = json.loads(tag.get("data-react-props") or "")
    except ValueError:
        return None
    return props if isinstance(props, dict) else None


def _location(loc: dict | None) -> str:
    """`city, country` from the structured location (country short-named by code);
    falls back to the office label ("London - HQ") when no city is set."""
    loc = loc if isinstance(loc, dict) else {}
    city = (loc.get("city") or "").strip()
    code = (loc.get("countryCode") or "").strip().upper()
    country = _COUNTRY_BY_CODE.get(code) or (loc.get("country") or "").strip()
    bits = [b for b in (city or (loc.get("name") or "").strip(), country) if b]
    return ", ".join(dict.fromkeys(bits))


def parse_board(html: str, slug: str) -> list[dict]:
    props = react_props(html, BOARD_COMPONENT) or {}
    out = []
    for jp in props.get("jobPosts") or []:
        if not isinstance(jp, dict) or not jp.get("id"):
            continue
        title = (jp.get("name") or (jp.get("job") or {}).get("name") or "").strip()
        if not title:
            continue
        out.append({
            "title": title,
            "location": _location(jp.get("location")),
            "url": JOB_URL.format(slug=slug, id=jp["id"]),
            "posted_date": None,      # Screenloop exposes no dates
            "description": "",        # the job page brings the body
            "employment_type": "",    # job page only — carried as a header line
            "workplace": "",
            "salary_text": "",
            "source_type": "ATS",
            "source_detail": "Screenloop",
        })
    return out


def _salary_text(sal) -> str:
    if isinstance(sal, str):
        return sal.strip()
    if isinstance(sal, dict):
        return " ".join(str(v) for v in sal.values() if v not in (None, "", 0)).strip()
    return ""


def parse_job(html: str) -> str:
    """Posting body as Markdown, prefixed with `Employment type:` / `Workplace type:`
    (/ `Salary:`) header lines from the structured preview block."""
    props = react_props(html, JOB_COMPONENT)
    if not props:
        return ""
    meta = props.get("previewJobPost") or {}
    header = (f"Employment type: {meta.get('employmentType') or ''}\n"
              f"Workplace type: {meta.get('locationType') or ''}\n")
    salary = _salary_text(meta.get("salary"))
    if salary:
        header += f"Salary: {salary}\n"
    body = html_to_markdown(props.get("jobPostHtmlString") or "")
    return (header + "\n" + body).strip()


class ScreenloopFetcher:
    needs_detail = True
    live_listing = True        # the board lists only currently-published posts
    check_robots = True        # HTML scrape, not a documented JSON API
    rung_name = "screenloop"

    def __init__(self, company, http, query=None):
        self.company, self.http = company, http
        self.slug = company.get("ats_slug") or slug_from_url(company.get("careers_url", ""))
        self.careers_url = BOARD.format(slug=self.slug)   # robots-checked by the ladder

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self) -> ListingResult:
        html = self.http.get(self.careers_url).text
        out = parse_board(html, self.slug)
        return ListingResult(OK if out else EMPTY, out, self.rung_name)

    def detail(self, url) -> str:
        if not url:
            return ""
        return parse_job(self.http.get(url).text)
