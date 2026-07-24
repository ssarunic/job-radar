"""MCP tool tests — network-free, against a temp canonical store.

Calls the tool functions directly (FastMCP's @tool returns them unchanged); one
test goes through the MCP layer to pin the registered surface (names + schemas).
"""
import shutil
from datetime import date, timedelta
from pathlib import Path

import anyio
import mcp_app
import pytest

from outputs import index_builder, md_writer

TODAY = date.today().isoformat()
OLD = (date.today() - timedelta(days=30)).isoformat()
OLDER = (date.today() - timedelta(days=45)).isoformat()

CAPSA = {
    "id": "aaa11111", "company": "Capsa", "company_slug": "capsa",
    "title_raw": "Head of Product", "title_normalised": "Head of Product",
    "seniority_rank": 6, "seniority_level": "Head", "locations": ["London"],
    "salary": {"min": 140000, "max": 170000, "currency": "GBP",
               "original_text": "£140K – £170K"}, "compensation_type": "Base Only",
    "employment_type": "Full time", "workplace_model": "On site",
    "posted_date": "2026-06-10", "job_ad_url": "https://jobs.ashbyhq.com/capsa/x",
    "source_detail": "Ashby", "first_seen": TODAY, "last_seen": TODAY,
    "status": "open",
}
MONZO = {
    "id": "bbb22222", "company": "Monzo", "company_slug": "monzo",
    "title_raw": "Senior Product Manager, Legacy", "title_normalised": "Senior Product Manager",
    "seniority_rank": 3, "seniority_level": "Senior", "locations": ["London"],
    "salary": {"min": None, "max": None, "currency": None, "original_text": None},
    "compensation_type": "Not Stated", "employment_type": "Full time",
    "workplace_model": "On site", "posted_date": "2026-01-01",
    "job_ad_url": "https://job-boards.greenhouse.io/monzo/jobs/1",
    "source_detail": "Greenhouse", "first_seen": OLD, "last_seen": OLD,
    "status": "closed",
}
MONZO_OPEN = {
    **MONZO, "id": "ccc33333", "title_raw": "Product Director, Payments",
    "title_normalised": "Director of Product", "seniority_rank": 7,
    "seniority_level": "Director", "first_seen": OLDER, "last_seen": TODAY,
    "status": "open",
}


@pytest.fixture
def mcp_store(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    md_writer.write_posting(jobs, "capsa", "head-of-product", "aaa11111", CAPSA,
                            "## About Capsa\n\n- **bold** bullet", "", "my private note")
    md_writer.write_posting(jobs, "monzo", "spm-legacy", "bbb22222", MONZO, "Old role.", "", "")
    md_writer.write_posting(jobs, "monzo", "pd-payments", "ccc33333", MONZO_OPEN, "Pay.", "", "")
    index_builder.rebuild(jobs, tmp_path / "data" / "jobs.jsonl")
    cfg = tmp_path / "config"
    cfg.mkdir()
    repo_cfg = Path(__file__).resolve().parents[3] / "config"
    for f in ("settings.yaml", "search_profile.yaml"):
        shutil.copy(repo_cfg / f, cfg / f)
    (cfg / "companies.csv").write_text(
        "name,slug,careers_url,ats_type,ats_slug,priority,active\n"
        "Capsa,capsa,,ashby,capsa,,true\n"
        "Monzo,monzo,,greenhouse,monzo,,true\n"
        "Ghost,ghost,,lever,ghost,,false\n")
    monkeypatch.setenv("JSA_ROOT", str(tmp_path))
    # keep every test network-free: no scans, no ATS probing
    monkeypatch.setattr("services.run_service.seek_run", lambda *a, **k: None)
    return tmp_path


# --- read tools -----------------------------------------------------------------

def test_stats(mcp_store):
    s = mcp_app.stats()
    assert s["open"] == 2 and s["total"] == 3
    assert s["companies"] == 2               # distinct companies WITH roles, not registry (3)
    assert "last_run" in s


def test_list_jobs_default_open_sorted_by_seniority(mcp_store):
    jobs = mcp_app.list_jobs()
    assert [j["id"] for j in jobs] == ["ccc33333", "aaa11111"]   # Director before Head


def test_list_jobs_filters_combine(mcp_store):
    assert len(mcp_app.list_jobs(status="all")) == 3
    assert [j["id"] for j in mcp_app.list_jobs(min_rank=7)] == ["ccc33333"]
    assert [j["id"] for j in mcp_app.list_jobs(q="head")] == ["aaa11111"]
    assert [j["id"] for j in mcp_app.list_jobs(company="monzo", status="all", limit=1,
                                               sort="recent")] == ["bbb22222"]


def test_list_jobs_summary_shape(mcp_store):
    job = mcp_app.list_jobs(q="head")[0]
    assert job["salary"]["min"] == 140000 and job["locations"] == ["London"]
    assert "ad_markdown" not in job          # summaries never carry the ad text


def test_search_jobs(mcp_store):
    assert [j["id"] for j in mcp_app.search_jobs(q="CAPSA")] == ["aaa11111"]
    assert mcp_app.search_jobs(q="nope") == []


def test_new_jobs_filters_on_first_seen(mcp_store):
    assert [j["id"] for j in mcp_app.new_jobs(days=1)] == ["aaa11111"]
    ids = {j["id"] for j in mcp_app.new_jobs(days=60)}
    assert ids == {"aaa11111", "ccc33333"}   # open only — closed Monzo role excluded


def test_get_job_detail_and_error(mcp_store):
    d = mcp_app.get_job("aaa11111")
    assert "**bold**" in d["ad_markdown"] and d["notes"] == "my private note"
    assert mcp_app.get_job("nope") == {"error": "no role with id 'nope'"}


def test_list_companies_is_full_registry(mcp_store):
    by_slug = {c["slug"]: c for c in mcp_app.list_companies()}
    assert set(by_slug) == {"capsa", "monzo", "ghost"}
    assert by_slug["capsa"]["open_roles"] == 1 and by_slug["monzo"]["open_roles"] == 1
    assert by_slug["ghost"]["active"] is False and by_slug["ghost"]["open_roles"] == 0


def test_company_roles(mcp_store):
    assert [r["id"] for r in mcp_app.company_roles("monzo")] == ["ccc33333"]  # open only
    assert mcp_app.company_roles("nope") == []


# --- management tools (Phase 2) --------------------------------------------------

def test_follow_company_clean_ats_url(mcp_store):
    r = mcp_app.follow_company("https://jobs.ashbyhq.com/attio", name="Attio")
    assert r["company"] == {"name": "Attio", "slug": "attio", "ats_type": "ashby",
                            "ats_slug": "attio", "careers_url": "https://jobs.ashbyhq.com/attio"}
    assert r["scanned"] is True              # seek stubbed in fixture, still reported
    assert r["open_roles"] == 0              # scan kept nothing -> honest note, not "queryable"
    assert "no currently-open" in r["note"]
    by_slug = {c["slug"]: c for c in mcp_app.list_companies()}
    assert by_slug["attio"]["active"] is True


def test_follow_company_scan_false(mcp_store):
    r = mcp_app.follow_company("https://jobs.lever.co/plaid", scan=False)
    assert r["scanned"] is False and "daily run" in r["note"]


def test_follow_company_scan_failure_non_fatal(mcp_store, monkeypatch):
    monkeypatch.setattr("services.run_service.seek_run",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    r = mcp_app.follow_company("https://job-boards.greenhouse.io/figma")
    assert r["company"]["slug"] == "figma" and r["scanned"] is False


def test_follow_company_rejects_non_url_and_unknown_ats(mcp_store, monkeypatch):
    assert "error" in mcp_app.follow_company("Attio")            # name, not a URL

    class _NoNet:                            # unrecognised host body-probe must not hit network
        def get(self, url):
            raise RuntimeError("offline")

    monkeypatch.setattr(mcp_app, "HttpClient", lambda *a, **k: _NoNet())
    r = mcp_app.follow_company("https://example.com/careers")
    assert "not a recognised ATS" in r["error"]


def test_follow_company_dedupe(mcp_store):
    r = mcp_app.follow_company("https://jobs.ashbyhq.com/capsa")
    assert "already tracking" in r["error"] and r["slug"] == "capsa"


def test_follow_company_reactivates_unfollowed(mcp_store):
    r = mcp_app.follow_company("https://jobs.lever.co/ghost")
    assert "error" not in r and r["company"]["active"] is True
    assert "re-activated" in r["note"]
    by_slug = {c["slug"]: c for c in mcp_app.list_companies()}
    assert by_slug["ghost"]["active"] is True


def test_unfollow_company(mcp_store):
    assert mcp_app.unfollow_company("monzo") == {"slug": "monzo", "active": False}
    by_slug = {c["slug"]: c for c in mcp_app.list_companies()}
    assert by_slug["monzo"]["active"] is False
    assert "error" in mcp_app.unfollow_company("nope")


def test_follow_company_rejects_non_public_urls(mcp_store):
    """SSRF guard: refused before any fetch — no HttpClient is ever constructed."""
    for bad in ("ftp://boards.greenhouse.io/x",       # scheme
                "http://localhost:8765/api/seek",     # loopback name
                "http://127.0.0.1/latest/meta-data",  # loopback IP
                "http://192.168.1.10/jobs",           # private range
                "http://[::1]:8080/",                 # v6 loopback
                "http://169.254.169.254/",            # link-local (cloud metadata)
                "http://intranet/careers",            # bare intranet name
                "http://pi.local/admin"):             # mDNS
        r = mcp_app.follow_company(bad)
        assert "public" in r.get("error", ""), f"not rejected: {bad}"


# --- registered MCP surface -------------------------------------------------------

def test_mcp_surface(mcp_store):
    tools = {t.name: t for t in anyio.run(mcp_app.mcp.list_tools)}
    assert set(tools) == {"stats", "list_jobs", "search_jobs", "new_jobs", "get_job",
                          "set_job_status", "list_companies", "company_roles",
                          "follow_company", "unfollow_company"}
    status = tools["list_jobs"].inputSchema["properties"]["status"]
    assert status["enum"] == ["open", "applied", "suspected_filled", "closed", "all"]
    assert mcp_app.mcp.instructions            # model-facing contract is set


def test_mcp_mounted_in_web_app(mcp_store):
    """The deployed surface: POST /mcp on the FastAPI app (not the standalone runner)
    must reach the MCP server — this is what the connector URL hits."""
    import app as webapp
    from fastapi.testclient import TestClient
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "t", "version": "0"}}}
    with TestClient(webapp.app) as client:     # context manager -> lifespan runs
        r = client.post("/mcp", headers={"Content-Type": "application/json",
                                         "Accept": "application/json, text/event-stream"},
                        json=init)
        assert r.status_code == 200 and "JobRadar" in r.text
        assert client.get("/api/stats").status_code == 200   # web API unaffected


# --- set_job_status ---------------------------------------------------------------

def test_set_job_status_applied_with_note(mcp_store):
    out = mcp_app.set_job_status("aaa11111", "applied", note="Applied 2026-07-24.")
    assert out["status"] == "applied"
    assert "Applied 2026-07-24." in out["notes"]
    # visible through the read tools (index rebuilt)
    assert [j["id"] for j in mcp_app.list_jobs(status="applied")] == ["aaa11111"]


def test_set_job_status_note_appends_not_replaces(mcp_store):
    mcp_app.set_job_status("aaa11111", "applied", note="first")
    out = mcp_app.set_job_status("aaa11111", "applied", note="second")
    assert "first" in out["notes"] and "second" in out["notes"]


def test_set_job_status_revert_and_unknown(mcp_store):
    mcp_app.set_job_status("aaa11111", "applied")
    assert mcp_app.set_job_status("aaa11111", "open")["status"] == "open"
    assert "error" in mcp_app.set_job_status("zzz99999", "applied")
