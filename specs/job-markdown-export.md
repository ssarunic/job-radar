# Job ad Markdown export

> **Status:** ✅ implemented. One-click Markdown of a role from the web UI — for
> pasting into Claude/an LLM — instead of copy-pasting the rendered HTML page.

## Why

The canonical store is already the artifact we want (`jobs/<company>/
<role>--<id>.md`: YAML frontmatter with every extracted fact + the captured ad
as Markdown + `## My notes`). Today the only way to get it out of the deployed
web app is to copy the rendered HTML. This feature serves the canonical file
over HTTP, verbatim — no new rendition, no conversion, honouring
constitution "Markdown is canonical".

## Surface

- **`GET /api/jobs/{job_id}/markdown`** — returns the canonical role file
  **byte-for-byte** (frontmatter + ad + notes), `Content-Type:
  text/markdown; charset=utf-8`. 404 (same shape as `GET /api/jobs/{id}`)
  when the id is unknown or the file is gone. Resolves the file via the
  existing `_role_path(job_id)` (index `_path` lookup — no MD scan).
  - `?download=1` adds `Content-Disposition: attachment;
    filename="<company_slug>--<file stem>.md"` (e.g.
    `fin-ai--senior-product-manager--d70c6f2e.md`) so the browser saves
    instead of displaying.
  - Path style: a sibling segment (`/markdown`), **not** `/{job_id}.md` — a
    `.md` suffix would be ambiguous against the existing `/api/jobs/{job_id}`
    route (Starlette path params match `[^/]+`, so ordering would decide).
- **Web** (`JobDetail.tsx`), next to "View original ↗":
  - **"⧉ Copy Markdown"** — fetches the endpoint and writes the text to the
    clipboard; this is the primary paste-into-Claude flow. Brief "Copied ✓"
    confirmation state on the button. `navigator.clipboard` only exists in
    secure contexts, and the app is normally served over plain http on the
    tailnet — so insecure contexts fall back to the hidden-textarea
    `document.execCommand("copy")` trick.
  - **"⬇ .md"** — plain `<a href=".../markdown?download=1">` download link.

## Non-goals / notes

- **No new Markdown rendition.** The file is served as stored. Frontmatter is
  a feature, not noise: it carries salary/location/URL/status facts an LLM
  should see.
- **`## My notes` is included.** Single-user tool; the notes are the user's
  own context and usually improve the LLM prompt. Not configurable for now.
- **MCP unchanged** — `get_job` already returns `ad_markdown` + `notes`;
  agents don't need this endpoint. It exists for the human-in-a-browser flow.
- **Read-only** — no index rebuild, no writes, no rate-limit concerns
  (tailnet-only single user).

## Tests

`webapp/backend/tests/test_api.py`: 200 with `text/markdown` content type and
body identical to the on-disk file (starts with `---`, contains the id);
`?download=1` sets the attachment disposition with the expected filename;
404 on unknown id.

## Docs

One line in the `docs/` user guide (job page section): you can copy a role as
Markdown or download the `.md` file to share it with an AI assistant.
