"""cvMail (Thomson Reuters) ATS adapter — e.g. Mishcon de Reya (SPEC: cvmail-adapter.md).

The legal-sector ATS behind `fsr.cvmailuk.com/<firm>/`. No JSON API — a server-
rendered ColdFusion board, so this is the first HTML-scraping ATS rung and is
robots-checked (constitution §2). The board table lists title + firm-configurable
columns (header cells name them — Location is found by header, not position);
>50 jobs paginate via a form POST that needs the page's `x-token` and the session
cookie, so pages are walked through the shared HttpClient session. Job links carry
a per-render `rcd` param — URLs are normalised to `page=jobSpecific&jobId=N` so
they are stable across runs (URL-based dedup/lifecycle would churn otherwise).
Detail pages are label/value rows; Description converts to Markdown and the other
fields (Closing Date, Duration, …) are prepended so employment/salary text reaches
the downstream classifiers. No posted date exists anywhere ⇒ None (kept by the
recency filter).
"""
from __future__ import annotations

import html as _html
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.htmltext import html_to_markdown
from scrapers.result import EMPTY, OK, ListingResult

_MAX_PAGES = 20


def board_url(careers_url: str) -> str:
    """Any cvMail link for a firm (deep job link included) -> its jobBoard URL."""
    p = urlsplit(careers_url)
    firm = next((seg for seg in p.path.split("/") if seg), "")
    firm = firm.removesuffix("main.cfm")
    return f"{p.scheme}://{p.netloc}/{firm}/main.cfm?page=jobBoard"


def normalize_job_url(href: str, base: str) -> str:
    """Absolutise + strip volatile params: keep only page=jobSpecific&jobId=N."""
    absolute = urljoin(base, _html.unescape(href))
    q = parse_qs(urlsplit(absolute).query)
    job_id = (q.get("jobId") or q.get("jobid") or [""])[0]
    p = urlsplit(absolute)
    return f"{p.scheme}://{p.netloc}{p.path}?page=jobSpecific&jobId={job_id}"


def _location_column(soup) -> int | None:
    """Index of the Location column among the row's text cells. The title cell is
    also `jbTableTextStyle`, so both headers and cells count from 0 including it."""
    headers = [" ".join(td.get_text(" ", strip=True).split())
               for td in soup.select("td.jbTableHeaderCaptionStyle")]
    for i, h in enumerate(headers):
        if "location" in h.lower():
            return i
    return None


def _parse_board(html: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    loc_idx = _location_column(soup)
    out = []
    for row in soup.select("tr.odd, tr.even"):
        link = row.select_one('a[href*="jobSpecific"]')
        if link is None:
            continue
        cells = row.select("td.jbTableTextStyle")
        texts = [" ".join(td.get_text(" ", strip=True).split()) for td in cells]
        if loc_idx is not None and loc_idx < len(texts):
            location = texts[loc_idx]
        else:
            location = texts[-1] if len(texts) > 1 else ""
        out.append({
            "title": " ".join(link.get_text(" ", strip=True).split()),
            "location": location,
            "url": normalize_job_url(link["href"], base),
            "posted_date": None,      # cvMail exposes no dates
            "description": "",        # detail page brings the body
            "source_type": "ATS",
            "source_detail": "cvMail",
        })
    return out


def _paging_form(html: str, base: str) -> tuple[str, dict, int] | None:
    """(action_url, post_data, total_pages) of the board's paging form, if any."""
    soup = BeautifulSoup(html, "lxml")
    form = soup.find("form", attrs={"name": "paging"})
    if form is None:
        return None
    action = urljoin(base, _html.unescape(form.get("action") or ""))
    data = {inp.get("name"): inp.get("value", "")
            for inp in form.find_all("input", type="hidden") if inp.get("name")}
    pages = len(soup.select('select[name="jump_page"] option')) or 1
    return action, data, pages


class CvMailFetcher:
    needs_detail = True
    live_listing = True   # ATS board lists only currently-open roles
    check_robots = True        # HTML scrape, not a documented JSON API
    rung_name = "cvmail"

    def __init__(self, company, http, query=None):
        self.company, self.http = company, http
        self.careers_url = board_url(company["careers_url"])   # robots-checked by the ladder

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def listing(self) -> ListingResult:
        html = self.http.get(self.careers_url).text
        out = _parse_board(html, self.careers_url)
        form = _paging_form(html, self.careers_url)
        if form:
            action, data, pages = form
            for page in range(2, min(pages, _MAX_PAGES) + 1):
                data = {**data, "jump_to": str(page), "next_page": "Next >>"}
                html = self.http.post(action, data=data).text
                out.extend(_parse_board(html, self.careers_url))
                nxt = _paging_form(html, self.careers_url)
                if nxt is None:
                    break
                action, data, _ = nxt   # x-token is per-render — refresh each page
        return ListingResult(OK if out else EMPTY, out, self.rung_name)

    def detail(self, url) -> str:
        if not url:
            return ""
        soup = BeautifulSoup(self.http.get(url).text, "lxml")
        extras, description = [], ""
        for label_td in soup.select("td.jobFieldStyle"):
            if label_td.find("table") is not None:
                continue   # wrapper cell containing a nested field table, not a label
            label = " ".join(label_td.get_text(" ", strip=True).split())
            if len(label) > 60:
                continue
            value_td = label_td.find_next("td", class_="jobValueStyle")
            if not label or value_td is None:
                continue
            if label.lower() == "description":
                description = html_to_markdown(value_td.decode_contents())
            elif label.lower() not in ("job title", "location"):   # already captured
                value = " ".join(value_td.get_text(" ", strip=True).split())
                if value:
                    extras.append(f"**{label}:** {value}")
        # de-dup: nested tables can surface the same label twice
        extras = list(dict.fromkeys(extras))
        return "\n\n".join(p for p in ["\n".join(extras), description] if p).strip()
