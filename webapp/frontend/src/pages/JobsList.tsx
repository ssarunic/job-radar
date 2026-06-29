import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, RANK_LABEL, fmtSalary } from "../api";

export default function JobsList() {
  const [status, setStatus] = useState("open");
  const [minRank, setMinRank] = useState(0);
  const [q, setQ] = useState("");

  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api("/stats") });

  const params = new URLSearchParams({ status, sort: "seniority" });
  if (minRank) params.set("min_rank", String(minRank));
  if (q) params.set("q", q);
  const jobs = useQuery({
    queryKey: ["jobs", status, minRank, q],
    queryFn: () => api(`/jobs?${params.toString()}`),
  });

  return (
    <div className="page">
      <div className="stats">
        {stats.data && (
          <>
            <b>{stats.data.open}</b> open · {stats.data.new_7d} new (7d) ·{" "}
            {stats.data.companies} companies
            {stats.data.last_run && <span className="muted"> · last run {stats.data.last_run}</span>}
          </>
        )}
      </div>

      <div className="filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="open">Open</option>
          <option value="applied">Applied</option>
          <option value="suspected_filled">Suspected filled</option>
          <option value="closed">Closed</option>
          <option value="all">All</option>
        </select>
        <select value={minRank} onChange={(e) => setMinRank(Number(e.target.value))}>
          <option value={0}>Any seniority</option>
          <option value={3}>Senior+</option>
          <option value={5}>Principal+</option>
          <option value={6}>Head+</option>
          <option value={7}>Director+</option>
        </select>
        <input
          placeholder="Search company or title…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {jobs.isLoading && <p className="muted">Loading…</p>}
      {jobs.data && (
        <div className="list">
          {jobs.data.jobs.map((j: any) => (
            <Link key={j.id} to={`/jobs/${j.id}`} className="row">
              <div className="row-main">
                <span className="company">{j.company}</span>
                <span className="title">{j.title_raw}</span>
              </div>
              <div className="row-meta">
                <span className="pill">{RANK_LABEL[j.seniority_rank] || j.seniority_level}</span>
                <span className="loc">{(j.locations || []).join(", ")}</span>
                {fmtSalary(j.salary) && <span className="salary">{fmtSalary(j.salary)}</span>}
                <span className={`badge ${j.status}`}>{j.status.replace("_", " ")}</span>
                <span className="muted date">{j.first_seen}</span>
              </div>
            </Link>
          ))}
          {jobs.data.count === 0 && <p className="muted empty">No roles match.</p>}
        </div>
      )}
    </div>
  );
}
