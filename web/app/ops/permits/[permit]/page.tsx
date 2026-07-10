import Link from "next/link";
import { notFound } from "next/navigation";
import {
  loadEyeballVerdicts,
  loadPermitStatus,
  loadClusters,
  loadCloseabilityFull,
  loadLayeredPlans,
  loadTrainRoster,
  findOverlaysForPermit,
  type OverlayImage,
} from "@/lib/opsData";
import { getDocMeta, type DocMeta } from "@/lib/opsPages";
import OrigOverlayPair from "@/components/OrigOverlayPair";
import DocStrip from "@/components/DocStrip";
import { DEMO_PERMITS } from "@/lib/demoTypes";
import { GUIDES } from "@/lib/guides";

export const dynamic = "force-dynamic";

// Pull "<docid>_p<page>" out of overlay filenames like
// overlay_24-06748-RNVS_7372349_p5_model.png / downstream_..._4237450_p7.jpg
const DOC_PAGE_RE = /(\d{6,})_p(\d+)/;

function overlayDocPage(
  o: OverlayImage,
  fallback: { doc_id: string; page: string } | null
): { doc_id: string | null; page: string | null } {
  const m = o.file.match(DOC_PAGE_RE);
  if (m) return { doc_id: m[1], page: m[2] };
  // eyeball renders are named <permit>.jpg — the matching verdict/roster row
  // records which doc/page that render came from.
  if (fallback) return { doc_id: fallback.doc_id, page: fallback.page };
  return { doc_id: null, page: null };
}

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
  const rosterRow = loadTrainRoster().find((r) => r.permit === permit) ?? null;
  const overlays = findOverlaysForPermit(permit);

  const known =
    verdicts.length || status || myCluster || closeRows.length || layerRows.length || overlays.length;
  if (!known) notFound();

  const latest = verdicts[0] ?? null;
  const hasDemo = DEMO_PERMITS.includes(permit);
  const hasGuide = Object.prototype.hasOwnProperty.call(GUIDES, permit);
  const fallbackDocPage = latest
    ? { doc_id: latest.doc_id, page: latest.page }
    : rosterRow
      ? { doc_id: rosterRow.doc_id, page: rosterRow.page }
      : null;

  // Primary documents for the full-document strips: the docs this permit's
  // pipeline artifacts actually reference (roster first, then verdicts,
  // then geometry candidates), capped so a permit with many scored docs
  // doesn't render a wall of strips.
  const docOrder: string[] = [];
  const pushDoc = (id: string | null | undefined) => {
    if (id && /^\d+$/.test(id) && !docOrder.includes(id)) docOrder.push(id);
  };
  pushDoc(rosterRow?.doc_id);
  for (const v of verdicts) pushDoc(v.doc_id);
  for (const r of closeRows) pushDoc(r.doc_id);
  for (const r of layerRows) pushDoc(r.doc_id);
  // permits whose only doc references live in overlay filenames (e.g. the
  // TRUTH_AREA takeoff permits — no layered/closeability/verdict rows)
  for (const o of overlays) pushDoc(o.file.match(DOC_PAGE_RE)?.[1]);
  const docMetas = (await Promise.all(docOrder.slice(0, 3).map((d) => getDocMeta(d)))).filter(
    (m): m is DocMeta => m !== null
  );

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
          <div className="section-title">Before / after ({overlays.length} renders)</div>
          <div className="pair-list">
            {overlays.map((o) => {
              const { doc_id, page } = overlayDocPage(o, fallbackDocPage);
              return (
                <OrigOverlayPair
                  key={o.rel}
                  docId={doc_id}
                  page={page}
                  overlaySrc={`/api/opsimg/${o.rel.split("/").map(encodeURIComponent).join("/")}`}
                  overlayFile={o.file}
                />
              );
            })}
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

      {docMetas.length > 0 && (
        <>
          <div className="section-title">Full document{docMetas.length > 1 ? "s" : ""}</div>
          {docMetas.map((m) => (
            <DocStrip key={m.docId} docId={m.docId} pageCount={m.pageCount} titles={m.titles} name={m.name} />
          ))}
          <p className="hint">
            Tap a page to view it full size. Page titles are read from the extracted page text where
            available.
          </p>
        </>
      )}
      <div style={{ height: 30 }} />
    </main>
  );
}
