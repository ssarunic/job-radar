import { useEffect, useState } from "react";
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
  const [active, setActive] = useState(false);
  const [msg, setMsg] = useState("");

  // Poll seek status only while a refresh is in flight.
  const status = useQuery({
    queryKey: ["seek"],
    queryFn: () => api("/seek"),
    enabled: active,
    refetchInterval: active ? 2000 : false,
  });

  const start = useMutation({
    mutationFn: () => apiSend("/seek", "POST"),
    onSuccess: () => { setMsg(""); setActive(true); },
    onError: () => setActive(true),   // already running (409) → just track it to completion
  });

  useEffect(() => {
    if (active && status.data && status.data.running === false) {
      setActive(false);
      ["jobs", "stats", "companies", "runs"].forEach((k) =>
        qc.invalidateQueries({ queryKey: [k] }));
      if (status.data.error) setMsg("refresh failed");
      else if (typeof status.data.added === "number")
        setMsg(status.data.added > 0 ? `+${status.data.added} new` : "up to date");
    }
  }, [active, status.data, qc]);

  const running = active || status.data?.running;
  return (
    <span className="refresh">
      {msg && !running && <span className="muted refresh-msg">{msg}</span>}
      <button onClick={() => start.mutate()} disabled={running}>
        {running ? "Refreshing…" : "↻ Refresh"}
      </button>
    </span>
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
