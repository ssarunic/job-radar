"""Web API tests — network-free, against a temp canonical store."""
import json
from pathlib import Path

import app as webapp
import pytest
from fastapi.testclient import TestClient

from outputs import index_builder, md_writer

CAPSA = {
    "id": "aaa11111", "company": "Capsa", "company_slug": "capsa",
    "title_raw": "Head of Product", "title_normalised": "Head of Product",
    "seniority_rank": 6, "seniority_level": "Head", "locations": ["London"],
    "salary": {"min": 140000, "max": 170000, "currency": "GBP",
               "original_text": "£140K – £170K"}, "compensation_type": "Base Only",
    "employment_type": "Full time", "workplace_model": "On site",
    "posted_date": "2026-06-10", "job_ad_url": "https://jobs.ashbyhq.com/capsa/x",
    "source_detail": "Ashby", "first_seen": "2026-06-27", "last_seen": "2026-06-27",
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
    "source_detail": "Greenhouse", "first_seen": "2026-01-01", "last_seen": "2026-02-01",
    "status": "closed",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    md_writer.write_posting(jobs, "capsa", "head-of-product", "aaa11111", CAPSA,
                            "## About Capsa\n\n- **bold** bullet\n- second",
                            "- 6 years in product", "my private note")
    md_writer.write_posting(jobs, "monzo", "spm-legacy", "bbb22222", MONZO,
                            "Old role.", "", "")
    index_builder.rebuild(jobs, tmp_path / "data" / "jobs.jsonl")
    # Seed config so the company-management endpoints have a registry + settings.
    import shutil
    cfg = tmp_path / "config"
    cfg.mkdir()
    repo_cfg = Path(__file__).resolve().parents[3] / "config"
    for f in ("settings.yaml", "search_profile.yaml"):
        shutil.copy(repo_cfg / f, cfg / f)
    (cfg / "companies.csv").write_text(
        "name,slug,careers_url,ats_type,ats_slug,priority,active\n"
        "Capsa,capsa,,ashby,capsa,,true\n"
        "Monzo,monzo,,greenhouse,monzo,,true\n")
    monkeypatch.setenv("JSA_ROOT", str(tmp_path))
    # follow scans the new company by default — stub the seek so POSTs stay network-free.
    monkeypatch.setattr("services.run_service.seek_run", lambda *a, **k: None)
    return TestClient(webapp.app)


def test_stats(client):
    s = client.get("/api/stats").json()
    assert s["open"] == 1 and s["total"] == 2 and s["companies"] == 2


def test_jobs_default_open_only(client):
    j = client.get("/api/jobs").json()
    assert j["count"] == 1 and j["jobs"][0]["id"] == "aaa11111"


def test_jobs_status_all(client):
    assert client.get("/api/jobs?status=all").json()["count"] == 2


def test_jobs_status_closed(client):
    j = client.get("/api/jobs?status=closed").json()
    assert [x["id"] for x in j["jobs"]] == ["bbb22222"]


def test_jobs_min_rank(client):
    assert client.get("/api/jobs?status=all&min_rank=5").json()["count"] == 1


def test_jobs_company_and_query(client):
    assert client.get("/api/jobs?status=all&company=monzo").json()["count"] == 1
    assert client.get("/api/jobs?status=all&q=head").json()["jobs"][0]["company"] == "Capsa"


def test_jobs_summary_has_salary(client):
    job = client.get("/api/jobs").json()["jobs"][0]
    assert job["salary"]["min"] == 140000 and job["salary"]["currency"] == "GBP"
    assert job["locations"] == ["London"]


def test_job_detail(client):
    d = client.get("/api/jobs/aaa11111").json()
    assert d["title_raw"] == "Head of Product"
    assert "**bold**" in d["ad_markdown"]            # markdown preserved
    assert "## My notes" not in d["ad_markdown"]     # notes split out of the ad
    assert d["notes"] == "my private note"           # user notes returned separately
    assert d["salary"]["max"] == 170000


def test_job_detail_404(client):
    assert client.get("/api/jobs/nope").status_code == 404


def test_job_markdown_serves_canonical_file(client, tmp_path):
    r = client.get("/api/jobs/aaa11111/markdown")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    on_disk = (tmp_path / "jobs" / "capsa" / "head-of-product--aaa11111.md"
               ).read_text(encoding="utf-8")
    assert r.text == on_disk                          # byte-for-byte, no rendition
    assert r.text.startswith("---")                   # frontmatter included
    assert "my private note" in r.text                # notes included by design
    assert "content-disposition" not in r.headers     # inline unless ?download=1


def test_job_markdown_download_disposition(client):
    r = client.get("/api/jobs/aaa11111/markdown?download=1")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == \
        'attachment; filename="capsa--head-of-product--aaa11111.md"'


def test_job_markdown_404(client):
    assert client.get("/api/jobs/nope/markdown").status_code == 404


def test_spa_blocks_path_traversal(client, tmp_path, monkeypatch):
    # The SPA fallback must not serve files outside the built dist, even via encoded
    # dot segments (%2e%2e) that decode to "..". Regression for a P1 traversal.
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "ok.js").write_text("console.log(1)")
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    monkeypatch.setattr(webapp, "_DIST", dist)

    assert client.get("/ok.js").text == "console.log(1)"          # real asset still served
    for p in ["/%2e%2e/secret.txt", "/..%2fsecret.txt", "/%2e%2e%2fsecret.txt"]:
        r = client.get(p)
        assert "TOPSECRET" not in r.text                          # never escapes dist
        assert "<html>app</html>" in r.text                       # falls back to index.html


# --- company management -------------------------------------------------------

def test_list_companies(client):
    r = client.get("/api/companies").json()
    assert r["count"] == 2
    by_slug = {c["slug"]: c for c in r["companies"]}
    assert by_slug["capsa"]["open_roles"] == 1        # Capsa's role is open
    assert by_slug["monzo"]["open_roles"] == 0        # Monzo's role is closed
    assert by_slug["capsa"]["ats_type"] == "ashby" and by_slug["capsa"]["active"] is True


def test_open_count_dedupes_multilocation(client, tmp_path):
    # A role open in two locations is stored as two index rows (one per location)
    # but must count as ONE open role — the pill has to match the listed roles.
    role = {**MONZO, "id": "ccc33333", "title_raw": "Group PM, Payments",
            "title_normalised": "Group Product Manager", "seniority_rank": 4,
            "locations": ["London", "Remote"], "status": "open"}
    md_writer.write_posting(tmp_path / "jobs", "monzo", "gpm-payments", "ccc33333",
                            role, "desc", "", "")
    index_builder.rebuild(tmp_path / "jobs", tmp_path / "data" / "jobs.jsonl")
    by_slug = {c["slug"]: c for c in client.get("/api/companies").json()["companies"]}
    assert by_slug["monzo"]["open_roles"] == 1                 # 2 location-rows -> 1 role
    d = client.get("/api/companies/monzo").json()
    assert len(d["roles"]) == d["company"]["open_roles"]       # pill matches the list


def test_company_detail(client):
    d = client.get("/api/companies/capsa").json()
    assert d["company"]["slug"] == "capsa" and d["company"]["open_roles"] == 1
    assert [r["id"] for r in d["roles"]] == ["aaa11111"]   # Capsa's one open role


def test_company_detail_404(client):
    assert client.get("/api/companies/nope").status_code == 404


def test_follow_manual_no_network(client):
    r = client.post("/api/companies", json={
        "name": "Wise", "ats_type": "smartrecruiters",
        "careers_url": "https://www.smartrecruiters.com/Wise"})
    assert r.status_code == 201
    assert r.json()["company"]["slug"] == "wise"
    assert {c["slug"] for c in client.get("/api/companies").json()["companies"]} >= {"wise"}


def test_follow_by_name_already_tracked_409_without_discovery(client, monkeypatch):
    """Typing a tracked company's name says so, even when its ATS isn't
    name-probeable (was: "couldn't auto-detect an ATS for 'Natwest'")."""
    def boom(*a, **k):
        raise AssertionError("discovery should not run")
    monkeypatch.setattr("services.discovery.discover", boom)
    r = client.post("/api/companies", json={"query": "capsa"})
    assert r.status_code == 409
    assert "already tracking capsa" in r.json()["detail"].lower()


def test_follow_dedupe_409(client):
    r = client.post("/api/companies", json={
        "name": "Capsa", "ats_type": "ashby", "careers_url": "https://jobs.ashbyhq.com/capsa"})
    assert r.status_code == 409
    assert "already tracking" in r.json()["detail"].lower()


def test_follow_by_query_uses_discovery(client, monkeypatch):
    monkeypatch.setattr("services.discovery.discover",
                        lambda query, http: {"name": "Granola", "slug": "granola",
                                             "careers_url": "", "ats_type": "ashby",
                                             "ats_slug": "granola"})
    r = client.post("/api/companies", json={"query": "Granola"})
    assert r.status_code == 201 and r.json()["company"]["ats_type"] == "ashby"


def test_follow_empty_is_422(client):
    assert client.post("/api/companies", json={}).status_code == 422


def test_follow_query_undetected_is_422(client, monkeypatch):
    monkeypatch.setattr("services.discovery.discover", lambda query, http: None)
    r = client.post("/api/companies", json={"query": "Nope Inc"})
    assert r.status_code == 422
    # shown verbatim in the Follow modal: plain language, no field names
    assert "careers page" in r.json()["detail"] and "ats_type" not in r.json()["detail"]


def test_follow_scans_new_company_by_default(client, monkeypatch):
    seen = {}

    def fake_seek(settings, profile, companies, **kw):
        seen["slugs"] = [c["slug"] for c in companies]
        seen["notify_enabled"] = (settings.get("notify") or {}).get("enabled")

    monkeypatch.setattr("services.run_service.seek_run", fake_seek)
    r = client.post("/api/companies", json={
        "name": "Wise", "ats_type": "smartrecruiters", "careers_url": "https://x"})
    assert r.status_code == 201 and r.json()["scanned"] is True
    assert seen["slugs"] == ["wise"]                  # scoped to just the new company
    assert seen["notify_enabled"] is False            # Slack suppressed for the interactive scan


def test_follow_scan_false_skips_seek(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("seek_run must not be called when scan=false")

    monkeypatch.setattr("services.run_service.seek_run", boom)
    r = client.post("/api/companies", json={
        "name": "Wise", "ats_type": "smartrecruiters", "careers_url": "https://x", "scan": False})
    assert r.status_code == 201 and r.json()["scanned"] is False


def test_follow_scan_failure_is_non_fatal(client, monkeypatch):
    monkeypatch.setattr("services.run_service.seek_run",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network down")))
    r = client.post("/api/companies", json={
        "name": "Wise", "ats_type": "smartrecruiters", "careers_url": "https://x"})
    assert r.status_code == 201                        # follow still succeeds
    assert r.json()["scanned"] is False                # but scan reported as not done


def test_unfollow_toggles_active(client):
    assert client.patch("/api/companies/monzo", json={"active": False}).status_code == 200
    by_slug = {c["slug"]: c for c in client.get("/api/companies").json()["companies"]}
    assert by_slug["monzo"]["active"] is False


def test_set_active_unknown_slug_404(client):
    assert client.patch("/api/companies/nope", json={"active": False}).status_code == 404


# --- manual refresh (POST /api/seek) ------------------------------------------

class _SyncThread:                       # run the spawned thread inline → deterministic
    def __init__(self, target, daemon=None):
        self._target = target

    def start(self):
        self._target()


def test_manual_seek_runs_and_reports(client, monkeypatch):
    class FakeResult:
        diff = [{"change": "added"}, {"change": "added"}, {"change": "updated"}]
        summary_text = "seek done"

    seen = {}

    def fake_seek(settings, profile, companies, **kw):
        seen["notify_enabled"] = (settings.get("notify") or {}).get("enabled")
        prog = kw.get("progress")                         # exercise per-company progress
        if prog:
            prog("→ Capsa (ashby) …")
            prog("   ✓ 1 kept via ashby")                 # non-"→" line: ignored
            prog("→ Monzo (greenhouse) …")
        return FakeResult()

    monkeypatch.setattr("services.run_service.seek_run", fake_seek)
    monkeypatch.setattr(webapp.threading, "Thread", _SyncThread)
    assert client.post("/api/seek").json()["started"] is True
    s = client.get("/api/seek").json()
    assert s["running"] is False and s["error"] is None
    assert s["added"] == 2                                # added/reopened counted
    assert seen["notify_enabled"] is False               # Slack suppressed for manual refresh
    assert s["total"] == 2 and s["done"] == 2            # both companies counted
    assert s["current"] is None                          # cleared on success


def test_seek_conflict_when_running(client, monkeypatch):
    monkeypatch.setitem(webapp._seek_state, "running", True)
    assert client.post("/api/seek").status_code == 409


# --- run history (Activity) ---------------------------------------------------

def _write_run(tmp_path, ts, lines, summary="RUN SUMMARY"):
    rd = tmp_path / "data" / "runs" / ts
    rd.mkdir(parents=True)
    (rd / "diff.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    (rd / "summary.txt").write_text(summary)


def test_runs_list_and_detail(client, tmp_path):
    _write_run(tmp_path, "2026-06-30T120000Z", [
        {"change": "added", "id": "x1", "company": "Monzo", "title": "PM", "location": "London"},
        {"change": "closed", "id": "x2", "company": "Wise", "title": "PD", "location": "London"},
    ])
    lst = client.get("/api/runs").json()
    assert lst["count"] == 1 and lst["runs"][0]["ts"] == "2026-06-30T120000Z"
    assert lst["runs"][0]["counts"] == {"added": 1, "closed": 1}
    d = client.get("/api/runs/2026-06-30T120000Z").json()
    assert len(d["changes"]) == 2 and "RUN SUMMARY" in d["summary"]


def test_run_detail_404_and_bad_ts(client):
    assert client.get("/api/runs/2026-01-01T000000Z").status_code == 404   # well-formed, absent
    assert client.get("/api/runs/not-a-ts").status_code == 404             # rejected by ts regex


def test_runs_content_search(client, tmp_path):
    _write_run(tmp_path, "2026-06-30T120000Z", [
        {"change": "added", "company": "Monzo", "title": "Senior Product Manager", "location": "L"},
    ])
    _write_run(tmp_path, "2026-06-29T120000Z", [
        {"change": "added", "company": "Wise", "title": "Principal PM", "location": "London"},
    ])
    # q filters to the matching run (case-insensitive, company or title) + returns snippets
    r = client.get("/api/runs?q=monzo").json()
    assert r["count"] == 1 and r["runs"][0]["ts"] == "2026-06-30T120000Z"
    assert r["runs"][0]["matched"] == ["Monzo: Senior Product Manager"]
    # title match works too
    assert client.get("/api/runs?q=principal").json()["runs"][0]["ts"] == "2026-06-29T120000Z"
    # no match → empty; no q → all runs, no `matched` key
    assert client.get("/api/runs?q=nope").json()["count"] == 0
    assert "matched" not in client.get("/api/runs").json()["runs"][0]


# --- profile (Settings page) ------------------------------------------------------

def test_get_profile(client):
    p = client.get("/api/profile").json()
    assert p["companies_followed"] == 2
    assert p["profile"]["seniority_min"] == 3


def test_put_profile_merges_and_persists(client):
    r = client.put("/api/profile", json={
        "search_label": "design leadership", "seniority_min": 4,
        "home_city": "Berlin", "home_terms": ["berlin", "germany"],
        "allow_remote": False})
    assert r.status_code == 200
    p = client.get("/api/profile").json()["profile"]
    assert p["search_label"] == "design leadership"
    assert p["seniority_min"] == 4
    assert p["allow_remote"] is False
    assert p["location"]["home_city"] == "Berlin"
    assert p["location"]["home_terms"] == ["berlin", "germany"]
    # untouched fields survive the merge
    assert "exclude_titles" in p and "marketing" in p["exclude_titles"]


def test_put_profile_partial_location_merge(client):
    client.put("/api/profile", json={"home_city": "Berlin"})
    client.put("/api/profile", json={"remote_regions": ["europe"]})
    loc = client.get("/api/profile").json()["profile"]["location"]
    assert loc["home_city"] == "Berlin" and loc["remote_regions"] == ["europe"]


def test_get_profile_location_falls_back_to_defaults(client):
    # shipped profile has no `location:` block — the page still gets the real rules
    loc = client.get("/api/profile").json()["location"]
    assert loc["home_city"] == "london"
    assert "edinburgh" in loc["home_terms"] and "eu " in loc["remote_regions"]
    client.put("/api/profile", json={"home_terms": ["berlin"]})
    loc = client.get("/api/profile").json()["location"]
    assert loc["home_terms"] == ["berlin"] and loc["home_city"] == "london"


def test_put_profile_role_toggles_and_exclusions(client):
    r = client.put("/api/profile", json={
        "include_product_owner": False, "include_ai_innovation": False,
        "exclude_titles": ["marketing", "intern"]})
    assert r.status_code == 200
    p = client.get("/api/profile").json()["profile"]
    assert p["include_product_owner"] is False and p["include_ai_innovation"] is False
    assert p["exclude_titles"] == ["marketing", "intern"]
    assert p["seniority_min"] == 3                      # untouched


def test_put_profile_employment_and_work_types(client):
    p = client.get("/api/profile").json()
    assert p["location"]["workplace"] == ["On site", "Hybrid", "Remote"]   # default: all
    r = client.put("/api/profile", json={
        "employment": ["Contract", "Full time"], "workplace": ["Hybrid", "On site"]})
    assert r.status_code == 200
    p = client.get("/api/profile").json()
    assert p["profile"]["employment"] == ["Full time", "Contract"]         # canonical order
    assert p["profile"]["workplace"] == ["On site", "Hybrid"]
    assert p["profile"]["allow_remote"] is False                           # kept in step
    assert p["location"]["workplace"] == ["On site", "Hybrid"]
    # the older flag still works, and re-adds Remote to the stored list
    client.put("/api/profile", json={"allow_remote": True})
    p = client.get("/api/profile").json()
    assert p["profile"]["workplace"] == ["On site", "Hybrid", "Remote"]
    assert p["location"]["workplace"] == ["On site", "Hybrid", "Remote"]


def test_put_profile_validates(client):
    assert client.put("/api/profile", json={"home_terms": []}).status_code == 422
    assert client.put("/api/profile", json={"employment": []}).status_code == 422
    assert client.put("/api/profile", json={"employment": ["Zero hours"]}).status_code == 422
    assert client.put("/api/profile", json={"workplace": []}).status_code == 422
    assert client.put("/api/profile", json={"workplace": ["Anywhere"]}).status_code == 422

    assert client.put("/api/profile", json={"seniority_min": 12}).status_code == 422
    assert client.put("/api/profile",
                      json={"home_terms": ["ok", "  "]}).status_code == 422


# --- job status/notes editing ----------------------------------------------------

def test_patch_job_applied_and_notes(client):
    r = client.patch("/api/jobs/aaa11111",
                     json={"status": "applied", "notes": "Applied today."})
    assert r.status_code == 200
    d = client.get("/api/jobs/aaa11111").json()
    assert d["status"] == "applied" and d["notes"] == "Applied today."
    # ad text untouched, status visible in the (rebuilt) index
    assert "bold" in d["ad_markdown"]
    jobs = client.get("/api/jobs?status=applied").json()
    assert [j["id"] for j in jobs["jobs"]] == ["aaa11111"]


def test_patch_job_unmark_applied(client):
    client.patch("/api/jobs/aaa11111", json={"status": "applied"})
    client.patch("/api/jobs/aaa11111", json={"status": "open"})
    assert client.get("/api/jobs/aaa11111").json()["status"] == "open"


def test_patch_job_rejected(client):
    r = client.patch("/api/jobs/aaa11111", json={"status": "rejected"})
    assert r.status_code == 200
    assert client.get("/api/jobs/aaa11111").json()["status"] == "rejected"
    jobs = client.get("/api/jobs?status=rejected").json()
    assert [j["id"] for j in jobs["jobs"]] == ["aaa11111"]
    # rejected roles are hidden from the default (open) view
    assert "aaa11111" not in [j["id"] for j in client.get("/api/jobs").json()["jobs"]]
    # undo: back to applied
    client.patch("/api/jobs/aaa11111", json={"status": "applied"})
    assert client.get("/api/jobs/aaa11111").json()["status"] == "applied"


def test_patch_job_validation(client):
    assert client.patch("/api/jobs/aaa11111", json={}).status_code == 422
    assert client.patch("/api/jobs/aaa11111",
                        json={"status": "closed"}).status_code == 422
    assert client.patch("/api/jobs/nope1234",
                        json={"status": "applied"}).status_code == 404
