# Connecting Claude (MCP)

JobRadar ships an [MCP](https://modelcontextprotocol.io) server, so Claude
(Desktop, Code, or claude.ai integrations) can work with your tracked roles
conversationally:

- "What's new since yesterday?"
- "How do I stack up against each open role?" (Claude reads the full ad text)
- "Follow Revolut for me" (Claude finds the careers URL and follows it)

## Endpoint

The MCP server runs inside the web container at:

```
http://localhost:8765/mcp        (Streamable HTTP)
```

If JobRadar runs on another machine (a home server, a Pi on your Tailscale
network), use that host instead — and note the server only accepts Host names
it's told about via `JSA_MCP_ALLOWED_HOSTS` (see `deploy/docker-compose.yml`
for an example).

## Claude Code

```bash
claude mcp add jobradar --transport http http://localhost:8765/mcp
```

## Claude Desktop

Settings → Connectors → Add custom connector → URL
`http://localhost:8765/mcp`.

## What Claude can do

| Ask | Tool used |
|---|---|
| Headline numbers | `stats` |
| What's new today / this week | `new_jobs` |
| Browse & filter roles | `list_jobs`, `search_jobs` |
| Full ad text + fit judgement | `get_job` |
| Companies you track | `list_companies`, `company_roles` |
| Start/stop tracking | `follow_company`, `unfollow_company` |
| Mark applied + log a note | `set_job_status` |

All read-write operations touch only your own store; there's no cloud account
behind any of this.
