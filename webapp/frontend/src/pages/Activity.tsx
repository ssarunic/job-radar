import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, fmtRunTs } from "../api";

const CHANGE_ORDER = ["added", "reopened", "updated", "suspected_filled", "closed"];
const CHANGE_LABEL: Record<string, string> = {
  added: "added", reopened: "reopened", updated: "updated",
  suspected_filled: "susp. filled", closed: "closed",
};

export default function Activity() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api("/runs") });

  return (
    <div className="page">
      {runs.isLoading && <p className="muted">Loading…</p>}
      {runs.data && (
        <div className="list">
          {runs.data.runs.map((r: any) => (
            <Link key={r.ts} to={`/activity/${r.ts}`} className="row clickable">
              <div className="row-main">
                <span className="company">{fmtRunTs(r.ts)}</span>
              </div>
              <div className="row-meta">
                {CHANGE_ORDER.filter((k) => r.counts[k]).map((k) => (
                  <span key={k} className={`badge ${k}`}>
                    {r.counts[k]} {CHANGE_LABEL[k]}
                  </span>
                ))}
                {r.total === 0 && <span className="muted">no changes</span>}
              </div>
            </Link>
          ))}
          {runs.data.count === 0 && <p className="muted empty">No runs yet.</p>}
        </div>
      )}
    </div>
  );
}
