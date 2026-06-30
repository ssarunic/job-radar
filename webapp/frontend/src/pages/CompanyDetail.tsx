import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, apiSend, RANK_LABEL, fmtSalary } from "../api";

export default function CompanyDetail() {
  const { slug } = useParams();
  const qc = useQueryClient();
  const detail = useQuery({
    queryKey: ["company", slug],
    queryFn: () => api(`/companies/${slug}`),
  });

  const toggle = useMutation({
    mutationFn: (active: boolean) => apiSend(`/companies/${slug}`, "PATCH", { active }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["company", slug] });
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
  });

  if (detail.isLoading) return <p className="muted">Loading…</p>;
  if (detail.isError || !detail.data)
    return (
      <p className="muted">
        Not found. <Link to="/companies">← all companies</Link>
      </p>
    );

  const c = detail.data.company;
  const roles = detail.data.roles as any[];

  return (
    <div className="page">
      <Link to="/companies" className="back">← all companies</Link>

      <div className="company-head">
        <h1>{c.name}</h1>
        <div className="row-meta">
          <span className="pill">{c.ats_type}</span>
          <span className="pill">{c.open_roles} open</span>
          {!c.active && <span className="badge closed">unfollowed</span>}
          <button disabled={toggle.isPending} onClick={() => toggle.mutate(!c.active)}>
            {c.active ? "Unfollow" : "Re-follow"}
          </button>
        </div>
        {c.careers_url && (
          <a className="ats-link" href={c.careers_url} target="_blank" rel="noreferrer">
            View careers page ({c.ats_type}) ↗
          </a>
        )}
      </div>

      <div className="list">
        {roles.map((j) => (
          <Link key={j.id} to={`/jobs/${j.id}`} className="row clickable">
            <div className="row-main">
              <span className="title">{j.title_raw}</span>
            </div>
            <div className="row-meta">
              <span className="pill">{RANK_LABEL[j.seniority_rank] || j.seniority_level}</span>
              <span className="loc">{(j.locations || []).join(", ")}</span>
              {fmtSalary(j.salary) && <span className="salary">{fmtSalary(j.salary)}</span>}
              <span className="muted date">{j.first_seen}</span>
            </div>
          </Link>
        ))}
        {roles.length === 0 && (
          <p className="muted empty">
            No open roles tracked for {c.name}.
            {c.careers_url && (
              <>
                {" "}
                <a href={c.careers_url} target="_blank" rel="noreferrer">
                  Check their careers page ↗
                </a>
              </>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
