"""Rung 3 — static HTML via the shared HTTP client + BeautifulSoup (SPEC §4.3)."""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup


def listing(url: str, selectors: dict, http):
    """Return (postings, status). status in {ok, empty}."""
    soup = BeautifulSoup(http.get(url).text, "lxml")
    out = []
    for card in soup.select(selectors["job_card"]):
        title_el = card.select_one(selectors["title"]) if selectors.get("title") else None
        loc_el = card.select_one(selectors["location"]) if selectors.get("location") else None
        link_el = card.select_one(selectors["link"]) if selectors.get("link") else card.find("a")
        href = link_el.get("href") if link_el else ""
        out.append({
            "title": (title_el.get_text(strip=True) if title_el else ""),
            "location": (loc_el.get_text(strip=True) if loc_el else ""),
            "url": urljoin(url, href) if href else "",
            "posted_date": None,
            "description": "",
            "employment_type": "",
            "salary_text": "",
            "source_type": "CompanySite",
            "source_detail": "StaticHTML",
        })
    return out, ("ok" if out else "empty")


def detail(url: str, http) -> str:
    soup = BeautifulSoup(http.get(url).text, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)
