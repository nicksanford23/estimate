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
  materialsJoined,
  loadLabelProposals,
  type OverlayImage,
} from "@/lib/opsData";
import { getDocMeta, type DocMeta } from "@/lib/opsPages";
import {
  getPermitRecord,
  getDocumentsInventory,
  getProcessedDocuments,
  getLabeledPageProgress,
  getLatestLabelsForPermit,
} from "@/lib/opsDb";
import { getPermitDisplayName } from "@/lib/opsNames";
import { r2Set } from "@/lib/r2";
import OrigOverlayPair from "@/components/OrigOverlayPair";
import DocStrip from "@/components/DocStrip";
import PermitWorkbenchTabs from "@/components/PermitWorkbenchTabs";
import type { PagesTabDoc } from "@/components/PagesTab";
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
  if (fallback) return { doc_id: fallback.doc_id, page: fallback.page };
  return { doc_id: null, page: null };
}

// Simple filename/name -> badge classifier. Not exhaustive — a handful of
// common patterns is enough for the Documents tab; misses just show no badge.
function docTypeBadge(name: string | null): string | null {
  const n = (name ?? "").toLowerCase();
  if (/rev|addend/i.test(n)) return "revision";
  if (/survey/i.test(n)) return "survey";
  if (/permit|application|afidavit|affidavit|paperwork/i.test(n)) return "paperwork";
  if (/arch|floor|a-\d/i.test(n)) return "arch set";
  return null;
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

  const [permitRecord, docsInventory, processedDocs, labelProgress, latestLabels, downloadedSet, displayName] =
    await Promise.all([
      getPermitRecord(permit),
      getDocumentsInventory(permit),
      getProcessedDocuments(permit),
      getLabeledPageProgress(permit),
      getLatestLabelsForPermit(permit),
      r2Set(),
      getPermitDisplayName(permit),
    ]);

  const known =
    verdicts.length ||
    status ||
    myCluster ||
    closeRows.length ||
    layerRows.length ||
    overlays.length ||
    permitRecord ||
    docsInventory.length;
  if (!known) notFound();

  const latest = verdicts[0] ?? null;
  const hasDemo = DEMO_PERMITS.includes(permit);
  const hasGuide = Object.prototype.hasOwnProperty.call(GUIDES, permit);
  const fallbackDocPage = latest
    ? { doc_id: latest.doc_id, page: latest.page }
    : rosterRow
      ? { doc_id: rosterRow.doc_id, page: rosterRow.page }
      : null;

  const docOrder: string[] = [];
  const pushDoc = (id: string | null | undefined) => {
    if (id && /^\d+$/.test(id) && !docOrder.includes(id)) docOrder.push(id);
  };
  pushDoc(rosterRow?.doc_id);
  for (const v of verdicts) pushDoc(v.doc_id);
  for (const r of closeRows) pushDoc(r.doc_id);
  for (const r of layerRows) pushDoc(r.doc_id);
  for (const o of overlays) pushDoc(o.file.match(DOC_PAGE_RE)?.[1]);
  const docMetas = (await Promise.all(docOrder.slice(0, 3).map((d) => getDocMeta(d)))).filter(
    (m): m is DocMeta => m !== null
  );

  // ---- checklist numbers (honest — "—" when unknown, never fabricated) ----
  const docsInventoried = docsInventory.length;
  const docsDownloaded = docsInventory.filter((d) => downloadedSet.has(d.doc_id)).length;
  const pagesLabeled = labelProgress.total > 0 ? `${labelProgress.labeled}/${labelProgress.total}` : "—";
  const geometryCount = closeRows.length > 0 ? `${closeRows.length} pages scored` : "—";
  const confirmedVerdicts = verdicts.filter((v) => v.verdict === "CONFIRMED").length;
  const humanVerified = verdicts.length ? (confirmedVerdicts > 0 ? `${confirmedVerdicts} confirmed` : "no confirm yet") : "—";
  const materialsOk = materialsJoined(permit);
  const proposals = loadLabelProposals(permit);
  const hasProposals = Object.keys(proposals).length > 0;

  // ---- Pages tab data: one doc section per processed/downloaded doc ----
  const labelsByDoc = new Map<number, Map<number, string | null>>();
  for (const row of latestLabels) {
    let m = labelsByDoc.get(row.document_id);
    if (!m) labelsByDoc.set(row.document_id, m = new Map());
    m.set(row.page_index, row.category);
  }
  const downloadedProcessedDocs = processedDocs.filter((d) => downloadedSet.has(d.onestop_doc_id));
  const pagesDocMetas = await Promise.all(
    downloadedProcessedDocs.map((d) => getDocMeta(d.onestop_doc_id))
  );
  const pagesTabDocs: PagesTabDoc[] = downloadedProcessedDocs
    .map((d, i) => {
      const meta = pagesDocMetas[i];
      const pageCount = meta?.pageCount ?? d.page_count ?? 0;
      if (!pageCount) return null;
      const labelMap = labelsByDoc.get(d.id);
      const labels: (string | null)[] = Array.from({ length: pageCount }, (_, pi) => labelMap?.get(pi) ?? null);
      return {
        docId: d.onestop_doc_id,
        name: meta?.name ?? d.filename,
        pageCount,
        titles: meta?.titles ?? Array.from({ length: pageCount }, () => null),
        labels,
      };
    })
    .filter((d): d is PagesTabDoc => d !== null)
    .sort((a, b) => b.pageCount - a.pageCount);
  // Suggestions file is keyed by page_index only (no doc_id) — attach it to
  // the largest/default-open doc, the plan-set doc it was generated against.
  if (hasProposals && pagesTabDocs.length) {
    pagesTabDocs[0].suggestions = Array.from({ length: pagesTabDocs[0].pageCount }, (_, pi) => {
      const p = proposals[String(pi)];
      return p ? { label: p.label, evidence: p.evidence } : null;
    });
  }

  const overviewTab = (
    <>
      <div className="section-title">Processing checklist</div>
      <div className="checklist-row">
        <ChecklistChip
          label="Docs inventoried"
          value={docsInventoried > 0 ? String(docsInventoried) : "—"}
          state={docsInventoried > 0 ? "done" : "unknown"}
        />
        <ChecklistChip
          label="Docs downloaded"
          value={docsInventoried > 0 ? `${docsDownloaded}/${docsInventoried}` : "—"}
          state={docsInventoried > 0 ? (docsDownloaded === docsInventoried ? "done" : docsDownloaded > 0 ? "partial" : "none") : "unknown"}
        />
        <ChecklistChip
          label="Pages labeled"
          value={pagesLabeled}
          state={labelProgress.total > 0 ? (labelProgress.labeled === labelProgress.total ? "done" : labelProgress.labeled > 0 ? "partial" : "none") : "unknown"}
        />
        <ChecklistChip label="Geometry (floor plans)" value={geometryCount} state={closeRows.length > 0 ? "partial" : "unknown"} />
        <ChecklistChip label="Materials joined" value={materialsOk ? "yes" : "no"} state={materialsOk ? "done" : "none"} />
        <ChecklistChip label="Human verified" value={humanVerified} state={confirmedVerdicts > 0 ? "done" : verdicts.length ? "partial" : "unknown"} />
      </div>

      {permitRecord && (
        <>
          <div className="section-title">Permit record</div>
          <div className="ops-table-wrap">
            <table className="ops-table">
              <tbody>
                <tr>
                  <td>Address</td>
                  <td className="wrap">{permitRecord.address ?? <span className="dash">—</span>}</td>
                </tr>
                <tr>
                  <td>Description</td>
                  <td className="wrap">{permitRecord.description ?? <span className="dash">—</span>}</td>
                </tr>
                <tr>
                  <td>Status</td>
                  <td>{permitRecord.status ?? <span className="dash">—</span>}</td>
                </tr>
                <tr>
                  <td>Contractor</td>
                  <td>{permitRecord.contractor ?? <span className="dash">—</span>}</td>
                </tr>
                <tr>
                  <td>Cost / SF</td>
                  <td className="mono-num">
                    {permitRecord.cost ?? "—"} / {permitRecord.sqft ?? "—"}
                  </td>
                </tr>
              </tbody>
            </table>
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
    </>
  );

  const documentsTab = (
    <>
      <div className="section-title">
        Documents ({docsInventory.length}, {docsDownloaded} downloaded)
      </div>
      <div className="ops-table-wrap">
        <table className="ops-table">
          <thead>
            <tr>
              <th>Doc</th>
              <th>Name</th>
              <th>Type</th>
              <th>Pages</th>
              <th>Downloaded</th>
              <th>PDF</th>
            </tr>
          </thead>
          <tbody>
            {docsInventory.map((d) => {
              const downloaded = downloadedSet.has(d.doc_id);
              const processed = processedDocs.find((p) => p.onestop_doc_id === d.doc_id);
              const badge = docTypeBadge(d.name);
              return (
                <tr key={d.doc_id}>
                  <td className="mono-num">{d.doc_id}</td>
                  <td className="wrap">{d.name ?? <span className="dash">—</span>}</td>
                  <td>{badge ? <span className="chip">{badge}</span> : <span className="dash">—</span>}</td>
                  <td className="mono-num">{processed?.page_count ?? <span className="dash">—</span>}</td>
                  <td>
                    {downloaded ? (
                      <span className="status-pill CONFIRMED">downloaded</span>
                    ) : (
                      <span className="chip disabled">not downloaded</span>
                    )}
                  </td>
                  <td>
                    {downloaded ? (
                      <a href={`/api/pdf/${d.doc_id}`} target="_blank" rel="noreferrer" className="btn ghost">
                        Open PDF ↗
                      </a>
                    ) : (
                      <span className="dash">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {docsInventory.length === 0 && (
              <tr>
                <td colSpan={6} className="empty">
                  No document inventory on file for this permit.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );

  const historyTab = (
    <>
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

      {overlays.length === 0 && verdicts.length === 0 && docMetas.length === 0 && (
        <p className="hint">No history recorded for this permit yet.</p>
      )}
    </>
  );

  const takeoffTab = (
    <>
      <div className="section-title">Takeoff</div>
      <div className="actions" style={{ marginBottom: 12 }}>
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
      {!hasDemo && !hasGuide && <p className="hint">No takeoff/guide built for this permit yet.</p>}
    </>
  );

  return (
    <main>
      <Link href="/ops/permits" className="back" style={{ margin: "0 0 12px", display: "inline-block" }}>
        ← all buildings
      </Link>

      <div className="ops-detail-head">
        <div>
          <h1>{displayName}</h1>
          <div style={{ marginTop: 2 }}>
            <span className="mono-num" style={{ fontSize: 12, color: "var(--muted)" }}>
              {permit}
            </span>
          </div>
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

      <PermitWorkbenchTabs
        permit={permit}
        overview={overviewTab}
        documents={documentsTab}
        pagesDocs={pagesTabDocs}
        history={historyTab}
        takeoff={takeoffTab}
      />

      <div style={{ height: 30 }} />
    </main>
  );
}

function ChecklistChip({
  label,
  value,
  state,
}: {
  label: string;
  value: string;
  state: "done" | "partial" | "none" | "unknown";
}) {
  return (
    <div className={`checklist-chip state-${state}`}>
      <span className="checklist-label">{label}</span>
      <span className="checklist-value">{value}</span>
    </div>
  );
}
