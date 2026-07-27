import Icon, { type IconName } from "../components/Icon";

// Living style guide (dev-facing, not in the nav — /styleguide). Every sample
// uses the app's real classes and reads token values from the stylesheet at
// render time, so this page cannot drift from the UI. Written spec:
// specs/design-system.md.

const TOKENS = ["bg", "panel", "line", "text", "muted", "accent",
  "open", "applied", "rejected", "suspected", "closed"] as const;
const ICONS: IconName[] = ["copy", "download", "check", "x", "external-link", "refresh"];
const BADGES = ["open", "applied", "rejected", "suspected_filled", "closed",
  "added", "reopened", "updated"];

export default function StyleGuide() {
  const css = getComputedStyle(document.documentElement);
  return (
    <div className="sg">
      <h1>Style guide</h1>
      <p className="muted">
        Rendered from the live stylesheet — see <code>specs/design-system.md</code> for
        the rules. New UI must be composed from what's on this page.
      </p>

      <h2>Colour tokens</h2>
      <div className="sg-row">
        {TOKENS.map((t) => (
          <div className="sg-swatch" key={t}>
            <div className="sg-chip" style={{ background: `var(--${t})` }} />
            <div className="sg-name">--{t}<br />{css.getPropertyValue(`--${t}`).trim()}</div>
          </div>
        ))}
      </div>

      <h2>Typography</h2>
      <div className="detail"><h1>Page title — 24px</h1></div>
      <div className="ad"><h2>Section heading — 17px</h2></div>
      <p>Body — 15px/1.5 system stack.</p>
      <p className="muted" style={{ fontSize: 14 }}>Secondary / labels — 14px muted.</p>
      <div className="row-meta"><span>Metadata line — 13px muted</span><span className="salary">salary green</span></div>
      <p className="error">Inline error — 15px.</p>

      <h2>Buttons & links</h2>
      <div className="actions">
        <a className="apply" href="#0">Primary action <Icon name="external-link" size={14} /></a>
        <button><Icon name="copy" /> Neutral with icon</button>
        <button>Neutral</button>
        <button disabled>Disabled</button>
        <a className="btn" href="#0"><Icon name="download" /> Link as button</a>
      </div>
      <p>Inline heading button <button className="small">Edit</button> — 12px <code>button.small</code>.</p>

      <h2>Icons — 16px Lucide outlines, currentColor (emoji only for data labels)</h2>
      <div className="sg-row">
        {ICONS.map((n) => (
          <span className="sg-icon" key={n}><Icon name={n} /> <span className="sg-name">{n}</span></span>
        ))}
      </div>

      <h2>Badges & pills</h2>
      <div className="sg-row">
        {BADGES.map((b) => <span key={b} className={`badge ${b}`}>{b.replace("_", " ")}</span>)}
        <span className="pill">neutral pill</span>
      </div>

      <h2>Inputs</h2>
      <div className="filters">
        <select><option>Select</option></select>
        <input placeholder="Text input (flexes)" />
      </div>
      <div className="field">
        Field label
        <input placeholder="Wizard field" />
      </div>
      <div className="notes"><textarea rows={2} placeholder="Textarea" /></div>

      <h2>List row</h2>
      <a className="row" href="#0">
        <div className="row-main">
          <span className="company">Company</span>
          <span className="title">Role title</span>
          <span className="badge open">open</span>
        </div>
        <div className="row-meta">
          <span>📍 London</span><span>🎚️ Head (r6)</span>
          <span className="salary">💷 GBP 140,000–170,000</span>
        </div>
      </a>

      <h2>Facts strip (emoji as data labels)</h2>
      <div className="facts">
        <span>📍 London</span><span>🎚️ Head (r6)</span><span>🏢 Hybrid</span>
        <span>🕒 Full time</span><span>📅 2026-06-10</span>
      </div>

      <h2>Banner</h2>
      <div className="banner">A banner message with a <a className="ats-link" href="#0">link</a>.</div>
    </div>
  );
}
