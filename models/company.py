"""Company dataclass for Exploratory/enrichment mode (product-spec §6.1)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Company:
    name: str = ""
    slug: str = ""
    careers_url: str = ""
    ats_type: str = ""
    description: str = ""              # 1-2 sentence summary
    industry: str = ""
    sub_industry: str = ""
    hq_location: str = ""
    total_funding: str = ""           # original string, no conversion (product-spec §7)
    main_investors: list = field(default_factory=list)
    year_founded: str = ""
    employee_count: str = ""          # original string / range
    revenue: str = ""
    data_confidence: str = "Low"      # High | Medium | Low (product-spec §14)
    last_updated_utc: str = ""
    notes: str = ""

    def to_frontmatter(self) -> dict:
        return {
            "name": self.name,
            "slug": self.slug,
            "careers_url": self.careers_url,
            "ats_type": self.ats_type,
            "industry": self.industry,
            "sub_industry": self.sub_industry,
            "hq_location": self.hq_location,
            "total_funding": self.total_funding,
            "main_investors": list(self.main_investors),
            "year_founded": self.year_founded,
            "employee_count": self.employee_count,
            "revenue": self.revenue,
            "data_confidence": self.data_confidence,
            "last_updated_utc": self.last_updated_utc,
            "notes": self.notes,
        }
