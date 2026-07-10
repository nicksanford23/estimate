// Human-readable display names for permits, derived from estimate.permits
// (address + description). In-process cache — the permits table is
// static-ish, no TTL/invalidation needed for an ops dashboard.
import { q } from "./db";

const cache = new Map<string, string>();

function truncate(s: string, max: number): string {
  const t = s.trim();
  if (t.length <= max) return t;
  return t.slice(0, max - 1).trimEnd() + "…";
}

function format(permitNum: string, address: string | null, description: string | null): string {
  const addr = (address ?? "").trim();
  const desc = truncate((description ?? "").trim(), 60);
  if (addr && desc) return `${addr} — ${desc}`;
  if (addr) return addr;
  if (desc) return desc;
  return permitNum;
}

export async function getPermitDisplayNames(permitNums: string[]): Promise<Map<string, string>> {
  const out = new Map<string, string>();
  const missing: string[] = [];
  for (const p of permitNums) {
    const hit = cache.get(p);
    if (hit != null) out.set(p, hit);
    else missing.push(p);
  }
  if (missing.length) {
    const rows = await q<{ permit_num: string; address: string | null; description: string | null }>(
      `SELECT permit_num, address, description FROM estimate.permits WHERE permit_num = ANY($1)`,
      [missing]
    );
    const byPermit = new Map(rows.map((r) => [r.permit_num, r]));
    for (const p of missing) {
      const r = byPermit.get(p);
      const name = format(p, r?.address ?? null, r?.description ?? null);
      cache.set(p, name);
      out.set(p, name);
    }
  }
  return out;
}

export async function getPermitDisplayName(permitNum: string): Promise<string> {
  const m = await getPermitDisplayNames([permitNum]);
  return m.get(permitNum) ?? permitNum;
}
