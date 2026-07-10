// Server-only readers for the Ops dashboard ("Mission Control").
// Reads the CSV/JSONL/JSON artifacts the triage + probe pipeline already
// writes under data/ (gitignored). Read-only except appendVerdict(), which
// is the ONE permitted mutation (Screen C, append-only eyeball_verdicts.csv).
//
// No fabricated numbers: every function here reads a real file and returns
// "—"/null for anything absent, never a guess.
import fs from "node:fs";
import path from "node:path";

export const DATA_ROOT = process.env.DATA_ROOT ?? "/workspaces/estimate";
const D = (...p: string[]) => path.join(DATA_ROOT, ...p);

// ---------------------------------------------------------------- CSV -----
// Minimal RFC4180 parser: quoted fields, "" escapes, commas/newlines inside
// quotes. Good enough for our own pipeline's CSVs (no exotic encodings).
export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n") {
      row.push(field);
      field = "";
      rows.push(row);
      row = [];
    } else if (c === "\r") {
      // skip; \n handles the row break
    } else {
      field += c;
    }
  }
  if (field.length || row.length) {
    row.push(field);
    rows.push(row);
  }
  const nonEmpty = rows.filter((r) => !(r.length === 1 && r[0] === ""));
  if (!nonEmpty.length) return [];
  const header = nonEmpty[0];
  return nonEmpty.slice(1).map((r) => {
    const o: Record<string, string> = {};
    header.forEach((h, i) => (o[h] = r[i] ?? ""));
    return o;
  });
}

function readCsv(rel: string): Record<string, string>[] {
  const p = D(rel);
  if (!fs.existsSync(p)) return [];
  return parseCsv(fs.readFileSync(p, "utf8"));
}

function readJsonl(rel: string): Record<string, unknown>[] {
  const p = D(rel);
  if (!fs.existsSync(p)) return [];
  return fs
    .readFileSync(p, "utf8")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

function readJson<T>(rel: string): T | null {
  const p = D(rel);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

const num = (v: string | undefined) => {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const bool = (v: string | undefined) => /^(true|1|yes)$/i.test((v ?? "").trim());

// ---------------------------------------------------------- file paths ---
export const PATHS = {
  downloadBatch: "data/triage/download_batch_2026-07-09.csv",
  layeredPlans: "data/triage/layered_plans.csv",
  closeabilityFull: "data/triage/closeability_full.csv",
  eyeballVerdicts: "data/triage/eyeball_verdicts.csv",
  trainRoster: "data/triage/train_layered_roster.csv",
  permitStatus: "data/triage/permit_status.jsonl",
  clusters: "data/probe30b/clusters.csv",
  scoreboard: "data/takeoff/scoreboard.csv",
  discoverTargets: "data/discover_targets.csv",
  overnightLog: "data/triage/overnight_dl.log",
};

// ------------------------------------------------------------ loaders ----
export type LayeredRow = {
  permit: string;
  doc_id: string;
  page: string;
  wall_segs: number | null;
  layers: string;
};
export function loadLayeredPlans(): LayeredRow[] {
  return readCsv(PATHS.layeredPlans).map((r) => ({
    permit: r.permit,
    doc_id: r.doc_id,
    page: r.page,
    wall_segs: num(r.wall_segs),
    layers: r.layers,
  }));
}

export type CloseRow = {
  permit: string;
  doc_id: string;
  page: string;
  n_mid: number | null;
  cov_mid: number | null;
  largest_frac: number | null;
  best_fpp: number | null;
  rep_flag: boolean;
  bad_title: boolean;
  layers: string;
  note: string;
};
export function loadCloseabilityFull(): CloseRow[] {
  return readCsv(PATHS.closeabilityFull).map((r) => ({
    permit: r.permit,
    doc_id: r.doc_id,
    page: r.page,
    n_mid: num(r.n_mid),
    cov_mid: num(r.cov_mid),
    largest_frac: num(r.largest_frac),
    best_fpp: num(r.best_fpp),
    rep_flag: bool(r.rep_flag),
    bad_title: bool(r.bad_title),
    layers: r.layers,
    note: r.note,
  }));
}

// The calibrated gate, verbatim from data/triage/usable_layered_report.md
// ("## The calibrated gate"): rep_flag=false, bad_title=false, n_mid>=8,
// cov_mid>=0.2, largest_frac<=0.7. A permit passes if ANY of its scored
// pages passes.
export function gatePass(r: CloseRow): boolean {
  return (
    !r.rep_flag &&
    !r.bad_title &&
    (r.n_mid ?? 0) >= 8 &&
    (r.cov_mid ?? 0) >= 0.2 &&
    (r.largest_frac ?? 1) <= 0.7
  );
}
// The relaxed ("borderline — eyeball these") gate from the same report:
// mid>=5, cov_mid>=0.1, largest<=0.8, but NOT the main gate.
export function gateBorderline(r: CloseRow): boolean {
  return (
    (r.n_mid ?? 0) >= 5 &&
    (r.cov_mid ?? 0) >= 0.1 &&
    (r.largest_frac ?? 1) <= 0.8 &&
    !gatePass(r)
  );
}

export type VerdictRow = {
  permit: string;
  doc_id: string;
  page: string;
  verdict: "CONFIRMED" | "FALSE_PASS" | "UNCLEAR" | string;
  is_floor_plan: string;
  reason: string;
  slice: string;
  ts_utc: string;
};
export function loadEyeballVerdicts(): VerdictRow[] {
  return readCsv(PATHS.eyeballVerdicts).map((r) => ({
    permit: r.permit,
    doc_id: r.doc_id,
    page: r.page,
    verdict: r.verdict as VerdictRow["verdict"],
    is_floor_plan: r.is_floor_plan,
    reason: r.reason,
    slice: r.slice,
    ts_utc: r.ts_utc,
  }));
}

// Latest verdict per permit (by ts_utc; falls back to file order).
export function latestVerdictByPermit(rows: VerdictRow[]): Map<string, VerdictRow> {
  const m = new Map<string, VerdictRow>();
  for (const r of rows) {
    const prev = m.get(r.permit);
    if (!prev || (r.ts_utc || "") >= (prev.ts_utc || "")) m.set(r.permit, r);
  }
  return m;
}

export type RosterRow = {
  permit: string;
  doc_id: string;
  page: string;
  fpp: number | null;
  verdict_source: string;
};
export function loadTrainRoster(): RosterRow[] {
  return readCsv(PATHS.trainRoster).map((r) => ({
    permit: r.permit,
    doc_id: r.doc_id,
    page: r.page,
    fpp: num(r.fpp),
    verdict_source: r.verdict_source,
  }));
}

export type PermitStatus = {
  permit: string;
  status: string;
  tier: string | null;
  note: string;
  updated_at: string;
};
export function loadPermitStatus(): Map<string, PermitStatus> {
  const rows = readJsonl(PATHS.permitStatus) as unknown as Array<{
    permit: string;
    status: string;
    tier: string | null;
    note?: string;
    updated_at?: string;
  }>;
  const m = new Map<string, PermitStatus>();
  for (const r of rows) {
    m.set(r.permit, {
      permit: r.permit,
      status: r.status,
      tier: r.tier ?? null,
      note: r.note ?? "",
      updated_at: r.updated_at ?? "",
    });
  }
  return m;
}

export type ClusterRow = {
  cluster_id: string;
  permit: string;
  split: string;
  wall_sig_norm: string;
  architect: string;
  n_mid: number | null;
  cov_mid: number | null;
  largest_frac: number | null;
};
export function loadClusters(): ClusterRow[] {
  return readCsv(PATHS.clusters).map((r) => ({
    cluster_id: r.cluster_id,
    permit: r.permit,
    split: r.split,
    wall_sig_norm: r.wall_sig_norm,
    architect: r.architect,
    n_mid: num(r.n_mid),
    cov_mid: num(r.cov_mid),
    largest_frac: num(r.largest_frac),
  }));
}
export function clusterMap(rows: ClusterRow[]): Map<string, ClusterRow> {
  return new Map(rows.map((r) => [r.permit, r]));
}

export type ScoreboardRow = {
  permit: string;
  ts: string;
  path: string;
  n_auto: number | null;
  n_review: number | null;
  n_open: number | null;
  n_artifact: number | null;
  total_sf: number | null;
  graded_median_err: number | null;
  graded_coverage: number | null;
  green_precision: number | null;
  flags: string;
};
export function loadScoreboard(): ScoreboardRow[] {
  return readCsv(PATHS.scoreboard).map((r) => ({
    permit: r.permit,
    ts: r.ts,
    path: r.path,
    n_auto: num(r.n_auto),
    n_review: num(r.n_review),
    n_open: num(r.n_open),
    n_artifact: num(r.n_artifact),
    total_sf: num(r.total_sf),
    graded_median_err: num(r.graded_median_err),
    graded_coverage: num(r.graded_coverage),
    green_precision: num(r.green_precision),
    flags: r.flags,
  }));
}

// Count of discovery targets = one-time full-enumeration denominator
// (data/discover_targets.csv, one row per un-enumerated permit).
export function discoverTargetCount(): number {
  const p = D(PATHS.discoverTargets);
  if (!fs.existsSync(p)) return 0;
  // count data lines (minus header) without loading the whole 9k-row parse
  const text = fs.readFileSync(p, "utf8");
  const lines = text.split("\n").filter((l) => l.trim().length > 0);
  return Math.max(0, lines.length - 1);
}

// Parses the tail of the overnight downloader log for a backlog reading.
export type DownloaderBacklog = {
  pendingCandidates: number | null;
  lastCycleUploaded: number | null;
  lastCycleFailed: number | null;
  lastTs: string | null;
  discoveryState: string | null;
};
export function readDownloaderBacklog(): DownloaderBacklog {
  const p = D(PATHS.overnightLog);
  const out: DownloaderBacklog = {
    pendingCandidates: null,
    lastCycleUploaded: null,
    lastCycleFailed: null,
    lastTs: null,
    discoveryState: null,
  };
  if (!fs.existsSync(p)) return out;
  const lines = fs.readFileSync(p, "utf8").split("\n").filter(Boolean);
  for (let i = lines.length - 1; i >= 0 && (out.pendingCandidates === null || out.lastCycleUploaded === null); i--) {
    const l = lines[i];
    const ts = l.match(/^\[(\d\d:\d\d:\d\d)\]/);
    const cyc = l.match(/cycle:\s*(\d+)\s*candidates pending.*discovery=(\w+)/);
    if (cyc && out.pendingCandidates === null) {
      out.pendingCandidates = Number(cyc[1]);
      out.discoveryState = cyc[2];
      out.lastTs = out.lastTs ?? ts?.[1] ?? null;
    }
    const done = l.match(/cycle done:\s*(\d+)\s*uploaded,\s*(\d+)\s*dead\/failed/);
    if (done && out.lastCycleUploaded === null) {
      out.lastCycleUploaded = Number(done[1]);
      out.lastCycleFailed = Number(done[2]);
      out.lastTs = out.lastTs ?? ts?.[1] ?? null;
    }
  }
  return out;
}

// ------------------------------------------------------------- overlays --
// Directories the mission whitelists for overlay/render images, scanned
// (non-recursively) for filenames containing the permit number.
const OVERLAY_DIRS = [
  "data/triage/eyeball",
  "data/probe30/overlays",
  "data/probe30/product_test",
  "data/probe30b",
  "data/probe2",
  "data/probe2b",
  "data/probe23",
  "data/probe24",
  "data/probe25",
  "data/probe26",
  "data/probe27",
  "data/probe28",
  "data/probe29",
];
const IMG_RE = /\.(jpg|jpeg|png)$/i;

export type OverlayImage = { rel: string; file: string; dir: string };

// Cache the directory listings for the process lifetime — these dirs are
// static pipeline output, not written to while the dashboard runs.
let _dirCache: Map<string, string[]> | null = null;
function listDir(rel: string): string[] {
  if (!_dirCache) _dirCache = new Map();
  if (_dirCache.has(rel)) return _dirCache.get(rel)!;
  const p = D(rel);
  let files: string[] = [];
  try {
    files = fs.readdirSync(p).filter((f) => IMG_RE.test(f));
  } catch {
    files = [];
  }
  _dirCache.set(rel, files);
  return files;
}

export function findOverlaysForPermit(permit: string): OverlayImage[] {
  const short = permit.split("-").slice(0, 2).join("-"); // e.g. "25-33341"
  const out: OverlayImage[] = [];
  for (const dir of OVERLAY_DIRS) {
    for (const f of listDir(dir)) {
      if (f.includes(permit) || f.includes(short)) {
        out.push({ rel: `${dir}/${f}`, file: f, dir });
      }
    }
  }
  return out;
}

// Resolve + validate a relative overlay path for streaming (path-traversal
// safe: must land under DATA_ROOT, inside one of the whitelisted dirs, and
// have an image extension).
export function resolveOverlayPath(rel: string): string | null {
  if (rel.includes("..")) return null;
  if (!IMG_RE.test(rel)) return null;
  const okDir = OVERLAY_DIRS.some((d) => rel === d || rel.startsWith(d + "/"));
  if (!okDir) return null;
  const full = path.resolve(D(rel));
  const root = path.resolve(DATA_ROOT);
  if (!full.startsWith(root + path.sep)) return null;
  if (!fs.existsSync(full)) return null;
  return full;
}

// ---------------------------------------------------- probe30 artifacts --
export type SegmentResults = {
  train_permits: string[];
  holdout_permits: string[];
  fixed_model: {
    n_train_segs: number;
    n_train_wall: number;
    canonical_threshold: number;
    train_f1_at_threshold: number;
    pooled_holdout_pr_auc: number;
    spread: { min: number; median: number; max: number };
  };
  probe25_baseline_pr_auc_range: [number, number];
  learning_curve: Array<{
    n_train_permits: number;
    pooled_holdout_pr_auc: number;
    median_holdout_pr_auc: number;
  }>;
};
export function loadSegmentResults(): SegmentResults | null {
  return readJson<SegmentResults>("data/probe30/segment_results.json");
}

export type Scorecard = {
  n_addressable_total: number;
  n_missed_total: number;
  pct_missed: number;
  n_matched_total: number;
  n_matched_le_30pct_err: number;
  median_abs_pct_error_matched: number;
  n_confident_wrong_total?: number;
  n_dual_review_total?: number;
  rules_v4_reference: { missed_pct: number; matched_le_30pct: number; median_err_pct: number };
  model_reference?: { missed_pct: number; matched_le_30pct: number; median_err_pct: number };
};
export function loadScorecard(which: "model" | "dual"): Scorecard | null {
  return readJson<Scorecard>(`data/probe30/product_test/scorecard_${which}.json`);
}

export type CanaryCase = {
  name: string;
  doc_id?: number;
  page_index?: number;
  verdict: string;
  n_rooms?: number;
  total_sf?: number;
  sane?: boolean;
};
export function loadCanary(which: "model" | "dual"): Record<string, CanaryCase> | null {
  return readJson<Record<string, CanaryCase>>(
    which === "model"
      ? "data/probe30/canary/canary_model_results.json"
      : "data/probe30/canary/canary_dual_results.json"
  );
}

export type DownstreamPoint = {
  n_train_permits: number;
  pooled_holdout_pr_auc: number;
  n_matched_total: number;
  n_missed_total: number;
  n_true_total: number;
  matched_frac: number;
};
export function loadDownstreamCurve(): DownstreamPoint[] {
  return readJson<DownstreamPoint[]>("data/probe30/downstream/learning_curve_downstream.json") ?? [];
}

// ------------------------------------------------------- Screen B rows ---
export type PermitRow = {
  permit: string;
  tier: string | null;
  status: string | null;
  verdict: string | null;
  verdictReason: string | null;
  cluster: string | null;
  architect: string | null;
  metrics: string;
  updated: string | null;
  inHarvested: boolean;
  inGatePassed: boolean;
};

// Merges every local (non-Neon) permit-keyed source into one row map. This
// is the "universe" of permits the SF-extraction pipeline has touched —
// cheap in-memory joins, no Neon round-trip (the big estimate.permits /
// discovered_docs tables are queried separately for the discovery-stage
// view, where the permit list itself comes from Neon).
export function buildPermitRows(): Map<string, PermitRow> {
  const rows = new Map<string, PermitRow>();
  const get = (permit: string): PermitRow => {
    let r = rows.get(permit);
    if (!r) {
      r = {
        permit,
        tier: null,
        status: null,
        verdict: null,
        verdictReason: null,
        cluster: null,
        architect: null,
        metrics: "—",
        updated: null,
        inHarvested: false,
        inGatePassed: false,
      };
      rows.set(permit, r);
    }
    return r;
  };

  const layered = loadLayeredPlans();
  for (const l of layered) get(l.permit).inHarvested = true;

  const close = loadCloseabilityFull();
  const bestClose = new Map<string, CloseRow>();
  for (const r of close) {
    const prev = bestClose.get(r.permit);
    if (!prev || (r.n_mid ?? 0) > (prev.n_mid ?? 0)) bestClose.set(r.permit, r);
    if (gatePass(r)) get(r.permit).inGatePassed = true;
  }
  for (const [permit, r] of bestClose) {
    const row = get(permit);
    if (row.metrics === "—") {
      row.metrics = `mid=${r.n_mid ?? "—"} cov=${r.cov_mid != null ? r.cov_mid.toFixed(2) : "—"} largest=${
        r.largest_frac != null ? r.largest_frac.toFixed(2) : "—"
      }`;
    }
  }

  const verdicts = loadEyeballVerdicts();
  const latest = latestVerdictByPermit(verdicts);
  for (const [permit, v] of latest) {
    const row = get(permit);
    row.verdict = v.verdict;
    row.verdictReason = v.reason;
    row.updated = v.ts_utc || row.updated;
  }

  const status = loadPermitStatus();
  for (const [permit, s] of status) {
    const row = get(permit);
    row.tier = s.tier;
    row.status = s.status;
    if (!row.updated || s.updated_at > row.updated) row.updated = s.updated_at;
  }

  const clusters = loadClusters();
  for (const c of clusters) {
    const row = get(c.permit);
    row.cluster = c.cluster_id;
    row.architect = c.architect;
  }

  const board = loadScoreboard();
  const bestBoard = new Map<string, ScoreboardRow>();
  for (const r of board) {
    if (r.total_sf == null) continue;
    const prev = bestBoard.get(r.permit);
    if (!prev || r.ts > prev.ts) bestBoard.set(r.permit, r);
  }
  for (const [permit, r] of bestBoard) {
    const row = get(permit);
    row.metrics = `${fmtNum(r.total_sf)} SF · ${r.n_auto ?? 0} auto / ${r.n_review ?? 0} review`;
  }

  return rows;
}

function fmtNum(n: number | null): string {
  return n == null ? "—" : n.toLocaleString("en-US");
}
