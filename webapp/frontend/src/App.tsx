import { useEffect, useRef } from "react";
import { Routes, Route, Link, NavLink } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiSend } from "./api";
import JobsList from "./pages/JobsList";
import JobDetail from "./pages/JobDetail";
import Companies from "./pages/Companies";
import CompanyDetail from "./pages/CompanyDetail";
import Activity from "./pages/Activity";
import RunDetail from "./pages/RunDetail";

function RefreshButton() {
  const qc = useQueryClient();

  // One always-on query; it self-polls only while a seek is running (derived state,
  // no setState-in-effect). A POST kicks it off; the interval stops itself at done.
  const status = useQuery({
    queryKey: ["seek"],
    queryFn: () => api("/seek"),
    refetchInterval: (q) => (q.state.data?.running ? 1500 : false),
  });
  const running = !!status.data?.running;

  const start = useMutation({
    mutationFn: () => apiSend("/seek", "POST"),
    onSettled: () => status.refetch(),   // success → start polling; 409 → just sync state
  });

  // On the running→done transition, refresh the lists so they reflect the new data.
  // Only invalidateQueries here (no setState) — keeps react-hooks/set-state-in-effect happy.
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !running) {
      ["jobs", "stats", "companies", "runs"].forEach((k) =>
        qc.invalidateQueries({ queryKey: [k] }));
    }
    wasRunning.current = running;
  }, [running, qc]);

  const total = status.data?.total ?? 0;
  const done = status.data?.done ?? 0;
  const current = status.data?.current as string | undefined;
  const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 8; // 8% = indeterminate
  const msg = running
    ? ""
    : status.data?.error
      ? "refresh failed"
      : typeof status.data?.added === "number"
        ? status.data.added > 0 ? `+${status.data.added} new` : "up to date"
        : "";

  return (
    <>
      <span className="refresh">
        {running && (
          <span className="muted refresh-msg">
            {current ? `Scanning ${current}…` : "Starting…"}
            {total ? ` ${done}/${total}` : ""}
          </span>
        )}
        {msg && !running && <span className="muted refresh-msg">{msg}</span>}
        <button onClick={() => start.mutate()} disabled={running}>
          {running ? "Refreshing…" : "↻ Refresh"}
        </button>
      </span>
      {running && (
        <div className="topbar-progress" style={{ width: `${pct}%` }} aria-hidden />
      )}
    </>
  );
}

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">🛰️ Job Radar</Link>
        <nav className="topnav">
          <NavLink to="/" end>Roles</NavLink>
          <NavLink to="/companies">Companies</NavLink>
          <NavLink to="/activity">Activity</NavLink>
        </nav>
        <RefreshButton />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<JobsList />} />
          <Route path="/jobs/:id" element={<JobDetail />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/companies/:slug" element={<CompanyDetail />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/activity/:ts" element={<RunDetail />} />
        </Routes>
      </main>
    </div>
  );
}
