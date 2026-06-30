import { Routes, Route, Link, NavLink } from "react-router-dom";
import JobsList from "./pages/JobsList";
import JobDetail from "./pages/JobDetail";
import Companies from "./pages/Companies";
import CompanyDetail from "./pages/CompanyDetail";

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
          <Route path="/companies/:slug" element={<CompanyDetail />} />
        </Routes>
      </main>
    </div>
  );
}
