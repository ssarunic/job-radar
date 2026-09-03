"""Stage A asks the adapter for a usable location only when the listing row's
location can't be judged AND the row already passed title + recency (Barclays:
"2 Locations" / street-address sites hid every UK role)."""
from datetime import date

from services import pipeline

PROFILE = {"seniority_min": 3, "include_product_owner": True, "exclude_titles": [],
           "locations": ["London"], "allow_remote": True, "employment": ["Full time"],
           "recency_days": 3650, "max_roles_per_company": 10}


class _Fetcher:
    needs_detail = True
    live_listing = True

    def __init__(self, answers):
        self.answers, self.resolved = answers, []

    def resolve_location(self, url):
        self.resolved.append(url)
        return self.answers.get(url, "")

    def detail(self, url):
        return "Employment type: Full time\n\nBody."


def _row(title, location, url):
    return {"title": title, "location": location, "url": url, "employment_type": "",
            "description": "", "salary_text": "", "source_detail": "Workday"}


def test_unusable_location_is_resolved_for_title_passing_rows_only():
    # d, h: resolve -> UK. se: title fails, no lookup. ok: usable, no lookup.
    # us: resolves to the US -> dropped.
    raw = [_row("Product Manager - Director", "2 Locations", "https://w/d"),
           _row("Head of Product", "Canary Wharf, 1 Churchill Place", "https://w/h"),
           _row("Software Engineer", "2 Locations", "https://w/se"),
           _row("Senior Product Manager", "London", "https://w/ok"),
           _row("Director of Product", "2 Locations", "https://w/us")]
    f = _Fetcher({"https://w/d": ("Canary Wharf, 1 Churchill Place, United Kingdom; "
                                  "Glasgow, Clyde Place"),
                  "https://w/h": "Canary Wharf, 1 Churchill Place, United Kingdom",
                  "https://w/us": "New York, 745 7th Avenue, United States of America"})
    kept = pipeline.process_company({"name": "B", "slug": "b"}, PROFILE, raw, f, {}, None,
                                    date(2026, 9, 3))
    assert sorted(f.resolved) == ["https://w/d", "https://w/h", "https://w/us"]
    assert sorted(k.title_raw for k in kept) == \
        ["Head of Product", "Product Manager - Director", "Senior Product Manager"]
    by_title = {k.title_raw: k for k in kept}
    assert by_title["Product Manager - Director"].locations == ["United Kingdom"]
    assert by_title["Senior Product Manager"].locations == ["London"]


def test_resolver_errors_and_fetchers_without_hook_are_harmless():
    class _Boom(_Fetcher):
        def resolve_location(self, url):
            raise RuntimeError("down")

    class _NoHook:
        needs_detail = False
        live_listing = True

    raw = [_row("Head of Product", "2 Locations", "https://w/x")]
    for fetcher in (_Boom({}), _NoHook()):
        assert pipeline.process_company({"name": "B", "slug": "b"}, PROFILE, raw, fetcher, {},
                                        None, date(2026, 9, 3)) == []
