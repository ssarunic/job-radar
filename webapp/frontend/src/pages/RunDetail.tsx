import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { fmtRunTs } from "./Activity";

const GROUPS: [string, string][] = [
  ["added", "Added"],
  ["reopened", "Reopened"],
  ["updated", "Updated"],
  ["suspected_filled", "Suspected filled"],
  ["closed", "Closed"],
];

export default function RunDetail() {
  const { ts } = useParams();
  const run = useQuery({ queryKey: ["runs", ts], queryFn: () => api(`/runs/${ts}`) });

  if (run.isLoading) return <p className="muted">Loading…</p>;
  if (run.isError || !run.data)
    return <p className="muted">Not found. <Link to="/activity">← activity</Link></p>;

  const changes: any[] = run.data.changes;

  return (
    <div className="page">
      <Link to="/activity" className="back">← activity</Link>
      <div className="company-head">
        <h1>{ts ? fmtRunTs(ts) : "Run"}</h1>
      </div>

      {GROUPS.map(([key, label]) => {
        const items = changes.filter((c) => c.change === key);
        if (!items.length) return null;
        return (
          <div key={key}>
            <p className="muted" style={{ margin: "12px 4px 4px" }}>
              <span className={`badge ${key}`}>{label}</span> ({items.length})
            </p>
            <div className="list">
              {items.map((c, i) => {
                const body = (
                  <>
                    <div className="row-main">
                      <span className="company">{c.company}</span>
                      <span className="title">{c.title}</span>
                    </div>
                    <div className="row-meta">
                      {c.location && <span className="loc">{c.location}</span>}
                      {c.url && (
                        <a href={c.url} target="_blank" rel="noreferrer">posting ↗</a>
                      )}
                    </div>
                  </>
                );
                return c.id ? (
                  <Link key={i} to={`/jobs/${c.id}`} className="row clickable">{body}</Link>
                ) : (
                  <div key={i} className="row">{body}</div>
                );
              })}
            </div>
          </div>
        );
      })}

      {changes.length === 0 && <p className="muted empty">No changes in this run.</p>}
    </div>
  );
}
