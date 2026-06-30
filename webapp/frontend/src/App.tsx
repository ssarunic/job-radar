import { Routes, Route, Link, NavLink } from "react-router-dom";
import JobsList from "./pages/JobsList";
import JobDetail from "./pages/JobDetail";
import Companies from "./pages/Companies";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">🛰️ Job Radar</Link>
        <nav className="topnav">
          <NavLink to="/" end>Roles</NavLink>
          <NavLink to="/companies">Companies</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<JobsList />} />
          <Route path="/jobs/:id" element={<JobDetail />} />
          <Route path="/companies" element={<Companies />} />
        </Routes>
      </main>
    </div>
  );
}
