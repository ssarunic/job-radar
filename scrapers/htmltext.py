"""Shared HTML -> text helper for ATS adapters."""
from __future__ import annotations

import html as _html

from bs4 import BeautifulSoup


def html_to_text(content: str) -> str:
    if not content:
        return ""
    soup = BeautifulSoup(_html.unescape(content), "lxml")
    return soup.get_text("\n", strip=True)
