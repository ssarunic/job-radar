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

export function fmtSalary(s: any): string {
  if (!s || s.min == null) return "";
  const cur = s.currency || "";
  const n = (x: number) => x.toLocaleString();
  const range = s.min === s.max ? n(s.min) : `${n(s.min)}–${n(s.max)}`;
  return `${cur} ${range}`.trim();
}
