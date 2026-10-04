"""Auto-detect a company's ATS for `follow` — by name (probe ATS APIs) or URL.

Returns a companies.csv-ready dict, or None if nothing matched (the user can then
add a workday/talemetry/custom entry by hand with a careers URL)."""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit

from models.job_posting import _slugify

_GH = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
_ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{}"
_LEVER = "https://api.lever.co/v0/postings/{}?mode=json"
_SR = "https://api.smartrecruiters.com/v1/companies/{}/postings?limit=1"
_WK = "https://apply.workable.com/api/v3/accounts/{}/jobs"

CAREERS = {
    "greenhouse": "https://job-boards.greenhouse.io/{}",
    "ashby": "https://jobs.ashbyhq.com/{}",
    "lever": "https://jobs.lever.co/{}",
    "smartrecruiters": "https://jobs.smartrecruiters.com/{}",
    "workable": "https://apply.workable.com/{}/",
}


# Leading host labels that say "this is the jobs site", not who the company is.
_GENERIC_LABELS = {"www", "careers", "career", "jobs", "job", "apply", "work",
                   "join", "hiring", "talent", "recruiting", "recruitment"}

# A Workday board linked from a branded careers page: tenant, wdN shard, site
# (an optional locale segment like /en-US/ sits between host and site).
_WD_LINK_RX = re.compile(
    r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[a-z]{2}/)?([\w-]+)",
    re.I)


def _host_name(host: str) -> str:
    """Company name hint from a host, skipping generic labels so
    careers.expediagroup.com → "Expediagroup", not "Careers"."""
    labels = [l for l in host.lower().split(".") if l]
    for label in labels[:-1]:                   # never the TLD
        if label not in _GENERIC_LABELS:
            return label.title()
    return (labels[0] if labels else host).title()


def _workday_board(body: str) -> tuple[str, str] | None:
    """(tenant, board URL) for the Workday site a careers page links to most."""
    hits = Counter((m.group(1).lower(), m.group(2).lower(), m.group(3))
                   for m in _WD_LINK_RX.finditer(body))
    if not hits:
        return None
    tenant, shard, site = hits.most_common(1)[0][0]
    return tenant, f"https://{tenant}.{shard}.myworkdayjobs.com/{site}"


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
    # Workable 404s unknown slugs but 200s some dormant accounts with total 0
    try:
        d = http.post_json(_WK.format(slug), json={"query": ""})
        if isinstance(d, dict) and (d.get("total") or 0) > 0:
            return "workable"
    except Exception:
        pass
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
    if host.endswith("workable.com"):
        # apply.workable.com/{slug}/j/{code} or the {slug}.workable.com alias
        sub = host.split(".")[0]
        slug = seg0 if sub in ("apply", "www", "workable") else sub
        if slug:
            return mk("workable", slug)
    if "myworkdayjobs" in host:
        # A pasted job/apply link (…/search/job/…/apply) must collapse to the
        # board — the adapter reads the site from the last path segment.
        board = _workday_board(url)
        return mk("workday", "", careers=board[1] if board else url,
                  name=host.split(".")[0].title())
    if "oraclecloud" in host:   # Oracle ORC — tenant subdomain is the name hint
        return mk("oracle", "", careers=url, name=host.split(".")[0].upper())
    if "recruitee.com" in host:                 # {slug}.recruitee.com (origin proxies the API)
        return mk("recruitee", "", careers=url, name=host.split(".")[0].title())
    if "cvmail" in host:   # fsr.cvmailuk.com/<firm>/… — Thomson Reuters cvMail (legal)
        board = f"{urlsplit(url).scheme}://{host}/{seg0}/main.cfm?page=jobBoard"
        return mk("cvmail", seg0, careers=board, name=seg0.title())
    if "revolutpeople" in host:   # revolutpeople.com/{tenant}/… — white-label ATS
        return mk("revolutpeople", seg0,
                  careers=f"https://revolutpeople.com/{seg0}/public/careers")
    if host.endswith("revolut.com") and seg0 == "careers":
        # Revolut's own board: their tenant 403s the public API, so the adapter
        # scrapes __NEXT_DATA__ from www.revolut.com/careers instead.
        return mk("revolutpeople", "revolut",
                  careers="https://www.revolut.com/careers", name="Revolut")

    # Unrecognised host: body-probe for an embedded ATS (esp. Talemetry, which has
    # no host marker). Cloudflare-protected sites (e.g. NatWest) will 403 here and
    # fall through to custom — set ats_type by hand for those (#2).
    nm = _host_name(host)
    if http is not None:
        try:
            raw = http.get(url).text
            body = raw.lower()
            if "talemetry" in body:
                origin = f"{urlsplit(url).scheme}://{host}"
                return mk("talemetry", "", careers=origin, name=nm)
            if "myworkdayjobs" in body:
                # The adapter derives its API from the Workday host, so point
                # careers_url at the linked board, not the branded page (site
                # names are case-sensitive — match on the raw body).
                board = _workday_board(raw)
                if board:
                    return mk("workday", "", careers=board[1], name=board[0].title())
                return mk("workday", "", careers=url, name=nm)
            if "recruitee" in body:   # custom domain (careers.hostaway.com) proxies the API
                labels = host.replace("www.", "").split(".")
                sld = (labels[-2] if len(labels) >= 2 else labels[0]).title()
                return mk("recruitee", "", careers=url, name=sld)
        except Exception:
            pass
    return mk("custom", "", careers=url, name=nm)


def discover(query: str, http) -> dict | None:
    q = query.strip()
    if q.lower().startswith("http"):
        return _from_url(q, http)
    return _from_name(q, http)
