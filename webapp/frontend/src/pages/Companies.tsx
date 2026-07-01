import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, apiSend } from "../api";
import Modal from "../components/Modal";

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
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);

  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api("/companies") });

  const toggle = useMutation({
    mutationFn: (v: { slug: string; active: boolean }) =>
      apiSend(`/companies/${v.slug}`, "PATCH", { active: v.active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  const q = search.trim().toLowerCase();
  const rows: Company[] = (companies.data?.companies ?? []).filter(
    (c) =>
      !q ||
      c.name.toLowerCase().includes(q) ||
      (c.ats_type ?? "").toLowerCase().includes(q) ||
      c.slug.toLowerCase().includes(q),
  );
  const active = rows.filter((c) => c.active);
  const inactive = rows.filter((c) => !c.active);

  return (
    <div className="page">
      <div className="filters">
        <input
          placeholder="Search companies…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1 }}
        />
        <button onClick={() => setAdding(true)}>+ Follow</button>
      </div>

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
          {rows.length === 0 && (
            <p className="muted empty">{q ? "No companies match." : "No companies tracked yet."}</p>
          )}
        </div>
      )}

      {adding && <FollowModal onClose={() => setAdding(false)} />}
    </div>
  );
}

function FollowModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const follow = useMutation({
    mutationFn: (val: string) => apiSend("/companies", "POST", { query: val }),
    onSuccess: (data) => {
      const c = data.company;
      const found = data.scanned
        ? ` — ${c.open_roles} open role${c.open_roles === 1 ? "" : "s"} found`
        : "";
      setMsg({ kind: "ok", text: `Following ${c.name} via ${c.ats_type}${found}.` });
      setQuery("");
      qc.invalidateQueries({ queryKey: ["companies"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (e: Error) => setMsg({ kind: "err", text: e.message }),
  });

  return (
    <Modal title="Follow a company" onClose={onClose}>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) follow.mutate(query.trim());
        }}
      >
        <input
          autoFocus
          placeholder="Company name or careers URL…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={follow.isPending || !query.trim()}>
          {follow.isPending ? "Scanning…" : "Follow"}
        </button>
      </form>
      {msg && <p className={msg.kind === "ok" ? "muted" : "error"}>{msg.text}</p>}
      <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
        Name auto-detects the ATS; for Workday/Oracle/Recruitee, paste the careers URL.
      </p>
    </Modal>
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
  const navigate = useNavigate();
  return (
    <div
      className="row clickable"
      style={{ opacity: c.active ? 1 : 0.55 }}
      onClick={() => navigate(`/companies/${c.slug}`)}
    >
      <div className="row-main">
        <span className="company">{c.name}</span>
        <span className="title muted">{c.ats_type}</span>
      </div>
      <div className="row-meta">
        <span className="pill">{c.open_roles} open</span>
        <button
          disabled={busy}
          onClick={(e) => {
            e.stopPropagation();
            onToggle({ slug: c.slug, active: !c.active });
          }}
        >
          {c.active ? "Unfollow" : "Re-follow"}
        </button>
      </div>
    </div>
  );
}
