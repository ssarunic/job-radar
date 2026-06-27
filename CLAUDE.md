# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State

This repo is **spec-only**: it contains a single `README.md` that is a complete product specification. No source code, dependencies, build tooling, or tests exist yet. When asked to implement, you are building from scratch against the spec — there are no existing conventions to match beyond what the spec dictates below.

## What This Builds

A Python CLI that helps a single user find and track senior Product Management roles at a list of target companies. Two on-demand modes:

- **Exploratory Mode** — enrich a company list (description, industry, HQ, funding, revenue, employees) into a Company Index XLSX.
- **Job Seek Mode** — discover currently-open senior PM roles per company, filter/rank them, and output a Job Postings XLSX.

Input is an XLSX (company name in first column). Every run also emits a change diff (XLSX/CSV) and a console/TXT summary.

## Planned Architecture (from README §21–22)

Hybrid design: **hardcoded logic for reliability + Claude API only for fuzzy parsing.** This split is deliberate — keep it.

- **Hardcoded** (no API): URL/careers-page discovery, employment-type & location keyword filters, validation/formatting, rate limiting, retries, dedup, seniority ranking.
- **Claude API** (`services/claude_service.py`): job-title classification, salary/comp extraction from free text, company description summarization, requirement parsing. Always fall back to regex/heuristics if the API fails; cache successful extractions; validate every response against a JSON schema.

Intended module layout: `main.py` (Click CLI, mode select, hardcoded config) · `data/` (pandas XLSX I/O, file storage) · `models/` (dataclasses for Company / JobPosting) · `scrapers/` (requests + BeautifulSoup, per-domain rate limiter, site-specific parsers) · `services/` (company_enricher, job_finder, title_normalizer, location_filter, claude_service, response_parser) · `outputs/` (report_generator, diff_calculator) · `prompts/`.

Stack: Python 3.9+, pandas + openpyxl, requests + BeautifulSoup4, anthropic, click, python-dateutil. Target cost ~$15–30 for 300 companies (vs $150+ for pure-API), which is why most logic must stay hardcoded.

## Domain Rules That Are Easy To Get Wrong

These are the non-obvious rules the implementation must encode (README §11–15). They drive most of the business logic:

- **Seniority ranking** (numeric): CPO 9, VP 8, Director 7, Head 6, EIR ~6, Principal 5, Group 4, Senior 3, Product Manager/Mid 2, Product Owner 2 (→3 if title contains senior/lead). **Keep a role only if rank ≥ 3**, OR it's a Product Owner and `include product owner` is true.
- **Title exclusions**: drop titles containing marketing/growth marketing/brand (unless a second distinct title matches a PM pattern exactly), and people-ops/HR/talent/design-only roles.
- **Employment type**: exclude Contract — keep only Full time / Part time.
- **Salary**: never convert currency. Detect symbol/code, extract min/max (single number → both), always preserve the original text in `SalaryOriginalText`. Bonus mentioned → `CompensationType = Base+Bonus`.
- **Funding / revenue / employees**: store original strings (no conversion). For employee ranges use the midpoint for heuristics (51–200 → 125) and note the approximation.
- **Location**: accept London / UK / United Kingdom / England-with-London; remote OK if UK/Europe/EMEA-eligible (not US-only). Multi-location postings expand to one row per location, max 5; if >5 and includes London, keep only London + Remote.
- **Per-company cap**: keep top 10 most senior roles; ties broken by posted date, then alphabetical.
- **Dedup**: company = same canonical domain; job = same `JobAdURL` OR same Company + normalized title + first 120 chars of description + same location.
- **Posting lifecycle**: a posting missing for N=2 runs → `Suspected Filled`, then `Closed` on the next run.

## Operational Constraints

Public HTML only — respect robots.txt, no login areas. Defaults: 20s request timeout, 1 req/sec per domain, 2 retries with exponential backoff, 45-day recency cutoff, 30-minute runtime budget per batch, 50 companies initial / 300 hard cap. API keys and file paths are hardcoded in config per the spec (single-user tool).

When details are ambiguous, the README is the source of truth — check it before inventing behavior. Items marked ✅ in the README are confirmed decisions, not open questions.
