"""Shared HTML -> text/markdown helpers for ATS adapters."""
from __future__ import annotations

import html as _html
import re

from bs4 import BeautifulSoup
from markdownify import markdownify as _md


def html_to_text(content: str) -> str:
    if not content:
        return ""
    soup = BeautifulSoup(_html.unescape(content), "lxml")
    return soup.get_text("\n", strip=True)


def html_to_markdown(content: str) -> str:
    """Convert an ATS HTML description to Markdown (headings, lists, bold/italic,
    links). Handles both raw and entity-escaped HTML."""
    if not content:
        return ""
    md = _md(_html.unescape(content), heading_style="ATX", bullets="-",
             strip=["script", "style"])
    md = re.sub(r"\n{3,}", "\n\n", md)        # collapse runs of blank lines
    return md.strip()
