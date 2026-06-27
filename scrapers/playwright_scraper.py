"""Rung 2 — Playwright for JS-rendered / Cloudflare-protected sites (SPEC §4.2).

One PlaywrightSession per company reuses a single browser context, so the
Cloudflare clearance cookie obtained on the listing page carries over to detail
pages. If a managed challenge can't be cleared, the company is reported
``blocked`` rather than crashing the run.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")

CHALLENGE_MARKERS = ("just a moment", "enable javascript and cookies",
                     "checking your browser", "cf-chl", "challenge-platform")


def _looks_challenged(page) -> bool:
    try:
        title = (page.title() or "").lower()
        if any(m in title for m in CHALLENGE_MARKERS):
            return True
        body = (page.inner_text("body") or "").lower()[:600]
        return any(m in body for m in CHALLENGE_MARKERS)
    except Exception:
        return False


class PlaywrightSession:
    def __init__(self, settings: dict):
        self.settings = settings
        self.timeout = settings.get("request_timeout", 20) * 1000
        self._pw = None
        self._stealth_cm = None
        self.browser = None
        self.ctx = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._stealth_cm = None
        if self.settings.get("stealth"):
            from playwright_stealth import Stealth
            self._stealth_cm = Stealth().use_sync(sync_playwright())
            self._pw = self._stealth_cm.__enter__()
        else:
            self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            headless=self.settings.get("headless", True),
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.ctx = self.browser.new_context(
            user_agent=UA,
            locale="en-GB",
            viewport={"width": 1366, "height": 900},
        )
        self.ctx.set_default_timeout(self.timeout)
        return self

    def __exit__(self, *exc):
        for closer in (self.ctx, self.browser):
            try:
                if closer:
                    closer.close()
            except Exception:
                pass
        if self._stealth_cm:
            try:
                self._stealth_cm.__exit__(*exc)
            except Exception:
                pass
        elif self._pw:
            self._pw.stop()

    def _goto_clear(self, page, url: str, wait_for: str | None) -> str:
        """Navigate and attempt to ride out a Cloudflare managed challenge.
        Returns 'ok' | 'blocked'."""
        page.goto(url, wait_until="domcontentloaded")
        deadline = time.monotonic() + (self.timeout / 1000) * 2
        while time.monotonic() < deadline:
            if not _looks_challenged(page):
                break
            page.wait_for_timeout(1500)  # let CF JS run
        if _looks_challenged(page):
            return "blocked"
        if wait_for:
            try:
                page.wait_for_selector(wait_for, timeout=self.timeout)
            except Exception:
                pass  # selector may legitimately be absent (no results)
        return "ok"

    def listing(self, url: str, selectors: dict, wait_for: str | None):
        """Return (postings, status). status in {ok, blocked, empty}."""
        page = self.ctx.new_page()
        try:
            status = self._goto_clear(page, url, wait_for or selectors.get("job_card"))
            if status == "blocked":
                return [], "blocked"
            cards = page.locator(selectors["job_card"])
            n = cards.count()
            out = []
            for i in range(n):
                card = cards.nth(i)
                out.append({
                    "title": _safe_text(card, selectors.get("title")),
                    "location": _safe_text(card, selectors.get("location")),
                    "url": _safe_href(card, selectors.get("link"), page.url),
                    "posted_date": _safe_text(card, selectors.get("date")) or None,
                    "description": "",
                    "employment_type": "",
                    "salary_text": "",
                    "source_type": "CompanySite",
                    "source_detail": "Playwright",
                })
            return out, ("ok" if out else "empty")
        finally:
            page.close()

    def warm(self, url: str) -> bool:
        """Load a page to establish Cloudflare clearance for the context.
        Returns True if the page is usable (not stuck on a challenge)."""
        page = self.ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            deadline = time.monotonic() + (self.timeout / 1000) * 2
            while time.monotonic() < deadline and _looks_challenged(page):
                page.wait_for_timeout(1500)
            self._warm_page = page  # keep open; in-page fetch runs from here
            return not _looks_challenged(page)
        except Exception:
            page.close()
            return False

    def fetch_json(self, url: str, tries: int = 12):
        """Fetch JSON via fetch() inside the warmed page (rides CF clearance).
        Returns parsed JSON or None."""
        import json as _json
        page = getattr(self, "_warm_page", None)
        if page is None:
            return None
        js = ("async (u) => { try { const r = await fetch(u, {credentials:'include'}); "
              "return {s:r.status, b: await r.text()}; } "
              "catch(e){ return {s:-1, b:String(e)}; } }")
        for _ in range(tries):
            res = page.evaluate(js, url)
            if res["s"] == 200:
                try:
                    return _json.loads(res["b"])
                except Exception:
                    return None
            page.wait_for_timeout(1500)
        return None

    def detail(self, url: str) -> str:
        page = self.ctx.new_page()
        try:
            status = self._goto_clear(page, url, "body")
            if status == "blocked":
                return ""
            return page.inner_text("body") or ""
        except Exception:
            return ""
        finally:
            page.close()


def _safe_text(card, sel: str | None) -> str:
    if not sel:
        return ""
    try:
        loc = card.locator(sel).first
        if loc.count() == 0:
            return ""
        return (loc.inner_text() or "").strip()
    except Exception:
        return ""


def _safe_href(card, sel: str | None, base_url: str) -> str:
    from urllib.parse import urljoin
    try:
        loc = card.locator(sel).first if sel else card.locator("a").first
        if loc.count() == 0:
            return ""
        href = loc.get_attribute("href") or ""
        return urljoin(base_url, href) if href else ""
    except Exception:
        return ""
