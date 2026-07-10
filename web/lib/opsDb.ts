import { q } from "./db";

export type DiscoveryProgress = {
  discoveredPermits: number;
  latestRun: {
    run_id: number;
    pod_id: string;
    started_at: string;
    ended_at: string | null;
    final_state: string;
    settled: number | null;
    docs: number | null;
    note: string | null;
  } | null;
};

// estimate.discovered_docs / estimate.discovery_runs — the one-time full
// enumeration crawl (SELECT only, per CLAUDE.md).
export async function getDiscoveryProgress(): Promise<DiscoveryProgress> {
  const [{ n }] = await q<{ n: number }>(
    `SELECT COUNT(DISTINCT permit_num)::int n FROM estimate.discovered_docs`
  );
  const runs = await q<DiscoveryProgress["latestRun"] & Record<string, unknown>>(
    `SELECT run_id, pod_id, started_at::text, ended_at::text, final_state, settled, docs, note
     FROM estimate.discovery_runs ORDER BY run_id DESC LIMIT 1`
  );
  return { discoveredPermits: n, latestRun: runs[0] ?? null };
}

export async function getPermitsUniverse(): Promise<number> {
  const [{ n }] = await q<{ n: number }>(`SELECT COUNT(*)::int n FROM estimate.permits`);
  return n;
}
