# In-UI notes + applied status

> **Status:** ✅ implemented. User-owned role fields (`status: applied`,
> `## My notes`) editable from the web UI and MCP, not just the file.

## Surface

- **`outputs/md_writer.update_user_fields(path, status=None, notes=None)`** —
  the single writer for user-owned fields: rewrites frontmatter `status`
  and/or the `## My notes` section, preserving the captured ad text verbatim
  (atomic write). `None` leaves a field untouched.
- **`PATCH /api/jobs/{id}`** — `{status?, notes?}`. Status restricted to
  `applied` | `open` (422 otherwise — `suspected_filled`/`closed` belong to
  the scan lifecycle); rebuilds the derived index on status change (status is
  indexed; notes are read from the file).
- **Web** (`JobDetail.tsx`): "✓ Mark applied"/"Unmark applied" button (shown
  for open/applied roles only) + a My-notes editor (textarea, Markdown,
  edit/save/cancel).
- **MCP `set_job_status(id, status, note=None)`** — same restriction; `note`
  **appends** to existing notes (the conversational "I applied" flow logs a
  dated line rather than replacing the user's text).

## Invariants

- The reconciler already never auto-advances an `applied` role
  (`services/reconciler.py`); this feature only adds writers for the fields it
  protects.
- Ad text is never modified by any of these paths (covered by tests).

## Tests

`tests/test_md_writer_user_fields.py` (helper: status-only, notes-only,
clearing); `webapp/backend/tests/test_api.py` (PATCH: persist + index rebuild,
unmark, validation); `webapp/backend/tests/test_mcp.py` (tool: apply + note
append, revert, unknown id, surface list).
