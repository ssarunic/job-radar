import { useEffect, useRef, useState } from "react";
import { useParams, useLocation, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, apiSend, fmtSalary } from "../api";

// navigator.clipboard needs a secure context; the app is normally served over
// plain http on the tailnet, so fall back to the textarea/execCommand trick.
async function copyText(text: string) {
  if (window.isSecureContext && navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand("copy");   // returns false when blocked, doesn't throw
  ta.remove();
  if (!ok) throw new Error("copy blocked");
}

export default function JobDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  // The list passes its filter query via link state; back returns to that exact view.
  // Deep links (Slack, MCP) carry no state -> plain unfiltered list.
  const fromSearch = (useLocation().state as { fromSearch?: string } | null)?.fromSearch ?? "";
  const back = { pathname: "/", search: fromSearch };
  const { data, isLoading, isError } = useQuery({
    queryKey: ["job", id],
    queryFn: () => api(`/jobs/${id}`),
  });

  const update = useMutation({
    mutationFn: (patch: { status?: string; notes?: string }) =>
      apiSend(`/jobs/${id}`, "PATCH", patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", id] });
      qc.invalidateQueries({ queryKey: ["jobs"] });   // status shows in the list
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  const [copied, setCopied] = useState<"idle" | "busy" | "done" | "failed">("idle");
  const copiedReset = useRef<number | undefined>(undefined);

  useEffect(() => window.scrollTo(0, 0), []);   // don't inherit the list's scroll offset

  if (isLoading) return <p className="muted">Loading…</p>;
  if (isError || !data) return <p className="muted">Not found. <Link to={back}>← all roles</Link></p>;

  const d: any = data;
  const sal = fmtSalary(d.salary);
  const applied = d.status === "applied";
  const mdUrl = `/api/jobs/${id}/markdown`;
  const copyMarkdown = async () => {
    clearTimeout(copiedReset.current);   // a retry must not be reset by the old timer
    setCopied("busy");
    try {
      const r = await fetch(mdUrl);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await copyText(await r.text());
      setCopied("done");
    } catch {
      setCopied("failed");
    }
    copiedReset.current = window.setTimeout(() => setCopied("idle"), 2000);
  };
  return (
    <article className="detail">
      <Link to={back} className="back">← all roles</Link>
      <h1>{d.title_raw}</h1>
      <div className="sub">
        {d.company} · <span className={`badge ${d.status}`}>{d.status.replace("_", " ")}</span>
      </div>
      <div className="facts">
        <span>📍 {(d.locations || []).join(", ")}</span>
        <span>🎚️ {d.seniority_level} (r{d.seniority_rank})</span>
        {sal && <span>💷 {sal}</span>}
        {d.workplace_model && <span>🏢 {d.workplace_model}</span>}
        {d.employment_type && <span>🕒 {d.employment_type}</span>}
        {d.posted_date && <span>📅 {d.posted_date}</span>}
        {d.source_detail && <span>🔌 {d.source_detail}</span>}
      </div>
      <div className="actions">
        <a className="apply" href={d.job_ad_url} target="_blank" rel="noreferrer">
          View original ↗
        </a>
        <button disabled={copied === "busy"} onClick={copyMarkdown}
                title="Copy the role as Markdown — facts, ad text and notes">
          {copied === "done" ? "Copied ✓" : copied === "failed" ? "Copy failed" : "⧉ Copy Markdown"}
        </button>
        <a className="btn" href={`${mdUrl}?download=1`} title="Download the role as a .md file">
          ⬇ .md
        </a>
        {(applied || d.status === "open") && (
          <button
            disabled={update.isPending}
            onClick={() => update.mutate({ status: applied ? "open" : "applied" })}
          >
            {applied ? "Unmark applied" : "✓ Mark applied"}
          </button>
        )}
      </div>
      <section className="ad">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{d.ad_markdown}</ReactMarkdown>
      </section>
      <NotesSection key={d.notes ?? ""} notes={d.notes ?? ""} saving={update.isPending}
                    onSave={(notes) => update.mutate({ notes })} />
    </article>
  );
}

function NotesSection({ notes, saving, onSave }: {
  notes: string; saving: boolean; onSave: (notes: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(notes);
  return (
    <section className="notes">
      <h2>
        My notes{" "}
        {!editing && (
          <button className="small" onClick={() => { setDraft(notes); setEditing(true); }}>
            {notes ? "Edit" : "+ Add"}
          </button>
        )}
      </h2>
      {editing ? (
        <>
          <textarea
            autoFocus
            value={draft}
            rows={Math.max(4, draft.split("\n").length + 1)}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Markdown supported. Never overwritten by scans."
          />
          <div className="filters" style={{ marginTop: 8 }}>
            <button disabled={saving}
                    onClick={() => { onSave(draft); setEditing(false); }}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </>
      ) : notes ? (
        <ReactMarkdown>{notes}</ReactMarkdown>
      ) : (
        <p className="muted">No notes yet.</p>
      )}
    </section>
  );
}
