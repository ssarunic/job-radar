# JobRadar MCP server (remote, OAuth)

**Status**: 🔨 In progress — Phase A (read tools) + Phase 2 management tools implemented
and tested; OAuth (Phase B) and Funnel exposure (Phase C) pending
**Created**: 2026-07-02
**Priority**: Medium (unlocks conversational access from Claude Desktop + mobile)

## Overview

Expose JobRadar as a **remote MCP server** so Claude (Desktop + mobile / claude.ai) can
query the tracked-role repository conversationally — "what's new today", "search product
lead roles", "show me role X so I can judge fit". **Phase 1 is read-only**: list / search
jobs and return an individual job's full ad text. **Phase 2 adds management**:
follow/unfollow a company (the client finds the ATS URL; the server consumes it).

The server is a thin layer over the **existing read API** (`services/queries.py`) —
the same store the web app and CLI use — mounted into the existing FastAPI app, so it
ships on the same image + push-deploy pipeline. It's exposed publicly over **HTTPS via
Tailscale Funnel** and protected by **OAuth 2.1** (the auth remote MCP connectors expect).

**The CV lives in the user's Claude project**, not the server. Fit analysis ("how do I
fit Attio's Product Lead role?") is Claude-side reasoning over `get_job`'s ad text + the
project CV — the server has no CV and no fit tool.

## Goals

1. Claude Desktop + mobile connect to `https://dalstonserver.<tailnet>.ts.net/mcp` and use
   read tools over the tracked roles.
2. Read tools: **list / search jobs**, **get one job's full ad text**, plus light company reads.
3. Remote **Streamable HTTP** transport + **OAuth 2.1** auth; public HTTPS via **Tailscale Funnel**.
4. Reuse `services.queries` (no logic duplication); rides the existing deploy pipeline.

## Non-goals

- **Full-fleet seek from MCP** ("re-scan all companies") — the daily run and the web UI's
  Refresh cover it; follow's scoped single-company scan is the only MCP-triggered scrape.
- **Server-side ATS discovery by company name** — probing slug variants against four ATS
  APIs is slow and unreliable inside a tool call; the *client* (Claude) web-searches for
  the board and passes a clean ATS URL. The server never searches the web.
- **Fetching un-tracked/arbitrary ads** (`get_job_by_url`) — deferred; for a role not in the
  DB, paste the ad into chat or follow the company.
- **Server-side CV / a fit tool** — CV lives in the Claude project; fit is Claude-side.
- Multi-user. OAuth is single-user (one login).

## Background findings

- FastAPI app + read endpoints over `queries`: `webapp/backend/app.py` (`GET /api/jobs`,
  `/api/jobs/{id}`, `/api/companies`, `/api/companies/{slug}`). MCP tools map onto the same
  `queries` functions — [`services/queries.py`](../services/queries.py):
  `list_roles`, `role_summary`, `get_role`, `stats`, `group_roles`.
- Store paths honour `JSA_ROOT` (`/data` on the Pi) via `services/store.py` — the MCP reads
  the same live store the daily scraper writes.
- Deploy: `deploy/docker-compose.yml` runs the web service on `:8765`; `.github/workflows/release.yml`
  push-deploys on tag. Mounting `/mcp` into the same app ⇒ same image, same pipeline.
- Tailscale is already on the Pi (`dalstonserver.tail824f04.ts.net`); the web app is
  tailnet-only today. **Funnel** exposes a chosen path publicly over HTTPS with a `ts.net` cert.

## Design

### Transport & hosting
- **MCP Python SDK (FastMCP), Streamable HTTP transport, mounted into the existing FastAPI app
  under `/mcp`** — one server, one deploy, shared `queries`/`store`. Add `mcp` to the runtime
  deps + `Dockerfile`.
- Read-only: every tool calls `services.queries` against `store` (`JSA_ROOT=/data`). No writes.

### Tools (Phase 1)
| Tool | Args | Returns | Backed by |
|---|---|---|---|
| `list_jobs` | `status="open", company?, min_rank?, q?, sort="seniority", limit?` | role summaries (title, company, rank, locations, salary, status, first_seen, web deep-link) | `queries.list_roles` + `role_summary` |
| `search_jobs` | `q, status="open"` | same shape, filtered by company+title | `list_roles(q=…)` |
| `new_jobs` | `days=1` | open roles with `first_seen` within N days ("what's new today") | `list_roles` + date filter |
| `get_job` | `id` | **full role**: frontmatter fields + **Markdown ad text** + notes + external URL (the text Claude reasons over for fit) | `queries.get_role` |
| `list_companies` | — | tracked companies + open-role counts | `registry` + counts (as `/api/companies`) |
| `company_roles` | `slug` | a company's open roles | `list_roles(company=slug)` |
| `stats` | — | open / new-7d / companies (distinct with ≥1 tracked role, not the registry) / last-run | `queries.stats` |

Results are structured JSON reusing `role_summary` / `get_role` shapes; each role carries its
web deep-link (`web_base_url/jobs/<id>`) so Claude can cite/link.

### Tools (Phase 2 — management)

Write tools over the same registry the web app manages (`config/companies.csv`, atomic
writes via `registry`). **Division of labour:** the *client* (Claude) resolves a company
name to its ATS job-board URL (web search → follow through to the board); the *server*
consumes only a clean ATS URL — it parses it with `discovery._from_url` and never
searches the web.

| Tool | Args | Side effects / returns | Backed by |
|---|---|---|---|
| `follow_company` | `ats_url, name?, scan=true` | appends to the registry; `scan=true` runs a **scoped one-company seek** (Slack suppressed, failure non-fatal — same semantics as web `POST /api/companies`) so roles are queryable immediately; the return includes the `open_roles` count the scan kept (0 = board live, no senior-PM matches — not a failure). Unrecognised ATS / already-active → `{"error": …}`; a previously-unfollowed company is **re-activated** instead of erroring | `discovery` + `registry.add_company` + `run_service.seek_run` |
| `unfollow_company` | `slug` | sets `active=false` (data kept, daily scrape skips it); unknown slug → `{"error": …}` | `registry.set_active` |

Accepted `ats_url` forms: the seven adapter boards (`(job-)boards.greenhouse.io/<slug>`,
`jobs.ashbyhq.com/<slug>`, `jobs.lever.co/<slug>`, `jobs.smartrecruiters.com/<Company>`,
`<tenant>.myworkdayjobs.com/<site>`, Oracle `…oraclecloud.com…`, `<slug>.recruitee.com`)
plus careers pages that embed a detectable ATS (Talemetry/Workday/Recruitee body probe).
Anything resolving to `custom` is rejected with an error that tells the model what to
pass instead. Because discovery body-probes unrecognised hosts with a real GET, the
model-supplied URL passes an **SSRF guard first**: non-http(s) schemes, loopback /
private / link-local addresses, and non-public hostnames (`localhost`, bare intranet
names, `.local`/`.internal`/…) are refused before any fetch.

### Tool descriptions are the model-facing contract

The client model never reads this spec. What it reads — and all it reads — is the
**server `instructions`**, the **tool docstrings**, and the **parameter schemas** in
`webapp/backend/mcp_app.py`. Those are prompt text, not documentation; the code is
authoritative for their wording. Rules:

- **Server `instructions`** (FastMCP's `instructions=`) carry the cross-tool guidance:
  the which-tool-when decision tree and the result-field glossary (`first_seen` vs
  `posted_date`, status lifecycle, seniority-rank ladder, salary semantics). Anything
  that applies to more than one tool lives here, not repeated per docstring.
- **Every tool docstring** must say *when to use it* (especially vs overlapping tools —
  e.g. `search_jobs` is a subset of `list_jobs`) and *how to read its output*, including
  its not-found shape (`[]` vs `{"error": …}`).
- **Enum-like params use `Literal`** (`status`, `sort`) so the schema constrains values
  instead of prose listing them.
- Field-semantics traps get called out where the model will trip on them: `stats.companies`
  counts companies *with tracked roles*, `new_jobs` filters on `first_seen` (scraper
  discovery), not `posted_date`.
- Write-tools follow the same rules, plus must state their side effects (what is
  written, what network activity happens, what the failure modes are) — see
  `follow_company`'s docstring for the pattern.

### Auth — OAuth 2.1 (single-user)
Remote MCP connectors authenticate via the **MCP Authorization spec** (OAuth 2.1): the MCP
server is an OAuth-protected **resource server**, with an **authorization server** (same app).
Implement the minimum the connector needs:
- **Dynamic Client Registration** (RFC 7591) — Claude registers a client.
- **Authorization Code + PKCE** flow. A single **shared-secret login** gates the consent step
  (it's just you); auto-approve after login.
- **Token** issue + validate (JWT or opaque + introspection); reject unauthenticated `/mcp` calls.
- Use the **MCP SDK's auth support** (or `authlib`) — do **not** hand-roll the full protocol.
- Secrets (signing key, login password, client secret) live in the Pi's `.env` (like the rest).
- **Risk:** OAuth is the heaviest part — isolate it in Phase B behind a clear gate.

### Exposure — Tailscale Funnel (only `/mcp` public)
- `tailscale funnel` exposes **only the `/mcp` path** on `https://dalstonserver.<tailnet>.ts.net/mcp`
  (valid `ts.net` cert, ports 443/8443/10000). The web UI + other `/api/*` routes stay **tailnet-only**
  (`tailscale serve`, not funnel). Funnel makes `/mcp` reachable from the public internet ⇒ OAuth is
  **mandatory**, which is why it gates that path.
- One-time Pi setup documented in `deploy.md`.
- The SDK's DNS-rebinding guard validates the `Host` header (unknown → 421). Defaults
  allow local + test hosts only; the Pi must set **`JSA_MCP_ALLOWED_HOSTS`** (comma list,
  `host:*` wildcards ports) to its tailnet + `ts.net` names — part of the Phase C checklist.

### Client setup
Claude Desktop / claude.ai → **Add custom connector** → URL `https://dalstonserver.<tailnet>.ts.net/mcp`
→ complete the OAuth login → tools appear. Then ask: *"what senior PM roles are new today?"*,
*"show me the Kraken product roles"*, *"get role <id> and tell me how I fit given my CV"*,
*"start tracking Attio"* (Claude web-searches for Attio's ATS board, then calls
`follow_company` with the clean URL).

## Execution plan

### Phase A — MCP server + read tools (no auth, tailnet-local) ✅
Mount FastMCP `/mcp` into the FastAPI app; implement the seven read tools over `queries`.
| # | File | Change |
|---|---|---|
| 1 | `webapp/backend/mcp_app.py` (new) | FastMCP server + tools; mounted from `app.py` |
| 2 | `webapp/backend/app.py` | mount `/mcp` |
| 3 | `Dockerfile` / deps | add `mcp` |
| 4 | `webapp/backend/tests/test_mcp.py` (new) | tool calls against a temp store (network-free) |

**Gate:** tests green; a local MCP client lists tools and `list_jobs`/`get_job`/`search_jobs` return correct data; `ruff` clean.

### Phase 2 — management tools (follow / unfollow) ✅
`follow_company` + `unfollow_company` in `mcp_app.py` (see Tools Phase 2 above), reusing
`discovery` / `registry` / the web follow's scoped-scan semantics. Tests in `test_mcp.py`
cover the clean-URL path, scan on/off, scan-failure non-fatality, non-URL and
unrecognised-ATS rejection, dedupe, re-activation, and unfollow.

**Gate:** tests green; from an MCP client, `follow_company` with a clean ATS URL adds the
company and its roles are queryable; `unfollow_company` deactivates it; `ruff` clean.
**Gate verified 2026-07-02** live over Streamable HTTP: `follow_company("https://boards.greenhouse.io/gocardless")`
resolved to `greenhouse/gocardless`, wrote the registry, and ran the scoped scan (board ok,
35 listed, 0 kept — no matching senior-PM roles that day); re-follow deduped; unfollow set
`active=false` keeping data; unknown slug returned the guided error.

### Phase B — OAuth 2.1 + protect `/mcp`
Add the auth/authorization server; require a valid token on `/mcp`.
**Gate:** a client can register + PKCE-auth + call a tool; unauthenticated → 401; secrets from `.env`.

### Phase C — Funnel exposure + real client
Funnel only `/mcp`; connect Claude Desktop + mobile end-to-end.
**Gate:** connect from Claude Desktop, run "what's new today"; web UI still tailnet-only.

### Phase D — Docs
`deploy.md` (Funnel + connector setup + the new `.env` secrets); `specs/README.md` index; mark this spec ✅.

## Alternatives considered
- **Cloudflare Tunnel + Access** — offloads auth but adds a vendor + a domain. Rejected (stay all-Tailscale).
- **Static bearer token** — simplest, but connectors want OAuth; not reliable. Rejected.
- **Standalone MCP process** — rejected; mounting on FastAPI reuses `queries` + one deploy.
- **`get_job_by_url` for un-tracked ads** — deferred (DB-only Phase 1).
- **Skill-describes-API / CLI** — rejected earlier: Claude-Code-only and/or brittle HTTP-guessing; MCP is the cross-surface, structured choice.

## Open questions
- Exact auth implementation — MCP SDK's built-in auth vs `authlib`; resolved in Phase B by
  prototyping the connector's registration flow.
- Funnel path-scoping specifics (expose only `/mcp`, keep the rest private); verified in Phase C.

## Rollback plan
Additive — a new `/mcp` mount + Funnel config + `.env` secrets. Disable by unmounting `/mcp`
and `tailscale funnel off`. No store/schema changes.
