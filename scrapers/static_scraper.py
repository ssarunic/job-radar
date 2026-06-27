"""Rung 3 — static HTML via requests + BeautifulSoup (SPEC §4.3)."""
from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def _headers(settings: dict) -> dict:
    return {"User-Agent": settings.get("user_agent", "JobSeekAssistant")}


def listing(url: str, selectors: dict, settings: dict):
    """Return (postings, status)."""
    r = requests.get(url, headers=_headers(settings),
                     timeout=settings.get("request_timeout", 20))
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
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


def detail(url: str, settings: dict) -> str:
    r = requests.get(url, headers=_headers(settings),
                     timeout=settings.get("request_timeout", 20))
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)
