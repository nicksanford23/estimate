import Link from "next/link";
import AutoRefresh from "@/components/AutoRefresh";
import { getDiscoveryProgress } from "@/lib/opsDb";
import {
  discoverTargetCount,
  readDownloaderBacklog,
  loadLayeredPlans,
  loadCloseabilityFull,
  loadEyeballVerdicts,
  latestVerdictByPermit,
  loadPermitStatus,
  gatePass,
  parseCsv,
  DATA_ROOT,
  PATHS,
} from "@/lib/opsData";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

const fmt = (n: number) => n.toLocaleString("en-US");
const pct = (a: number, b: number) => (b > 0 ? Math.round((a / b) * 1000) / 10 : 0);

function downloadedPermits(): number {
  const p = path.join(DATA_ROOT, PATHS.downloadBatch);
  if (!fs.existsSync(p)) return 0;
  const rows = parseCsv(fs.readFileSync(p, "utf8"));
  const s = new Set<string>();
  for (const r of rows) if (r.status === "ok" || r.status === "already_in_r2") s.add(r.permit);
  return s.size;
}

export default async function OpsFunnelPage() {
  const [discovery] = await Promise.all([getDiscoveryProgress()]);
  const target = discoverTargetCount();
  const backlog = readDownloaderBacklog();

  const layered = loadLayeredPlans();
  const harvestedPermits = new Set(layered.map((r) => r.permit)).size;

  const close = loadCloseabilityFull();
  const gatePermits = new Set<string>();
  for (const r of close) if (gatePass(r)) gatePermits.add(r.permit);

  const verdicts = loadEyeballVerdicts();
  const latest = latestVerdictByPermit(verdicts);
  let confirmedPermits = 0;
  for (const v of latest.values()) if (v.verdict === "CONFIRMED") confirmedPermits++;

  const status = loadPermitStatus();
  const tierCounts = new Map<string, number>();
  let tieredPermits = 0;
  for (const s of status.values()) {
    if (!s.tier) continue;
    tieredPermits++;
    for (const t of s.tier.split("+").map((x) => x.trim())) {
      tierCounts.set(t, (tierCounts.get(t) ?? 0) + 1);
    }
  }
  const tierList = [...tierCounts.entries()].sort((a, b) => b[1] - a[1]);

  const stages: Array<{
    n: number;
    label: string;
    plain: string;
    href: string;
    tint: string;
  }> = [
    {
      n: discovery.discoveredPermits,
      label: "Discovered",
      plain: "permits whose document lists we've fetched from the city portal",
      href: "/ops/permits?stage=discovered",
      tint: "var(--scraped)",
    },
    {
      n: downloadedPermits(),
      label: "Downloaded",
      plain: "permits with at least one plan-set PDF actually in hand",
      href: "/ops/permits?stage=downloaded",
      tint: "var(--downloaded)",
    },
    {
      n: harvestedPermits,
      label: "Harvested",
      plain: "permits whose plans carry named wall layers we can read",
      href: "/ops/permits?stage=harvested",
      tint: "var(--rendered)",
    },
    {
      n: gatePermits.size,
      label: "Gate-passed",
      plain: "permits whose wall geometry closes into room-shaped polygons",
      href: "/ops/permits?stage=gate_passed",
      tint: "var(--accent)",
    },
    {
      n: confirmedPermits,
      label: "Eyeball-confirmed",
      plain: "permits a human looked at and confirmed are real floor plans",
      href: "/ops/permits?stage=confirmed",
      tint: "var(--labeled)",
    },
    {
      n: tieredPermits,
      label: "Roster tiers",
      plain: "confirmed permits sorted into a training/answer-key tier",
      href: "/ops/permits?stage=tiered",
      tint: "var(--accent-ink)",
    },
  ];

  return (
    <main>
      <AutoRefresh ms={60000} />
      <div className="ops-tickers">
        <div className="ticker">
          <div className="tl">Discovery crawl</div>
          <div className="tv">
            {fmt(discovery.discoveredPermits)} / {target ? fmt(target) : "—"}
          </div>
          <div className="tsub">
            {target ? `${pct(discovery.discoveredPermits, target)}% of the one-time full enumeration` : "target unknown"}
            {discovery.latestRun ? ` · run ${discovery.latestRun.final_state}` : ""}
          </div>
          {target > 0 && (
            <div className="tbar">
              <i style={{ width: `${Math.min(100, pct(discovery.discoveredPermits, target))}%` }} />
            </div>
          )}
        </div>
        <div className="ticker">
          <div className="tl">Downloader backlog</div>
          <div className="tv">{backlog.pendingCandidates != null ? fmt(backlog.pendingCandidates) : "—"}</div>
          <div className="tsub">
            {backlog.pendingCandidates != null ? "candidate PDFs queued to fetch" : "no downloader log found"}
            {backlog.lastCycleUploaded != null
              ? ` · last cycle: ${fmt(backlog.lastCycleUploaded)} uploaded${
                  backlog.lastCycleFailed ? `, ${backlog.lastCycleFailed} failed` : ""
                }`
              : ""}
            {backlog.lastTs ? ` (${backlog.lastTs} UTC)` : ""}
          </div>
        </div>
      </div>

      <div className="section-title">The funnel</div>
      <div className="ops-funnel">
        {stages.map((s) => (
          <Link key={s.label} href={s.href} className="ops-stage" style={{ ["--tint" as string]: s.tint }}>
            <div className="n">{fmt(s.n)}</div>
            <div className="l" style={{ color: s.tint }}>
              {s.label}
            </div>
            <div className="p">{s.plain}</div>
            <div className="bar" />
          </Link>
        ))}
      </div>

      {tierList.length > 0 && (
        <>
          <div className="section-title">Roster tier breakdown</div>
          <div className="tier-pills">
            {tierList.map(([tier, n]) => (
              <Link key={tier} href={`/ops/permits?tier=${encodeURIComponent(tier)}`} className="tier-pill">
                <b>{fmt(n)}</b> {tier}
              </Link>
            ))}
          </div>
        </>
      )}

      <p className="hint" style={{ marginTop: 8 }}>
        Auto-refreshes every 60s. Sources: estimate.discovered_docs / discovery_runs (Neon),
        data/triage/{"{"}download_batch, layered_plans, closeability_full, eyeball_verdicts, permit_status{"}"}
        .
      </p>
    </main>
  );
}
