"""Workable ATS adapter — Rung 1 JSON API (SPEC §4.1, `specs/workable-adapter.md`).

Two public, unauthenticated endpoints the `apply.workable.com/{slug}` board itself
calls (constitution §2 — the JSON the browser already fetches):

- listing: `POST /api/v3/accounts/{slug}/jobs` — title, workplace, country list,
  published date; 10 per page, continued with the body's `token` = `nextPage`.
- detail:  `GET /api/v2/accounts/{slug}/jobs/{shortcode}` — description /
  requirements / benefits HTML. Listing rows carry no body, so `NEEDS_DETAIL`.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from scrapers.htmltext import html_to_markdown

LISTING = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"
DETAIL = "https://apply.workable.com/api/v2/accounts/{slug}/jobs/{code}"
BOARD = "https://apply.workable.com/{slug}/"
JOB_URL = "https://apply.workable.com/{slug}/j/{code}/"
NEEDS_DETAIL = True
_MAX_PAGES = 50           # 500 roles — far beyond any board we track


def _location(job: dict) -> str:
    """Filter-friendly label list: one `city, country` per entry in `locations[]`
    (falling back to the primary `location`), prefixed `Remote — ` for remote
    roles so `location_filter` can judge each country's eligibility."""
    entries = [e for e in (job.get("locations") or []) if isinstance(e, dict)]
    if not entries and isinstance(job.get("location"), dict):
        entries = [job["location"]]
    remote = job.get("remote") or (job.get("workplace") or "").lower() == "remote"
    labels = []
    for e in entries:
        place = ", ".join(p for p in ((e.get("city") or "").strip(),
                                      (e.get("region") or "").strip(),
                                      (e.get("country") or "").strip()) if p)
        if remote:
            place = f"Remote — {place}" if place else "Remote"
        if place and place not in labels:
            labels.append(place)
    if not labels and remote:
        labels.append("Remote")
    return "; ".join(labels)


def _listed(job: dict) -> bool:
    state = (job.get("state") or "published").lower()
    return state == "published" and not job.get("isInternal")


def fetch_listing(ats_slug: str, http) -> list[dict]:
    out, token, total = [], None, None
    for _ in range(_MAX_PAGES):
        body = {"query": "", "location": [], "department": [], "worktype": [], "remote": []}
        if token:
            body["token"] = token
        data = http.post_json(LISTING.format(slug=ats_slug), json=body)
        if not isinstance(data, dict):
            break
        total = data.get("total", 0) if total is None else total
        results = data.get("results") or []
        for j in results:
            if not _listed(j):
                continue
            code = j.get("shortcode") or ""
            out.append({
                "title": (j.get("title") or "").strip(),
                "location": _location(j),
                "url": JOB_URL.format(slug=ats_slug, code=code),
                "posted_date": j.get("published"),
                "freshness_date": j.get("published"),
                "description": "",
                "employment_type": "",      # not exposed by the public API
                "salary_text": "",
                "source_type": "ATS",
                "source_detail": "Workable",
            })
        token = data.get("nextPage")
        if not results or not token or len(out) >= total:
            break
    return out


def parse_job_url(url: str) -> tuple[str, str] | None:
    """`https://apply.workable.com/{slug}/j/{SHORTCODE}/…` -> (slug, shortcode)."""
    parts = [p for p in urlsplit(url).path.split("/") if p]
    if len(parts) >= 3 and parts[1] == "j":
        return parts[0], parts[2]
    return None


def fetch_detail(url: str, http) -> str:
    """Posting body as Markdown: description + labelled requirements/benefits
    (the label lets requirements extraction find the section)."""
    ref = parse_job_url(url)
    if not ref:
        return ""
    slug, code = ref
    data = http.get_json(DETAIL.format(slug=slug, code=code))
    if not isinstance(data, dict):
        return ""
    chunks = [html_to_markdown(data.get("description") or "")]
    for key, heading in (("requirements", "Requirements"), ("benefits", "Benefits")):
        md = html_to_markdown(data.get(key) or "")
        if md:
            chunks.append(f"## {heading}\n\n{md}")
    return "\n\n".join(c for c in chunks if c).strip()
