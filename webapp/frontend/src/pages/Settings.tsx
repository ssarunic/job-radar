import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiSend } from "../api";

type Profile = {
  search_label?: string;
  seniority_min?: number;
  include_product_owner?: boolean;
  include_ai_innovation?: boolean;
  exclude_titles?: string[];
  employment?: string[];
  recency_days?: number;
  max_roles_per_company?: number;
  custom_patterns?: unknown[];
};
// Geography as it applies (profile value, else the built-in default) — from the API,
// so this page never carries its own copy of the defaults.
type Geo = { home_city: string; home_terms: string[]; remote_regions: string[]; workplace: string[] };
type Data = { profile: Profile; location: Geo; companies_followed: number };

const SENIORITY: [number, string][] = [
  [9, "C-level only"],
  [8, "VP and above"],
  [7, "Director and above"],
  [6, "Head and above"],
  [5, "Principal / Staff and above"],
  [4, "Group / Lead and above"],
  [3, "Senior and above (default)"],
  [2, "Everything, including mid-level"],
];

const EMPLOYMENT = ["Full time", "Part time", "Contract"];
const EMPLOYMENT_HINT: Record<string, string> = {
  Contract: "fixed-term, interim, temporary, freelance",
};
const WORKPLACE = ["On site", "Hybrid", "Remote"];
const toggle = (list: string[], item: string, on: boolean) =>
  on ? [...list, item] : list.filter((x) => x !== item);

const showTerms = (terms: string[]) => terms.map((t) => t.trim()).join(", ");
// Comma-separated input -> terms. A term the user didn't retype keeps its stored
// form: some defaults carry significant whitespace ("eu " must not match "europe").
const splitTerms = (s: string, original: string[]) =>
  s.split(",").map((t) => t.trim()).filter(Boolean)
    .map((t) => original.find((o) => o.trim() === t) ?? t);
const sameTerms = (a: string[], b: string[]) => a.join("\n") === b.join("\n");

// Search settings: the editable subset of search_profile.yaml (PUT /api/profile).
// Read-only by default — these rules drive the daily scan, so changing them is a
// deliberate Edit → Save. `firstRun` (the /setup route) opens straight into the
// form and continues to Companies. Advanced fields (custom_patterns, operational
// knobs) are shown but stay file-edited (docs/configuration.md).
export default function Settings({ firstRun = false }: { firstRun?: boolean }) {
  const current = useQuery({ queryKey: ["profile"], queryFn: () => api("/profile") });
  const [editing, setEditing] = useState(firstRun);
  const navigate = useNavigate();

  if (current.isLoading) return <p className="muted">Loading…</p>;
  if (!current.data) return <p className="error">Couldn’t load settings.</p>;
  const data = current.data as Data;

  return (
    <div className="page settings">
      <div className="settings-head">
        <h2>{firstRun ? "Set up your search" : "Settings"}</h2>
        {!editing && <button onClick={() => setEditing(true)}>Edit</button>}
      </div>
      {editing ? (
        <SettingsForm
          data={data}
          saveLabel={firstRun ? "Save & pick companies" : "Save"}
          onDone={() => (firstRun ? navigate("/companies") : setEditing(false))}
          onCancel={firstRun ? undefined : () => setEditing(false)}
        />
      ) : (
        <SettingsView data={data} />
      )}
    </div>
  );
}

function Terms({ terms }: { terms: string[] }) {
  if (terms.length === 0) return <span className="muted">None</span>;
  return (
    <span className="pills">
      {terms.map((t) => <span className="pill" key={t}>{t.trim()}</span>)}
    </span>
  );
}

function SettingsView({ data }: { data: Data }) {
  const { profile, location } = data;
  const rank = profile.seniority_min ?? 3;
  const custom = (profile.custom_patterns ?? []).length;
  const yesNo = (v: boolean) => (v ? "Included" : "Not included");

  return (
    <>
      <section className="settings-card">
        <h3>Roles</h3>
        <dl className="kv">
          <dt>Searching for</dt>
          <dd>{profile.search_label || <span className="muted">Not set</span>}</dd>
          <dt>Minimum seniority</dt>
          <dd>{SENIORITY.find(([r]) => r === rank)?.[1] ?? `Rank ${rank} and above`}</dd>
          {custom > 0 ? (
            <>
              <dt>Title patterns</dt>
              <dd>
                {custom} custom {custom === 1 ? "pattern replaces" : "patterns replace"} the
                built-in product ladder <span className="muted">(set in the file)</span>
              </dd>
            </>
          ) : (
            <>
              <dt>Product Owner roles</dt>
              <dd>{yesNo(profile.include_product_owner ?? true)}</dd>
              <dt>AI / Innovation leadership</dt>
              <dd>{yesNo(profile.include_ai_innovation ?? true)}</dd>
            </>
          )}
          <dt>Excluded title words</dt>
          <dd><Terms terms={profile.exclude_titles ?? []} /></dd>
          <dt>Employment types</dt>
          <dd><Terms terms={profile.employment ?? ["Full time", "Part time"]} /></dd>
        </dl>
      </section>

      <section className="settings-card">
        <h3>Locations</h3>
        <dl className="kv">
          <dt>Home city</dt>
          <dd style={{ textTransform: "capitalize" }}>{location.home_city}</dd>
          <dt>Accepted locations</dt>
          <dd><Terms terms={location.home_terms} /></dd>
          <dt>Work types</dt>
          <dd>
            <Terms terms={location.workplace} />{" "}
            <span className="muted">(roles that don’t say are always kept)</span>
          </dd>
          <dt>Remote roles</dt>
          <dd>
            {location.workplace.includes("Remote")
              ? <>Included when open to <Terms terms={location.remote_regions} /></>
              : "Not included"}
          </dd>
        </dl>
      </section>

      <section className="settings-card">
        <h3>Companies</h3>
        <dl className="kv">
          <dt>Following</dt>
          <dd>
            {data.companies_followed}{" "}
            {data.companies_followed === 1 ? "company" : "companies"} ·{" "}
            <Link to="/companies?show=all" className="link">Manage companies</Link>
          </dd>
          <dt>Roles kept per company</dt>
          <dd>Top {profile.max_roles_per_company ?? 10} most senior</dd>
          <dt>Posting age limit</dt>
          <dd>{profile.recency_days ?? 45} days</dd>
        </dl>
      </section>

      <p className="muted settings-note">
        Changes apply from the next scan. The per-company cap and the age limit are
        changed in <code>config/search_profile.yaml</code>.
      </p>
    </>
  );
}

function SettingsForm({ data, saveLabel, onDone, onCancel }: {
  data: Data;
  saveLabel: string;
  onDone: () => void;
  onCancel?: () => void;
}) {
  const qc = useQueryClient();
  const { profile, location } = data;
  const custom = (profile.custom_patterns ?? []).length > 0;
  const cur = {
    label: profile.search_label ?? "",
    seniorityMin: profile.seniority_min ?? 3,
    includePO: profile.include_product_owner ?? true,
    includeAI: profile.include_ai_innovation ?? true,
    excludeTitles: profile.exclude_titles ?? [],
    employment: profile.employment ?? ["Full time", "Part time"],
  };

  const [label, setLabel] = useState(cur.label);
  const [seniorityMin, setSeniorityMin] = useState(String(cur.seniorityMin));
  const [includePO, setIncludePO] = useState(cur.includePO);
  const [includeAI, setIncludeAI] = useState(cur.includeAI);
  const [excludeTitles, setExcludeTitles] = useState(showTerms(cur.excludeTitles));
  const [homeCity, setHomeCity] = useState(location.home_city);
  const [homeTerms, setHomeTerms] = useState(showTerms(location.home_terms));
  const [employment, setEmployment] = useState(cur.employment);
  const [workplace, setWorkplace] = useState(location.workplace);
  const allowRemote = workplace.includes("Remote");
  const [remoteRegions, setRemoteRegions] = useState(showTerms(location.remote_regions));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    // Send only what changed: untouched fields keep following the defaults, and
    // an unchanged form doesn't rewrite the profile file at all.
    const body: Record<string, unknown> = {};
    if (label.trim() && label.trim() !== cur.label) body.search_label = label.trim();
    if (Number(seniorityMin) !== cur.seniorityMin) body.seniority_min = Number(seniorityMin);
    if (includePO !== cur.includePO) body.include_product_owner = includePO;
    if (includeAI !== cur.includeAI) body.include_ai_innovation = includeAI;
    const emp = EMPLOYMENT.filter((t) => employment.includes(t));
    if (!sameTerms(emp, EMPLOYMENT.filter((t) => cur.employment.includes(t)))) body.employment = emp;
    const work = WORKPLACE.filter((t) => workplace.includes(t));
    if (!sameTerms(work, location.workplace)) body.workplace = work;
    const excl = splitTerms(excludeTitles, cur.excludeTitles);
    if (!sameTerms(excl, cur.excludeTitles)) body.exclude_titles = excl;
    if (homeCity.trim() && homeCity.trim() !== location.home_city) body.home_city = homeCity.trim();
    const home = splitTerms(homeTerms, location.home_terms);
    if (!sameTerms(home, location.home_terms)) body.home_terms = home;
    const regions = splitTerms(remoteRegions, location.remote_regions);
    if (!sameTerms(regions, location.remote_regions)) body.remote_regions = regions;

    if (home.length === 0) {
      setError("Add at least one accepted location.");
      return;
    }
    if (emp.length === 0 || work.length === 0) {
      setError(`Pick at least one ${emp.length === 0 ? "employment type" : "work type"}.`);
      return;
    }
    if (Object.keys(body).length === 0) {
      onDone();
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiSend("/profile", "PUT", body);
      await qc.invalidateQueries({ queryKey: ["profile"] });
      onDone();
    } catch (e) {
      setError((e as Error).message);
      setSaving(false);
    }
  };

  const checkRow = { flexDirection: "row", alignItems: "center", gap: 8 } as const;

  return (
    <>
      <section className="settings-card">
        <h3>Roles</h3>
        <label className="field">
          <span>What are you searching for? <span className="muted">(label used in notifications)</span></span>
          <input value={label} placeholder="e.g. senior PM, design leadership"
                 onChange={(e) => setLabel(e.target.value)} />
        </label>

        <label className="field">
          Minimum seniority to keep
          <select value={seniorityMin} onChange={(e) => setSeniorityMin(e.target.value)}>
            {SENIORITY.map(([r, text]) => <option key={r} value={r}>{text}</option>)}
          </select>
        </label>

        {!custom && (
          <>
            <label className="field" style={checkRow}>
              <input type="checkbox" checked={includePO}
                     onChange={(e) => setIncludePO(e.target.checked)} />
              <span>Include Product Owner roles <span className="muted">(even below the minimum)</span></span>
            </label>
            <label className="field" style={checkRow}>
              <input type="checkbox" checked={includeAI}
                     onChange={(e) => setIncludeAI(e.target.checked)} />
              <span>Include AI / Innovation leadership roles <span className="muted">(e.g. Head of AI)</span></span>
            </label>
          </>
        )}

        <label className="field">
          <span>Skip titles containing <span className="muted">(comma-separated)</span></span>
          <textarea rows={2} value={excludeTitles}
                    onChange={(e) => setExcludeTitles(e.target.value)} />
        </label>

        <fieldset className="field checks">
          <legend>Employment types</legend>
          {EMPLOYMENT.map((t) => (
            <label key={t} style={checkRow}>
              <input type="checkbox" checked={employment.includes(t)}
                     onChange={(e) => setEmployment(toggle(employment, t, e.target.checked))} />
              <span>{t}{EMPLOYMENT_HINT[t] && <span className="muted"> ({EMPLOYMENT_HINT[t]})</span>}</span>
            </label>
          ))}
        </fieldset>
      </section>

      <section className="settings-card">
        <h3>Locations</h3>
        <label className="field">
          Home city
          <input value={homeCity} onChange={(e) => setHomeCity(e.target.value)} />
        </label>

        <label className="field">
          <span>Locations you accept <span className="muted">(comma-separated)</span></span>
          <textarea rows={2} value={homeTerms} onChange={(e) => setHomeTerms(e.target.value)} />
        </label>

        <fieldset className="field checks">
          <legend>
            Work types <span className="muted">(roles that don’t say are always kept)</span>
          </legend>
          {WORKPLACE.map((t) => (
            <label key={t} style={checkRow}>
              <input type="checkbox" checked={workplace.includes(t)}
                     onChange={(e) => setWorkplace(toggle(workplace, t, e.target.checked))} />
              {t}
            </label>
          ))}
        </fieldset>

        {allowRemote && (
          <label className="field">
            <span>Remote regions that include you <span className="muted">(comma-separated)</span></span>
            <input value={remoteRegions} onChange={(e) => setRemoteRegions(e.target.value)} />
          </label>
        )}
      </section>

      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button className="apply" onClick={save} disabled={saving}>
          {saving ? "Saving…" : saveLabel}
        </button>
        {onCancel && <button onClick={onCancel} disabled={saving}>Cancel</button>}
      </div>
    </>
  );
}
