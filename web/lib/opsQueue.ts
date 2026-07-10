// Builds the Screen C ("Check queue") worklist from real pipeline
// artifacts. Priority order per OPS_UI_V1.md: UNCLEAR permits first, then
// borderline gate candidates, then dual-engine disagreements (thin — only
// exists where scoreboard.csv actually recorded a multi-engine run).
import {
  loadCloseabilityFull,
  loadEyeballVerdicts,
  latestVerdictByPermit,
  loadScoreboard,
  findOverlaysForPermit,
  gateBorderline,
  type CloseRow,
} from "./opsData";

export type QueueItem = {
  key: string; // stable id for the item
  kind: "unclear" | "borderline" | "dual";
  permit: string;
  doc_id: string;
  page: string;
  overlay: { rel: string; file: string } | null;
  metrics: Record<string, string>;
  priorReason?: string;
  kindLabel: string;
};

function pickOverlay(permit: string, doc_id: string, page: string) {
  const found = findOverlaysForPermit(permit);
  if (!found.length) return null;
  const exact = found.find((f) => f.file.includes(`${doc_id}_p${page}`) || f.file.includes(`${doc_id}`));
  return exact ?? found[0];
}

export function buildCheckQueue(): QueueItem[] {
  const verdicts = loadEyeballVerdicts();
  const latest = latestVerdictByPermit(verdicts);
  const judgedPermits = new Set(verdicts.map((v) => v.permit));

  const items: QueueItem[] = [];

  // Tier 1: still-UNCLEAR permits (latest verdict per permit === UNCLEAR).
  for (const [permit, v] of latest) {
    if (v.verdict !== "UNCLEAR") continue;
    items.push({
      key: `unclear:${permit}:${v.doc_id}:${v.page}`,
      kind: "unclear",
      permit,
      doc_id: v.doc_id,
      page: v.page,
      overlay: pickOverlay(permit, v.doc_id, v.page),
      metrics: {},
      priorReason: v.reason,
      kindLabel: "Unclear — needs a second look",
    });
  }

  // Tier 2: borderline gate candidates never yet judged.
  const close = loadCloseabilityFull();
  const seenBorderline = new Set<string>();
  for (const r of close) {
    if (judgedPermits.has(r.permit)) continue;
    if (seenBorderline.has(r.permit)) continue;
    if (!gateBorderline(r)) continue;
    seenBorderline.add(r.permit);
    items.push({
      key: `borderline:${r.permit}:${r.doc_id}:${r.page}`,
      kind: "borderline",
      permit: r.permit,
      doc_id: r.doc_id,
      page: r.page,
      overlay: pickOverlay(r.permit, r.doc_id, r.page),
      metrics: fmtCloseMetrics(r),
      kindLabel: "Borderline gate score — never eyeballed",
    });
  }

  // Tier 3: dual-engine disagreement permits recorded in scoreboard.csv
  // (rules_engine=dual with more than one engine in engine_provenance).
  const board = loadScoreboard();
  const seenDual = new Set<string>();
  for (const r of board) {
    if (judgedPermits.has(r.permit) || seenDual.has(r.permit)) continue;
    const m = r.flags.match(/engine_provenance=([^|]+)/);
    if (!m) continue;
    const engines = new Set(
      m[1]
        .split(",")
        .map((s) => s.split(":")[0])
        .filter(Boolean)
    );
    if (engines.size < 2) continue;
    seenDual.add(r.permit);
    const closeRow = close.find((c) => c.permit === r.permit);
    items.push({
      key: `dual:${r.permit}`,
      kind: "dual",
      permit: r.permit,
      doc_id: closeRow?.doc_id ?? "",
      page: closeRow?.page ?? "",
      overlay: pickOverlay(r.permit, closeRow?.doc_id ?? "", closeRow?.page ?? ""),
      metrics: {
        "n auto": String(r.n_auto ?? "—"),
        "n review": String(r.n_review ?? "—"),
        "total SF": r.total_sf != null ? String(r.total_sf) : "—",
        "engine mix": m[1],
      },
      kindLabel: "Rules vs model disagreement",
    });
  }

  return items;
}

function fmtCloseMetrics(r: CloseRow): Record<string, string> {
  return {
    "room-band polygons": r.n_mid != null ? String(r.n_mid) : "—",
    "room-band coverage": r.cov_mid != null ? r.cov_mid.toFixed(3) : "—",
    "largest polygon frac": r.largest_frac != null ? r.largest_frac.toFixed(3) : "—",
    "fpp used": r.best_fpp != null ? String(r.best_fpp) : "—",
  };
}
