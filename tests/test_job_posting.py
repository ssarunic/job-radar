"""Stable IDs, URL canonicalisation, slug generation (SPEC §6.2)."""
from models.job_posting import JobPosting, _slugify, canonical_url


def _jp(**kw):
    base = dict(company="Monzo", company_slug="monzo", title_raw="Senior Product Manager",
                locations=["London"], job_ad_url="https://job-boards.greenhouse.io/monzo/jobs/123")
    base.update(kw)
    return JobPosting(**base)


def test_id_stable_for_same_url():
    assert _jp().id == _jp().id


def test_id_stable_across_location_change():
    """#3: URL-backed id must NOT change when location labels change."""
    assert _jp(locations=["London"]).id == _jp(locations=["Remote", "Edinburgh"]).id


def test_id_is_8_hex():
    jid = _jp().id
    assert len(jid) == 8
    int(jid, 16)  # valid hex


def test_id_without_url_uses_composite():
    a = _jp(job_ad_url="", description="alpha body text")
    b = _jp(job_ad_url="", description="alpha body text")
    assert a.id == b.id  # deterministic from company+title+desc+locations


def test_id_without_url_varies_by_location():
    """No-URL fallback still distinguishes by location (product-spec §15)."""
    a = _jp(job_ad_url="", locations=["London"])
    b = _jp(job_ad_url="", locations=["Manchester"])
    assert a.id != b.id


def test_canonical_url_strips_query_fragment_and_trailing_slash():
    assert canonical_url("https://Example.com/Jobs/123/?utm=x#frag") == \
        "https://example.com/Jobs/123"


def test_canonical_url_lowercases_host_only():
    # path case preserved, host lowercased
    assert canonical_url("HTTPS://JOBS.LEVER.CO/Acme/Abc") == \
        "https://jobs.lever.co/Acme/Abc"


def test_id_ignores_url_query_changes():
    a = _jp(job_ad_url="https://x.com/jobs/9?ref=a")
    b = _jp(job_ad_url="https://x.com/jobs/9?ref=b")
    assert a.id == b.id


def test_role_slug():
    assert _slugify("Senior PM, Payments! (Remote)") == "senior-pm-payments-remote"
    assert _jp(title_raw="Head of Product").role_slug == "head-of-product"
