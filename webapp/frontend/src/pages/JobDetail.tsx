import { useEffect } from "react";
import { useParams, useLocation, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, fmtSalary } from "../api";

export default function JobDetail() {
  const { id } = useParams();
  // The list passes its filter query via link state; back returns to that exact view.
  // Deep links (Slack, MCP) carry no state -> plain unfiltered list.
  const fromSearch = (useLocation().state as { fromSearch?: string } | null)?.fromSearch ?? "";
  const back = { pathname: "/", search: fromSearch };
  const { data, isLoading, isError } = useQuery({
    queryKey: ["job", id],
    queryFn: () => api(`/jobs/${id}`),
  });

  useEffect(() => window.scrollTo(0, 0), []);   // don't inherit the list's scroll offset

  if (isLoading) return <p className="muted">Loading…</p>;
  if (isError || !data) return <p className="muted">Not found. <Link to={back}>← all roles</Link></p>;

  const d: any = data;
  const sal = fmtSalary(d.salary);
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
      <a className="apply" href={d.job_ad_url} target="_blank" rel="noreferrer">
        View original ↗
      </a>
      <section className="ad">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{d.ad_markdown}</ReactMarkdown>
      </section>
      {d.notes && (
        <section className="notes">
          <h2>My notes</h2>
          <ReactMarkdown>{d.notes}</ReactMarkdown>
        </section>
      )}
    </article>
  );
}
