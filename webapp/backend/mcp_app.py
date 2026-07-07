"""JobRadar MCP server (spec: specs/mcp-server.md).

Exposes the tracked-role repository to Claude (Desktop + mobile) as MCP tools, thin
over the shared read layer `services.queries` (same store as the web app + CLI).
Phase 2 adds two management tools (follow_company / unfollow_company) over the same
registry the web app writes; no auth here (added in Phase B); localhost/tailnet for
now (public HTTPS via Tailscale Funnel is Phase C).

Deployed path: `app.py` mounts this server's routes under `/mcp` — same image, same
uvicorn process as the web app (spec: one server, one deploy).
Run standalone (local dev):  JSA_ROOT=… python -m webapp.backend.mcp_app
(Streamable HTTP on :8899/mcp)
"""
from __future__ import annotations

import ipaddress
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse

_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR.parents[1]))   # repo root -> services.*

from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

from models.job_posting import _slugify  # noqa: E402
from scrapers.http_client import HttpClient  # noqa: E402
from scrapers.rate_limiter import RateLimiter  # noqa: E402
from services import discovery, loader, queries, registry, run_service, store  # noqa: E402

# Model-facing contract (spec: specs/mcp-server.md "Tool descriptions"): these
# instructions and the tool docstrings are what the client model reads to pick a
# tool and interpret results — edit them as prompt text, not comments.
_INSTRUCTIONS = """\
JobRadar tracks senior Product-Management roles at companies the user follows,
scraped daily from each company's ATS. Single user.

Which tool:
- "What's new?" -> new_jobs (days=1 today, days=7 the past week); stats for headline numbers.
- Browse or filter roles (seniority, company, keyword, sort) -> list_jobs, the general query tool.
- Quick lookup by company/title text with no other filters -> search_jobs (a subset of list_jobs).
- Judge fit or summarise one role -> get_job. Summaries never include the ad text;
  any fit judgment requires this call.
- Which companies are tracked -> list_companies; one company's open roles -> company_roles.
- Track a new company -> follow_company. YOU find the company's ATS job-board URL first
  (web-search "<company> careers", follow through to the ATS board) and pass that clean
  URL — the server does not search the web. Stop tracking -> unfollow_company.

Reading results:
- first_seen = date the scraper discovered the posting (drives new_jobs); posted_date =
  the ATS's own date (may be null or much older); last_seen = last run it was still up.
- status lifecycle: open -> suspected_filled (missing 2 consecutive runs) -> closed;
  "applied" is set by the user.
- seniority_rank: CPO 9, VP 8, Director 7, Head 6, Principal/Staff 5,
  Group/Product-Lead 4, Senior 3, PM/Product Owner 2. AI/Innovation leadership
  titles (e.g. "AI & Innovation Lead", "Head of AI") rank in the same ladder.
  Only rank >= 3 (plus opted-in Product Owners) is tracked.
- salary min/max are extracted, never currency-converted; salary.original_text is
  authoritative. compensation_type notes bonus/equity mentions.
- job_ad_url is the external ATS posting — use it when citing or linking a role.
- Empty results return []; get_job returns {"error": ...} for an unknown id.
"""

Status = Literal["open", "applied", "suspected_filled", "closed", "all"]

# The SDK's DNS-rebinding guard 421s any Host it doesn't know; its built-in default
# is localhost-only, which breaks the deployed hostname. Local + test hosts by
# default; the Pi sets JSA_MCP_ALLOWED_HOSTS to its tailnet/ts.net names (Phase C).
_ALLOWED_HOSTS = [h.strip() for h in os.environ.get("JSA_MCP_ALLOWED_HOSTS", "").split(",")
                  if h.strip()] or ["127.0.0.1:*", "localhost:*", "testserver"]

mcp = FastMCP("JobRadar", instructions=_INSTRUCTIONS, host="127.0.0.1", port=8899,
              transport_security=TransportSecuritySettings(allowed_hosts=_ALLOWED_HOSTS))


def _index():
    return queries.load_index(store.index_path())


@mcp.tool()
def stats() -> dict:
    """Headline numbers: open roles, new in last 7 days, distinct companies with at
    least one tracked role (NOT the full registry — use list_companies for that),
    total roles ever tracked, last run timestamp."""
    return {**queries.stats(_index()), "last_run": store.last_run()}


@mcp.tool()
def list_jobs(status: Status = "open", company: Optional[str] = None,
              min_rank: Optional[int] = None, q: Optional[str] = None,
              sort: Literal["seniority", "recent"] = "seniority",
              limit: Optional[int] = None) -> list[dict]:
    """List tracked senior-PM roles — the general query tool; all filters combine.

    company: name or slug. min_rank: keep seniority_rank >= N (CPO 9, VP 8,
    Director 7, Head 6, Principal/Staff 5, Group/Product-Lead 4, Senior 3).
    q: case-insensitive substring over company + title. sort "seniority" = most
    senior first; "recent" = newest first_seen first.
    """
    roles = queries.list_roles(_index(), status=status, company=company,
                               min_rank=min_rank, q=q, sort=sort)
    if limit:
        roles = roles[:limit]
    return [queries.role_summary(r) for r in roles]


@mcp.tool()
def search_jobs(q: str, status: Status = "open") -> list[dict]:
    """Quick lookup of roles by company or title substring (case-insensitive).
    A subset of list_jobs — prefer list_jobs when you also want rank/company/sort/limit."""
    return [queries.role_summary(r) for r in queries.list_roles(_index(), status=status, q=q)]


@mcp.tool()
def new_jobs(days: int = 1) -> list[dict]:
    """Open roles the scraper first discovered within the last N days (first_seen,
    not the ATS posted_date). Default 1 = 'new today'; use 7 for 'the past week'."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    roles = [r for r in queries.list_roles(_index(), status="open")
             if (r.get("first_seen") or "") >= cutoff]
    return [queries.role_summary(r) for r in roles]


@mcp.tool()
def get_job(id: str) -> dict:
    """Full detail for one role by id: all fields + the **Markdown ad text** + the
    user's notes. Required for any fit-against-CV judgment — summaries from the
    list tools never contain the ad text. Unknown id returns {"error": ...}."""
    return queries.get_role(id) or {"error": f"no role with id {id!r}"}


@mcp.tool()
def list_companies() -> list[dict]:
    """The full registry of tracked companies (active or not) with ATS type and
    open-role counts. Source of the slugs company_roles expects."""
    counts: dict = {}
    for r in queries.group_roles(_index()):
        if r.get("status") == "open":
            counts[r.get("company_slug")] = counts.get(r.get("company_slug"), 0) + 1
    return [{"name": c.get("name"), "slug": c.get("slug"), "ats_type": c.get("ats_type"),
             "active": bool(c.get("active")), "open_roles": counts.get(c.get("slug"), 0)}
            for c in registry.list_companies()]


@mcp.tool()
def company_roles(slug: str) -> list[dict]:
    """Open roles for one company, by registry slug (e.g. 'monzo' — see
    list_companies). Unknown slug returns []."""
    roles = queries.list_roles(_index(), status="open", company=slug)
    return [queries.role_summary(r) for r in roles]


# --- management (Phase 2) -------------------------------------------------------

def _non_public_url(url: str) -> Optional[str]:
    """SSRF guard for the model-supplied ats_url: discovery body-probes unrecognised
    hosts with a real GET, so refuse anything that isn't plainly a public web host
    — before any fetch. Syntactic only (no DNS lookup: tests are network-free and
    a single-user tool doesn't warrant rebinding defences). Returns the reason, or
    None if the URL is acceptable."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return "not an http(s) URL"
    host = (p.hostname or "").lower()
    if not host:
        return "no host in URL"
    try:
        if not ipaddress.ip_address(host).is_global:
            return f"{host} is not a public address"
    except ValueError:                               # not an IP literal -> hostname
        if host == "localhost" or "." not in host:   # bare names = intranet
            return f"{host!r} is not a public hostname"
        if host.rsplit(".", 1)[-1] in ("localhost", "local", "internal", "lan", "home", "arpa"):
            return f"{host!r} is not a public hostname"
    return None


def _scan_company(slug: str, settings: dict) -> bool:
    """One-off seek for just this company so roles appear immediately instead of
    after the daily run. Slack suppressed; failure is non-fatal (as web follow)."""
    try:
        rows = [c for c in registry.list_companies() if c["slug"] == slug]
        if not rows:
            return False
        quiet = {**settings, "notify": {**(settings.get("notify") or {}), "enabled": False}}
        run_service.seek_run(quiet, loader.load_profile(), rows)
        return True
    except Exception:                                # noqa: BLE001 — never fail the follow
        return False


@mcp.tool()
def follow_company(ats_url: str, name: Optional[str] = None, scan: bool = True) -> dict:
    """Start tracking a company. Side effects: writes the company registry; with
    scan=true (default) also scrapes that company's board once so its roles are
    queryable immediately (takes a few seconds; no Slack notification).

    ats_url must be the company's ATS job-board URL — find it yourself first
    (web-search "<company> careers"/"jobs"); do NOT pass the company's homepage.
    Recognised directly: (job-)boards.greenhouse.io/<slug>, jobs.ashbyhq.com/<slug>,
    jobs.lever.co/<slug>, jobs.smartrecruiters.com/<Company>,
    <tenant>.myworkdayjobs.com/<site>, <tenant>.fa.<region>.oraclecloud.com/...,
    <slug>.recruitee.com, fsr.cvmailuk.com/<firm>/... (cvMail — UK law firms; any
    deep job link works). Other careers pages are probed for an embedded ATS
    (Talemetry/Workday/Recruitee) and rejected if none is found.

    name: display name override (recommended — URL-derived names are rough).
    Returns the registry row + scanned flag + open_roles kept by the scan (0 with
    scanned=true means the board is live but has no matching senior-PM roles right
    now — the follow still succeeded), or {"error": ...} (unrecognised ATS, already
    actively tracking). Following a previously-unfollowed company re-activates it."""
    url = (ats_url or "").strip()
    blocked = _non_public_url(url)
    if blocked:
        return {"error": f"ats_url must be a public http(s) ATS job-board URL — {blocked}"}
    settings = loader.load_settings()
    http = HttpClient(settings, RateLimiter(settings.get("rate_limit_per_sec", 1)))
    info = discovery.discover(url, http)
    if not info or info.get("ats_type") == "custom":
        return {"error": f"{url} is not a recognised ATS job board — pass the company's "
                         "Greenhouse/Ashby/Lever/SmartRecruiters/Workday/Oracle/Recruitee/cvMail "
                         "board URL (or a careers page that embeds one)"}
    if name and name.strip():
        info["name"], info["slug"] = name.strip(), _slugify(name)
    info["active"] = True
    if not registry.add_company(info):
        existing = registry.find_existing(info) or {}
        if existing and not existing.get("active"):      # unfollowed earlier -> re-activate
            registry.set_active(existing["slug"], True)
            return {"company": existing | {"active": True}, "scanned": False,
                    "note": "was unfollowed — re-activated; roles refresh on the next daily run"}
        return {"error": f"already tracking {existing.get('name') or info['slug']}",
                "slug": existing.get("slug") or info["slug"]}
    scanned = _scan_company(info["slug"], settings) if scan else False
    out = {"company": {k: info.get(k) for k in ("name", "slug", "ats_type", "ats_slug",
                                                "careers_url")},
           "scanned": scanned,
           "note": "roles appear after the next daily run"}
    if scanned:
        out["open_roles"] = len(queries.list_roles(_index(), status="open",
                                                   company=info["slug"]))
        out["note"] = ("roles queryable now" if out["open_roles"]
                       else "scan ok — no currently-open senior-PM roles on this board")
    return out


@mcp.tool()
def unfollow_company(slug: str) -> dict:
    """Stop tracking a company by registry slug (see list_companies). Side effect:
    sets active=false in the registry — existing roles/data are kept, the daily
    scrape just skips it. Unknown slug returns {"error": ...}."""
    if not registry.set_active(slug, False):
        return {"error": f"no company with slug {slug!r} — see list_companies"}
    return {"slug": slug, "active": False}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
