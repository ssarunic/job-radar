export async function api(path: string) {
  const r = await fetch(`/api${path}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// Mutating calls (POST/PATCH). On error, surfaces the FastAPI `detail` message.
export async function apiSend(path: string, method: string, body?: unknown) {
  const r = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
  return data;
}

export const RANK_LABEL: Record<number, string> = {
  9: "CPO", 8: "VP", 7: "Director", 6: "Head", 5: "Principal", 4: "Group", 3: "Senior", 2: "Mid",
};

// "2026-06-30T120000Z" -> "2026-06-30 12:00 UTC"
export function fmtRunTs(ts: string): string {
  const m = ts.match(/^(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  return m ? `${m[1]} ${m[2]}:${m[3]} UTC` : ts;
}

// "2026-06-30T120000Z" (run-dir name) -> Date, or null if unparseable
function parseRunTs(ts: string): Date | null {
  const m = ts.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]));
}

// Friendly age for a run timestamp: "just now", "35 minutes ago", "23 hours ago",
// "yesterday", "5 days ago"; older than a week falls back to the date ("12 Jul",
// plus the year when it isn't the current one). Pair with fmtRunTs in a title
// tooltip so the exact time stays one hover away.
export function fmtRunAge(ts: string): string {
  const d = parseRunTs(ts);
  if (!d) return ts;
  const mins = Math.floor((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return mins === 1 ? "1 minute ago" : `${mins} minutes ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  const opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  if (d.getFullYear() !== new Date().getFullYear()) opts.year = "numeric";
  return d.toLocaleDateString(undefined, opts);
}

export function fmtSalary(s: any): string {
  if (!s || s.min == null) return "";
  const cur = s.currency || "";
  const n = (x: number) => x.toLocaleString();
  const range = s.min === s.max ? n(s.min) : `${n(s.min)}–${n(s.max)}`;
  return `${cur} ${range}`.trim();
}
