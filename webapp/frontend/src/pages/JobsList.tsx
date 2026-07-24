import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { api, RANK_LABEL, fmtSalary } from "../api";
import { useScrollRestore } from "../hooks";

// Filters live in the URL (not useState) so the exact list survives navigating to a
// job and back, browser back/forward, and reload — and filtered views are shareable.
// Param names match the API's. Defaults are omitted to keep "/" clean.
const DEFAULTS: Record<string, string> = { status: "open", min_rank: "0", sort: "seniority", q: "" };

export default function JobsList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();

  const status = searchParams.get("status") ?? DEFAULTS.status;
  const minRank = Number(searchParams.get("min_rank") ?? DEFAULTS.min_rank);
  const sort = searchParams.get("sort") ?? DEFAULTS.sort;
  const q = searchParams.get("q") ?? DEFAULTS.q;

  const setFilter = (name: string, value: string) =>
    setSearchParams(
      (prev) => {
        if (value === DEFAULTS[name]) prev.delete(name);
        else prev.set(name, value);
        return prev;
      },
      { replace: true },   // filter tweaks (incl. every keystroke) don't pollute history
    );

  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api("/stats") });
  const profile = useQuery({ queryKey: ["profile"], queryFn: () => api("/profile") });
  const firstRun = profile.data?.companies_followed === 0;

  const params = new URLSearchParams({ status, sort });
  if (minRank) params.set("min_rank", String(minRank));
  if (q) params.set("q", q);
  const jobs = useQuery({
    queryKey: ["jobs", status, minRank, sort, q],
    queryFn: () => api(`/jobs?${params.toString()}`),
  });

  useScrollRestore(location.search, !!jobs.data);

  return (
    <div className="page">
      {firstRun && (
        <div className="banner">
          Welcome! <Link to="/setup">Set up your search</Link> (what roles,
          where), then follow your first companies — roles will appear here.
        </div>
      )}
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
        <select value={status} onChange={(e) => setFilter("status", e.target.value)}>
          <option value="open">Open</option>
          <option value="applied">Applied</option>
          <option value="suspected_filled">Suspected filled</option>
          <option value="closed">Closed</option>
          <option value="all">All</option>
        </select>
        <select value={minRank} onChange={(e) => setFilter("min_rank", e.target.value)}>
          <option value={0}>Any seniority</option>
          <option value={3}>Senior+</option>
          <option value={5}>Principal+</option>
          <option value={6}>Head+</option>
          <option value={7}>Director+</option>
        </select>
        <select value={sort} onChange={(e) => setFilter("sort", e.target.value)}>
          <option value="seniority">Sort: Seniority</option>
          <option value="recent">Sort: Most recent</option>
        </select>
        <input
          placeholder="Search company or title…"
          value={q}
          onChange={(e) => setFilter("q", e.target.value)}
        />
      </div>

      {jobs.isLoading && <p className="muted">Loading…</p>}
      {jobs.data && (
        <div className="list">
          {jobs.data.jobs.map((j: any) => (
            <Link
              key={j.id}
              to={`/jobs/${j.id}`}
              state={{ fromSearch: location.search }}   // detail's back link returns here
              className="row"
            >
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
