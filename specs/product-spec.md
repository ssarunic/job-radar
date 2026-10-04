# JobRadar – Product Spec

> _Moved from the repo root README (2026-07); code and specs cite it as
> "product-spec §N". The root README is now the user-facing landing page._

> **Status & authority.** This document is the original **product/domain spec** —
> it defines *what* the tool does and the business rules (seniority, filters,
> salary, lifecycle), and remains authoritative for those.
> It is **historical for storage & fetching**: it predates the implementation and
> describes XLSX outputs and an early module plan. For *how* data is stored and
> fetched, the authority is **`specs/constitution.md`** (principles) and
> **`specs/build-spec.md`** (storage layout, scraping ladder, ATS adapters,
> crawler policy). The canonical store is **Markdown + a derived JSONL index**,
> not XLSX. Where this README and `specs/` disagree, `specs/` wins.
>
> **Project status (2026-06-29) — implemented & deployed.** Working Python CLI
> (`seek` + `enrich`) + a FastAPI/React web app (browse roles + manage tracked
> companies), 267 tests. Fetches via a 9-adapter
> scraping ladder (browser-free — Talemetry uses `curl_cffi`). Ships via CI/CD:
> push a `vX.Y.Z` tag → GitHub Actions builds an arm64 image → GHCR → push-deploys
> to a Raspberry Pi over Tailscale SSH. The scraper runs **daily at 08:00
> Europe/London** and posts new senior PM roles to **Slack**, deep-linked to the
> web app. Runbook: **`specs/deploy.md`**.

## 1. Purpose

Help you find and track senior product management roles at a defined list of target companies. 
Two modes: 
* Exploratory (company enrichment) and 
* Job Seek (role discovery). 
Output: Two XLSX tables plus a reusable autonomous agent prompt (later).

## 2. Primary User

You (single job seeker). Future multi user out of scope now.

## 3. Modes Overview

### 3.1 Exploratory Mode (Company Enrichment)

For each company in the XLSX input list gather fresh public data and update the Company Index table.

### 3.2 Job Seek Mode (Role Discovery)

Iterate through the list. Find currently open senior product roles (London on site, London hybrid, or remote roles open to UK). Apply filters and ranking. Output Job Postings table.

## 4. Inputs

| Input                 | Format                               | Notes                 |
| --------------------- | ------------------------------------ | --------------------- |
| Company list          | **XLSX** (first column company name) | Provided by you. ✅    |
| Config (optional)     | Internal defaults                    | No separate file yet. |
| Stop words (optional) | Text list                            | May add later.        |

## 5. Outputs

| Output             | Format        | Notes                                                        |
| ------------------ | ------------- | ------------------------------------------------------------ |
| Company Index      | XLSX          | Versioned snapshot each run.                                 |
| Job Postings       | XLSX          | Up to 10 most senior qualifying roles per company per run. ✅ |
| Change Diff        | XLSX or CSV   | Assume we produce diff each run. ✅                           |
| Simple Run Summary | TXT / console | High level log only. ✅                                       |
| Final Prompt       | Markdown      | Produced when you say ready.                                 |

## 6. Data Fields

### 6.1 Company Index Fields

| Field          | Type                | Description                                                  |
| -------------- | ------------------- | ------------------------------------------------------------ |
| CompanyName    | String              | Official name.                                               |
| Description    | Text                | 1–2 sentence summary.                                        |
| WebsiteURL     | URL                 | Canonical https homepage.                                    |
| CareerPageURL  | URL                 | Detected careers page.                                       |
| Industry       | Categorical         | Broad industry (Fintech, Consumer, etc).                     |
| SubIndustry    | Categorical         | Narrow tag (Legaltech etc).                                  |
| HQLocation     | String              | City, Country.                                               |
| TotalFunding   | String              | As stated (no conversion) eg \$120M, £5.2M. ✅ (was numeric+) |
| MainInvestors  | List                | Key investors.                                               |
| YearFounded    | Year                | Launch/founding year if public.                              |
| EmployeeCount  | Integer / RangeText | Use midpoint if only a range. ✅                              |
| Revenue        | String              | Latest disclosed (no conversion).                            |
| LastUpdatedUTC | Timestamp           | Enrichment run time.                                         |
| DataConfidence | Enum                | High Medium Low.                                             |
| Notes          | Text                | Flags or caveats.                                            |
| SourceURLs     | List                | URLs used (optional).                                        |
| RemovedFields  | Note                | ❌ CAGR removed per your request.                             |

### 6.2 Job Postings Fields

| Field                    | Type      | Description                                                                                                                                      |
| ------------------------ | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| CompanyName              | String    | Convenience.                                                                                                                                     |
| CompanyWebsiteURL        | URL       | Link back to Company Index.                                                                                                                      |
| JobAdURL                 | URL       | Unique posting URL (primary key).                                                                                                                |
| RoleNameRaw              | String    | Title as found.                                                                                                                                  |
| RoleNameNormalised       | Enum      | CPO, VP Product, Director of Product, Head of Product, Group Product Manager, Principal Product Manager, Senior Product Manager, Product Manager |
| SeniorityLevel           | Enum      | C Level, VP, Director, Head, Principal, Group, Senior, Mid, Other.                                                                               |
| EmploymentType           | Enum      | Full time, Part time (exclude Contract). ✅                                                                                                       |
| WorkplaceModel           | Enum      | On site, Hybrid, Remote.                                                                                                                         |
| OfficeLocation           | String    | City Country or Remote tag.                                                                                                                      |
| RemoteEligibleRegions    | String    | Regions allowed.                                                                                                                                 |
| SalaryMin                | Numeric   | As stated in original currency (no conversion). ✅                                                                                                |
| SalaryMax                | Numeric   | As stated in original currency. ✅                                                                                                                |
| SalaryCurrency           | String    | Currency code or symbol detection. ✅                                                                                                             |
| SalaryOriginalText       | Text      | Original string.                                                                                                                                 |
| CompensationType         | Enum      | Base Only, Base+Bonus, OTE, Equity, Not Stated.                                                                                                  |
| RoleDescription          | Text      | Clean summary.                                                                                                                                   |
| Requirements             | Text      | Bullet list merged.                                                                                                                              |
| PostedDate               | Date      | If available.                                                                                                                                    |
| DetectedPostedDateSource | Enum      | Meta, Body, Sitemap, Feed.                                                                                                                       |
| CollectedDateUTC         | Timestamp | Capture time.                                                                                                                                    |
| Status                   | Enum      | Open, Suspected Filled, Closed.                                                                                                                  |
| SourceType               | Enum      | CompanySite, ATS, Aggregator.                                                                                                                    |
| SourceDetail             | String    | e.g. Greenhouse.                                                                                                                                 |
| FetchAttempts            | Integer   | Retry count.                                                                                                                                     |
| LastCheckedUTC           | Timestamp | Re validation time.                                                                                                                              |
| Notes                    | Text      | Manual or automated notes.                                                                                                                       |

## 7. Field Handling Rules (Adjusted)

- No currency conversion. Store salaries and financial figures in original currency and format. Provide min/max numerics plus currency code where parseable. Keep original text.
- Funding and revenue kept as original string if complex (e.g. Series B \$45M). Optional parse to numeric if clear.
- Employee range choose midpoint for numeric heuristics and store original (e.g. 51–200 → 125). Mark approximation in Notes.
- Title normalisation uses pattern list. Exclude Product Marketing even if includes Product Manager phrase unless truly dual role (assumption). ✅



## 8. Source Strategy (Public HTML Only)

| Need             | Primary                                                    | Fallback                                       |
| ---------------- | ---------------------------------------------------------- | ---------------------------------------------- |
| Company metadata | Company site pages (About, Careers, Press)                 | News articles, Wikipedia                       |
| Jobs             | Career page, ATS pages, sitemaps, job JSON feeds if public | Aggregators only if direct page blocked        |
| Funding          | Press releases, company blog, reputable news               | Crunchbase page only if accessible without API |
| Revenue          | Press, interviews, company blog, reports                   | None if absent                                 |
| Employees        | LinkedIn public (if visible), About page, news             | Estimation or omit                             |

## 9. Workflows

### 9.1 Exploratory Mode

1. Load XLSX list. 2. Normalise names (strip suffixes). 3. Resolve website (HEAD). 4. Find careers page via pattern scan (/careers /jobs /join). 5. Crawl limited pages (depth 1–2). 6. Extract description, HQ, founding year hints. 7. Scrape press/news for funding and revenue mentions (light, time boxed). 8. Derive employee midpoint. 9. Assign confidence. 10. Update table. 11. Save XLSX and diff. 12. Produce summary log (counts, errors, time).

### 9.2 Job Seek Mode

1. Load latest Company Index. 2. For each company fetch careers / ATS listing. 3. Extract postings. 4. Filter by seniority and title rules. 5. Expand multi location postings to one row per location (limit to relevant geography set). ✅ 6. For each kept posting fetch detail page. 7. Parse description, requirements, salary, posted date. 8. Normalise fields. 9. Rank by seniority. 10. Keep top 10 most senior per company (ties by posted date, then alphabetical). ✅ 11. Update status for previously seen postings. 12. Mark missing postings after N=2 runs as Suspected Filled then Closed on next run. 13. Save XLSX, diff, summary.

### 9.3 Run Triggers

- Both modes on demand initial phase. ✅
- Future scheduling (daily) planned but out of scope now.

## 10. Configuration Parameters (Current Defaults)

| Param                   | Default                                                 | Notes                                                                    |
| ----------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------ |
| min seniority           | Senior PM                                               | Filter keeps Senior PM and above plus any Product Owner (assumption). ✅  |
| include product owner   | true                                                    | See rule above.                                                          |
| exclude marketing roles | true                                                    | Titles containing Marketing (unless clearly separate listing) dropped. ✅ |
| exclude contract        | true                                                    | EmploymentType must be Full time or Part time. ✅                         |
| location cities         | London                                                  | Accept London variants.                                                  |
| allow remote            | true                                                    | Remote acceptable if UK/EMEA eligible.                                   |
| remote keywords         | remote, anywhere, UK remote, EMEA remote, Europe remote | Case insensitive.                                                        |
| recency days            | 45                                                      | Ignore older if date present.                                            |
| max roles per company   | 10                                                      | Most senior first. ✅                                                     |
| max companies per run   | 300 hard cap (initial 50). ✅                            |                                                                          |
| runtime budget          | 30 minutes per batch. ✅                                 |                                                                          |
| request timeout         | 20s                                                     | Per URL.                                                                 |
| rate limit per domain   | 1 req/sec                                               | Polite scraping.                                                         |
| retries                 | 2                                                       | Exponential backoff.                                                     |
| user agent              | Config string                                           | Identifies crawler purpose.                                              |
| diff output             | true                                                    | Always produce diff file. ✅                                              |
| notifications           | none now                                                | May add email later. ✅                                                   |

## 11. Title Normalisation Logic (Adjusted)

1. Lowercase. 2. Strip brackets. 3. Match patterns priority: cpo, chief product officer; vp product, vice president product; director of product; head of product; group product manager; principal product manager; staff product manager; product lead(er); senior product manager; product manager; product owner; entrepreneur in residence, eir. 4. Map product owner to Product Owner. 5. Exclude titles containing marketing, growth marketing, brand, unless second distinct title matches pattern exactly (rare). 6. Exclude people ops, HR, talent, design only roles; also graduate/internship-programme entry-level roles ("Graduate Programme…", "Internship Programme…", "Graduate PM"). ✅ 7. Seniority ranking numeric: CPO 9, VP 8, Director 7, Head 6, Principal 5, Staff 5, Group 4, Product Lead(er) 4, Senior 3, Mid (Product Manager) 2, Product Owner 2 (unless contains senior/lead then 3), EIR 6 (approx between Head and Director). A VP/Director-prefixed "Product Lead(er)" promotes to that tier even when the seniority word isn't adjacent to "product" (e.g. "… Product Lead … Vice President" → VP 8). Corporate-grade titles — the bank/enterprise "<function> <sep> <grade>" form, either order and separated by a dash, comma, colon or brackets ("Product Manager - Director", "Product Owner, Vice President", "Director - Product Manager", "Product Management Director") — rank on the **grade**, since the function half alone would score 2 and be dropped. The grade must sit adjacent to the product role, so "Director of Engineering, Product Manager" stays rank 2. AVP/Assistant Vice President has no rung here and keeps its function-based rank. ✅ UK-bank job-family aliases: "Product & Proposition Manager" / "Product and Proposition(s) Manager" / "Propositions Manager" are the PM role and are rewritten to it before matching ("Senior Product & Proposition Manager" → Senior Product Manager 3; "Lead Segment and Propositions Manager" → Product Manager 2, "Lead" is not a rung). ✅ Body-stated grades: a bank ad may title the bare job family and state the grade only in the body — Barclays' Workday template has a fixed "<grade> Expectations" section ("Vice President Expectations", "Director Expectations"). Adapters that flag `grades_in_body` (Workday) carry PM titles dropped *only by the seniority floor* through to the detail fetch, then re-rank every role on the body with the same rungs (VP 8, Director/Managing Director 7; AVP none) and drop the provisional ones still below the floor. A lift raises the rank but not the Stage-B cap order, so a body-graded role can still be cut by `max_roles_per_company` when higher-titled roles fill it. 8. Filter keep if rank ≥ 3 OR Product Owner included per config. 9. ✅ AI/Innovation leadership family (config `include_ai_innovation`, default on): titles whose domain is AI / Artificial Intelligence / GenAI / Innovation — including conjoined forms like "AI & Innovation" — rank by leadership role-word: Chief … Officer 9, VP 8, Director 7, Head 6, Lead(er) 4. Leadership role-words only (no manager tier — "Innovation Manager" is dropped), and IC-track qualifiers after the domain are excluded ("Head of AI Research", "VP AI Engineering", "AI Engineer Lead" all dropped). Example: "AI & Innovation Lead" → AI/Innovation Lead, rank 4, kept. PM patterns win when both match ("VP Product & AI" → VP Product). 10. ✅ Combined product + engineering titles: product leadership merged with technology/engineering ranks on the product ladder. Conjoined C-suite forms — "Chief Product and Technology Officer", "Chief Product & Engineering Officer", "Chief Digital and Product Officer", CPTO/CTPO — rank 9, provided **product** is one of the named domains, so a bare "Chief Technology Officer" is still dropped. The VP/Director/Head rungs already bridge the conjunction ("VP, Product & Engineering" → VP 8, "Head of Engineering and Product" → Head 6), and Director accepts the comma form alongside "of" ("Director, Product & Technology" → Director 7) — only when Director leads its title segment, so another function's director ("Sales Director, Product Specialists") isn't promoted. Engineering-only titles (CTO, VP Engineering, Head of Engineering) remain out of scope.

## 12. Location Handling (Expanded)

- Accept if location string includes London, UK, United Kingdom, England (with London). - For multi location listing produce separate rows per location up to 5 to avoid explosion. If more than 5 and includes London keep only London and Remote. - Remote accepted if open to UK / Europe / EMEA and not restricted to US only. - Mark WorkplaceModel by detection of keywords: hybrid (hybrid), remote (remote), otherwise on site.

## 13. Salary Processing (Adjusted)

- Detect currency symbol (£ € \$) or code. - Extract min and max numbers; if single number set both. - Do not convert. - Store SalaryCurrency and min/max numerics when clean. - Keep original text in SalaryOriginalText. - If range ambiguous (e.g. 80k–100k plus bonus) parse 80000–100000, set CompensationType Base+Bonus if bonus mentioned.

## 14. Data Quality and Confidence

High: ≥60 percent key fields present (Description, Website, Industry, Funding or Revenue or Employees) and at least two distinct page sources. Medium: single source. Low: partial or conflicting.

## 15. Deduplication Rules

- Company: same canonical domain. - Job posting: same JobAdURL OR same Company + RoleNameNormalised + first 120 chars of RoleDescription + same location.

## 16. Error Handling

Lightweight: retry network, mark failures. Aggregate counts in summary (success count, failures, blocked). Provide list of failed URLs for manual check. No full per URL log stored long term.

## 17. Security and Ethics

Public HTML only. Respect robots.txt. No login areas. Polite rate limiting.

## 18. Metrics (Updated)

| Metric                                            | Target                                          |
| ------------------------------------------------- | ----------------------------------------------- |
| Company coverage (basic fields)                   | >90 percent of companies enriched first run     |
| Role precision (senior PM+ or allowed exceptions) | >95 percent                                     |
| New role detection latency (on demand period)     | Within next run after posting                   |
| False positives (non PM roles)                    | <5 percent                                      |
| Data freshness (Company Index)                    | On demand not older than 30 days for key fields |

## 19. Risks and Mitigations

| Risk                                        | Impact         | Mitigation                                                           |
| ------------------------------------------- | -------------- | -------------------------------------------------------------------- |
| Title edge case (Product Owner lower level) | Noise          | Seniority ranking and potential future exclusion toggle              |
| Limited funding info without APIs           | Missing data   | Capture what is public, mark confidence Medium/Low                   |
| Salary formats varied                       | Parse errors   | Store original text always                                           |
| Time budget overrun                         | Incomplete run | Enforce per company time slice and early stop when budget approached |

## 20. Future Enhancements (Deferred)

- Alerts (email). - Fit score. - Cover letter drafts. - Scheduling automation. - API integration (when keys available). - Analytics dashboards.

## 21. System Architecture

### 21.1 Overview
Python-based CLI tool with hybrid approach: hardcoded logic for reliability + Claude API for intelligent parsing.

### 21.2 Core Components

**Main Controller** (`main.py`)
- CLI interface with mode selection (exploratory/job-seek)
- Hardcoded config (file paths, API keys)
- Run orchestration and logging

**Data Layer**
- Excel Handler (`data/excel_handler.py`) - pandas for XLSX I/O
- Models (`models/`) - dataclasses for Company/JobPosting schemas
- Storage (`data/storage.py`) - file-based persistence

**Scraping Engine**
- Web Scraper (`scrapers/web_scraper.py`) - requests + BeautifulSoup
- Rate Limiter (`scrapers/rate_limiter.py`) - domain-based throttling
- Parser Factory (`scrapers/parsers/`) - site-specific extraction logic

**AI Integration**
- Claude Service (`services/claude_service.py`) - Anthropic API client
- Prompt Templates (`prompts/`) - specialized extraction prompts
- Response Parser (`services/response_parser.py`) - JSON validation

**Business Logic**
- Company Enricher (`services/company_enricher.py`) - exploratory mode
- Job Finder (`services/job_finder.py`) - job seek mode
- Title Normalizer (`services/title_normalizer.py`) - PM role classification
- Location Filter (`services/location_filter.py`) - geography logic

**Output Generation**
- Report Generator (`outputs/report_generator.py`) - XLSX creation
- Diff Calculator (`outputs/diff_calculator.py`) - change tracking

### 21.3 Technology Stack
- Python 3.12+ (deployment simplicity)
- pandas + openpyxl (Excel handling)
- requests + BeautifulSoup4 (web scraping)
- anthropic (Claude API client)
- dataclasses (models)
- click (CLI interface)
- python-dateutil (date parsing)

### 21.4 Hybrid AI Integration Strategy

**Claude API Used For:**
- Job title classification and normalization
- Salary/compensation extraction from free text
- Company description summarization
- Complex requirement parsing

**Hardcoded Logic For:**
- URL patterns and site navigation
- Basic filtering (employment type, location keywords)
- Data validation and formatting
- Rate limiting and retry logic

**Benefits:**
- Cost-effective: ~$15-30 for 300 companies vs $150+ pure API
- Reliable core logic with intelligent parsing
- Graceful degradation if API fails
- Maintainable with fewer brittle rules

## 22. Claude API Integration Details

### 22.1 API Usage Patterns

**Company Enrichment Prompt:**
```
Extract company data from HTML and return JSON:
{
  "description": "1-2 sentence summary",
  "industry": "broad category",
  "sub_industry": "specific niche",
  "hq_location": "City, Country",
  "total_funding": "original format",
  "employee_count": "numeric or range",
  "year_founded": "YYYY or null"
}
```

**Job Classification Prompt:**
```
Analyze job posting and return JSON:
{
  "is_product_management": boolean,
  "seniority_level": "CPO|VP|Director|Head|Principal|Group|Senior|Mid|Other",
  "normalized_title": "standardized title",
  "employment_type": "Full time|Part time|Contract",
  "workplace_model": "On site|Hybrid|Remote"
}
```

**Salary Extraction Prompt:**
```
Extract salary information and return JSON:
{
  "salary_min": numeric,
  "salary_max": numeric,
  "currency": "GBP|USD|EUR",
  "compensation_type": "Base Only|Base+Bonus|OTE|Equity|Not Stated",
  "original_text": "exact string found"
}
```

### 22.2 Implementation Priority
1. Start with hardcoded logic for working system
2. Replace job title classification with Claude API
3. Add salary extraction for complex formats
4. Enhance company enrichment with AI parsing
5. Implement requirement/description summarization

### 22.3 Error Handling
- Fallback to regex patterns if API fails
- Cache successful extractions to reduce API calls
- Validate API responses against expected schemas
- Log API failures for manual review

## 23. Prompt Template (To Fill Later)

Will define system role, mode switch instructions, step flows, field schemas, ranking logic, filtering logic, output formatting, validation checklist, example outputs.

##
