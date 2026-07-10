import Link from "next/link";
import { notFound } from "next/navigation";
import {
  loadEyeballVerdicts,
  loadPermitStatus,
  loadClusters,
  loadCloseabilityFull,
  loadLayeredPlans,
  findOverlaysForPermit,
} from "@/lib/opsData";
import { DEMO_PERMITS } from "@/lib/demoTypes";
import { GUIDES } from "@/lib/guides";

export const dynamic = "force-dynamic";

export default async function OpsPermitDetail({
  params,
}: {
  params: Promise<{ permit: string }>;
}) {
  const { permit: raw } = await params;
  const permit = decodeURIComponent(raw);

  const verdicts = loadEyeballVerdicts()
    .filter((v) => v.permit === permit)
    .sort((a, b) => (a.ts_utc < b.ts_utc ? 1 : -1));
  const status = loadPermitStatus().get(permit) ?? null;
  const clusters = loadClusters();
  const myCluster = clusters.find((c) => c.permit === permit) ?? null;
  const clusterMates = myCluster ? clusters.filter((c) => c.cluster_id === myCluster.cluster_id) : [];
  const closeRows = loadCloseabilityFull().filter((r) => r.permit === permit);
  const layerRows = loadLayeredPlans().filter((r) => r.permit === permit);
  const overlays = findOverlaysForPermit(permit);

  const known =
    verdicts.length || status || myCluster || closeRows.length || layerRows.length || overlays.length;
  if (!known) notFound();

  const latest = verdicts[0] ?? null;
  const hasDemo = DEMO_PERMITS.includes(permit);
  const hasGuide = Object.prototype.hasOwnProperty.call(GUIDES, permit);

  return (
    <main>
      <Link href="/ops/permits" className="back" style={{ margin: "0 0 12px", display: "inline-block" }}>
        ← all buildings
      </Link>

      <div className="ops-detail-head">
        <div>
          <h1>{permit}</h1>
          <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            {status?.tier && <span className="chip code">{status.tier}</span>}
            {latest && <span className={`status-pill ${latest.verdict}`}>{latest.verdict}</span>}
            {status?.status && <span className="chip">{status.status}</span>}
          </div>
        </div>
        <div className="actions">
          {hasDemo && (
            <Link href={`/review/${encodeURIComponent(permit)}`} className="btn primary">
              Open review screen
            </Link>
          )}
          {hasGuide && (
            <Link href={`/permits/${encodeURIComponent(permit)}/guide`} className="btn ghost">
              Takeoff guide
            </Link>
          )}
          <Link href={`/permits/${encodeURIComponent(permit)}`} className="btn ghost">
            Model-1 doc browser
          </Link>
        </div>
      </div>

      {status?.note && (
        <p className="hint" style={{ marginTop: -8 }}>
          <b>Board note:</b> {status.note}
        </p>
      )}

      {overlays.length > 0 && (
        <>
          <div className="section-title">Overlay renders ({overlays.length})</div>
          <div className="ops-overlay-grid">
            {overlays.map((o) => (
              <div className="ops-overlay" key={o.rel}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/api/opsimg/${o.rel.split("/").map(encodeURIComponent).join("/")}`} alt={o.file} loading="lazy" />
                <div className="cap">{o.file}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {(closeRows.length > 0 || layerRows.length > 0) && (
        <>
          <div className="section-title">Geometry metrics</div>
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Doc</th>
                  <th>Page</th>
                  <th>Wall segs</th>
                  <th>Room-band polys</th>
                  <th>Coverage</th>
                  <th>Largest frac</th>
                  <th>fpp</th>
                </tr>
              </thead>
              <tbody>
                {closeRows.map((r) => (
                  <tr key={`${r.doc_id}-${r.page}`}>
                    <td className="mono-num">{r.doc_id}</td>
                    <td className="mono-num">{r.page}</td>
                    <td className="mono-num">{layerRows.find((l) => l.doc_id === r.doc_id && l.page === r.page)?.wall_segs ?? "—"}</td>
                    <td className="mono-num">{r.n_mid ?? "—"}</td>
                    <td className="mono-num">{r.cov_mid != null ? r.cov_mid.toFixed(3) : "—"}</td>
                    <td className="mono-num">{r.largest_frac != null ? r.largest_frac.toFixed(3) : "—"}</td>
                    <td className="mono-num">{r.best_fpp ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {myCluster && (
        <>
          <div className="section-title">
            Firm cluster {myCluster.cluster_id} — {myCluster.architect || "unknown firm"} ({clusterMates.length}{" "}
            {clusterMates.length === 1 ? "member" : "members"})
          </div>
          <div className="cluster-list">
            {clusterMates.map((c) => (
              <Link
                key={c.permit}
                href={`/ops/permits/${encodeURIComponent(c.permit)}`}
                className={`cluster-chip ${c.permit === permit ? "self" : ""}`}
              >
                {c.permit} <span style={{ opacity: 0.6 }}>({c.split})</span>
              </Link>
            ))}
          </div>
        </>
      )}

      {verdicts.length > 0 && (
        <>
          <div className="section-title">Verdict history ({verdicts.length})</div>
          <div className="verdict-hist">
            {verdicts.map((v, i) => (
              <div className="verdict-row" key={i}>
                <span className={`status-pill ${v.verdict}`}>{v.verdict}</span>
                <span className="rz">{v.reason || <span className="dash">no reason recorded</span>}</span>
                <span className="ts">
                  doc {v.doc_id} p{v.page} · slice={v.slice} · {v.ts_utc?.slice(0, 19).replace("T", " ") ?? "—"}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
