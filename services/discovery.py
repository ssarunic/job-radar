"""Auto-detect a company's ATS for `follow` — by name (probe ATS APIs) or URL.

Returns a companies.csv-ready dict, or None if nothing matched (the user can then
add a workday/talemetry/custom entry by hand with a careers URL)."""
from __future__ import annotations

from urllib.parse import urlsplit

from models.job_posting import _slugify

_GH = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
_ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{}"
_LEVER = "https://api.lever.co/v0/postings/{}?mode=json"
_SR = "https://api.smartrecruiters.com/v1/companies/{}/postings?limit=1"

CAREERS = {
    "greenhouse": "https://job-boards.greenhouse.io/{}",
    "ashby": "https://jobs.ashbyhq.com/{}",
    "lever": "https://jobs.lever.co/{}",
    "smartrecruiters": "https://jobs.smartrecruiters.com/{}",
}


def _slug_variants(name: str) -> list[str]:
    base = name.lower().strip()
    return list(dict.fromkeys([
        "".join(c for c in base if c.isalnum()),  # compact: "blackforestlabs"
        _slugify(name),                            # kebab:   "black-forest-labs"
        base.replace(" ", ""),
    ]))


def _probe(slug: str, http) -> str | None:
    """Return the ATS name whose board exists for this slug, else None."""
    def _try(url, ok):
        try:
            return ok(http.get_json(url))
        except Exception:
            return False
    if _try(_GH.format(slug), lambda d: isinstance(d, dict) and "jobs" in d):
        return "greenhouse"
    if _try(_ASHBY.format(slug), lambda d: isinstance(d, dict) and "jobs" in d):
        return "ashby"
    if _try(_LEVER.format(slug), lambda d: isinstance(d, list)):
        return "lever"
    # SR returns 200 even for unknown companies, so require an actual posting count
    if _try(_SR.format(slug), lambda d: isinstance(d, dict) and (d.get("totalFound") or 0) > 0):
        return "smartrecruiters"
    return None


def _from_name(name: str, http) -> dict | None:
    for slug in _slug_variants(name):
        ats = _probe(slug, http)
        if ats:
            return {"name": name, "slug": _slugify(name),
                    "careers_url": CAREERS[ats].format(slug),
                    "ats_type": ats, "ats_slug": slug, "priority": "medium"}
    return None


def _from_url(url: str, http=None) -> dict | None:
    host = urlsplit(url).netloc.lower()
    path = [p for p in urlsplit(url).path.split("/") if p]
    seg0 = path[0] if path else ""

    def mk(ats, ats_slug, careers=None, name=None):
        nm = name or (ats_slug.replace("-", " ").title() if ats_slug else host)
        return {"name": nm, "slug": _slugify(nm), "ats_type": ats,
                "ats_slug": ats_slug, "priority": "medium",
                "careers_url": careers or (CAREERS[ats].format(ats_slug)
                                           if ats in CAREERS and ats_slug else url)}

    if "ashbyhq" in host:
        return mk("ashby", seg0)
    if "greenhouse" in host or "grnh.se" in host:
        return mk("greenhouse", seg0)
    if "lever.co" in host:
        return mk("lever", seg0)
    if "smartrecruiters" in host:
        return mk("smartrecruiters", seg0)
    if "myworkdayjobs" in host:
        site = path[-1] if path else ""
        return mk("workday", "", careers=url, name=host.split(".")[0].title())
    # unknown host -> custom (Playwright); user can refine
    return mk("custom", "", careers=url, name=host.replace("www.", "").split(".")[0].title())


def discover(query: str, http) -> dict | None:
    q = query.strip()
    if q.lower().startswith("http"):
        return _from_url(q, http)
    return _from_name(q, http)
