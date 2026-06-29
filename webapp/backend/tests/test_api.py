"""Web API tests — network-free, against a temp canonical store."""
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
    monkeypatch.setenv("JSA_ROOT", str(tmp_path))
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
