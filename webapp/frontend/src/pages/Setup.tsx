import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiSend } from "../api";

type Profile = {
  search_label?: string;
  seniority_min?: number;
  allow_remote?: boolean;
  location?: { home_city?: string; home_terms?: string[]; remote_regions?: string[] };
};

// First-run wizard: writes the editable subset of search_profile.yaml via
// PUT /api/profile. Deliberately small — advanced fields (custom_patterns,
// operational knobs) stay file-edited (docs/configuration.md).
export default function Setup() {
  const current = useQuery({ queryKey: ["profile"], queryFn: () => api("/profile") });
  if (current.isLoading) return <p className="muted">Loading…</p>;
  return <SetupForm profile={current.data?.profile ?? {}} />;
}

function SetupForm({ profile }: { profile: Profile }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const loc = profile.location ?? {};

  const [label, setLabel] = useState(profile.search_label ?? "");
  const [seniorityMin, setSeniorityMin] = useState(String(profile.seniority_min ?? 3));
  const [homeCity, setHomeCity] = useState(loc.home_city ?? "London");
  const [homeTerms, setHomeTerms] = useState(
    (loc.home_terms ?? ["london", "united kingdom", "uk"]).join(", "),
  );
  const [allowRemote, setAllowRemote] = useState(profile.allow_remote ?? true);
  const [remoteRegions, setRemoteRegions] = useState(
    (loc.remote_regions ?? ["uk", "europe", "emea"]).join(", "),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const splitTerms = (s: string) =>
    s.split(",").map((t) => t.trim()).filter(Boolean);

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await apiSend("/profile", "PUT", {
        search_label: label.trim() || undefined,
        seniority_min: Number(seniorityMin),
        allow_remote: allowRemote,
        home_city: homeCity.trim() || undefined,
        home_terms: splitTerms(homeTerms),
        remote_regions: splitTerms(remoteRegions),
      });
      qc.invalidateQueries({ queryKey: ["profile"] });
      navigate("/companies");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page" style={{ maxWidth: 560 }}>
      <h2>Set up your search</h2>
      <p className="muted">
        Four questions; you can change any of this later by editing{" "}
        <code>config/search_profile.yaml</code> or revisiting this page.
      </p>

      <label className="field">
        What are you searching for? <span className="muted">(label used in notifications)</span>
        <input value={label} placeholder="e.g. senior PM, design leadership"
               onChange={(e) => setLabel(e.target.value)} />
      </label>

      <label className="field">
        Minimum seniority to keep
        <select value={seniorityMin} onChange={(e) => setSeniorityMin(e.target.value)}>
          <option value="7">Director and above</option>
          <option value="6">Head and above</option>
          <option value="5">Principal / Staff and above</option>
          <option value="4">Group / Lead and above</option>
          <option value="3">Senior and above (default)</option>
          <option value="2">Everything, including mid-level</option>
        </select>
      </label>

      <label className="field">
        Home city
        <input value={homeCity} onChange={(e) => setHomeCity(e.target.value)} />
      </label>

      <label className="field">
        Locations you accept <span className="muted">(comma-separated)</span>
        <input value={homeTerms} onChange={(e) => setHomeTerms(e.target.value)} />
      </label>

      <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <input type="checkbox" checked={allowRemote}
               onChange={(e) => setAllowRemote(e.target.checked)} style={{ width: "auto" }} />
        Include remote roles
      </label>

      {allowRemote && (
        <label className="field">
          Remote regions that include you <span className="muted">(comma-separated)</span>
          <input value={remoteRegions} onChange={(e) => setRemoteRegions(e.target.value)} />
        </label>
      )}

      {error && <p className="error">{error}</p>}
      <div className="filters" style={{ marginTop: 12 }}>
        <button onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save & pick companies"}
        </button>
      </div>
    </div>
  );
}
