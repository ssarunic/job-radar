"""Shared scraper contract (#1). Every adapter's listing() returns a ListingResult
so the ladder can make structured fall-through decisions."""
from __future__ import annotations

from dataclasses import dataclass, field


# status values
OK = "ok"          # postings fetched successfully (may still be 0 PM matches later)
EMPTY = "empty"    # source reachable but returned no postings at all
BLOCKED = "blocked"  # bot challenge / robots disallow — a real browser/human might see more
ERROR = "error"    # network/parse failure after retries


@dataclass
class ListingResult:
    status: str
    postings: list = field(default_factory=list)
    rung: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK
