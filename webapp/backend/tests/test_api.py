"""Web API tests — network-free, against a temp canonical store."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as webapp
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
    assert client.post("/api/companies", json={"query": "Nope Inc"}).status_code == 422


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
