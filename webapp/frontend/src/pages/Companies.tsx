import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiSend } from "../api";

type Company = {
  name: string;
  slug: string;
  ats_type: string | null;
  ats_slug: string | null;
  careers_url: string | null;
  active: boolean;
  open_roles: number;
};

export default function Companies() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api("/companies") });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["companies"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  };

  const follow = useMutation({
    mutationFn: (q: string) => apiSend("/companies", "POST", { query: q }),
    onSuccess: (data) => {
      const c = data.company;
      const found = data.scanned
        ? ` — ${c.open_roles} open role${c.open_roles === 1 ? "" : "s"} found`
        : "";
      setMsg({ kind: "ok", text: `Following ${c.name} via ${c.ats_type}${found}.` });
      setQuery("");
      refresh();
    },
    onError: (e: Error) => setMsg({ kind: "err", text: e.message }),
  });

  const toggle = useMutation({
    mutationFn: (v: { slug: string; active: boolean }) =>
      apiSend(`/companies/${v.slug}`, "PATCH", { active: v.active }),
    onSuccess: () => refresh(),
    onError: (e: Error) => setMsg({ kind: "err", text: e.message }),
  });

  const rows: Company[] = companies.data?.companies ?? [];
  const active = rows.filter((c) => c.active);
  const inactive = rows.filter((c) => !c.active);

  return (
    <div className="page">
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) follow.mutate(query.trim());
        }}
      >
        <input
          placeholder="Add a company — name or careers URL…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={follow.isPending || !query.trim()}>
          {follow.isPending ? "Scanning…" : "Follow"}
        </button>
      </form>

      {msg && <p className={msg.kind === "ok" ? "muted" : "error"}>{msg.text}</p>}

      {companies.isLoading && <p className="muted">Loading…</p>}
      {companies.data && (
        <div className="list">
          {active.map((c) => (
            <CompanyRow key={c.slug} c={c} onToggle={toggle.mutate} busy={toggle.isPending} />
          ))}
          {inactive.length > 0 && (
            <p className="muted" style={{ margin: "12px 4px 4px" }}>
              Unfollowed ({inactive.length})
            </p>
          )}
          {inactive.map((c) => (
            <CompanyRow key={c.slug} c={c} onToggle={toggle.mutate} busy={toggle.isPending} />
          ))}
          {rows.length === 0 && <p className="muted empty">No companies tracked yet.</p>}
        </div>
      )}
    </div>
  );
}

function CompanyRow({
  c,
  onToggle,
  busy,
}: {
  c: Company;
  onToggle: (v: { slug: string; active: boolean }) => void;
  busy: boolean;
}) {
  return (
    <div className="row" style={{ opacity: c.active ? 1 : 0.55 }}>
      <div className="row-main">
        <span className="company">{c.name}</span>
        {c.careers_url ? (
          <a className="title" href={c.careers_url} target="_blank" rel="noreferrer">
            {c.ats_type}
          </a>
        ) : (
          <span className="title">{c.ats_type}</span>
        )}
      </div>
      <div className="row-meta">
        <span className="pill">{c.open_roles} open</span>
        <button
          disabled={busy}
          onClick={() => onToggle({ slug: c.slug, active: !c.active })}
        >
          {c.active ? "Unfollow" : "Re-follow"}
        </button>
      </div>
    </div>
  );
}
