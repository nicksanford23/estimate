// TEMP ML workbench — server-only IO, rebuilt 2026-07-17 to mirror the LOCKED
// process (docs/pilot/FULL_PROCESS_LOCKED.md). The UI's only job is to make the
// process statuses visible and to make S8 human decisions possible; this module
// derives everything FRESH from artifacts on disk (no cache) so the workbench
// lights up as a parallel agent lands edge_gate_full/* files.
//
// FOUNDER CAVEAT (standing): this is a FUNCTIONAL SLICE, not a signed-off visual
// design. No invented polish. Projects are shown by ADDRESS, never permit
// number (permit is internal plumbing). Pending founder visual sign-off.
import fs from "fs";
import path from "path";

const ROOT = path.join(process.cwd(), "..");
export const SMOKE = path.join(ROOT, "data", "sam_smoke");
export const PDF_DIR = path.join(ROOT, "data", "render_cache", "pdf");
const GEO_HUMAN = path.join(ROOT, "data", "geometry_annotations", "human");

// Source plan documents per project (active revision first).
export const PROJECT_DOCS: Record<string, string[]> = {
  "24-06748-RNVS": ["7372349"],
  "14-11290-NEWC": ["1494156"],
  "20-29653-RNVS": ["4941409", "4941399", "4941401", "4941403"],
};

// Human names (address + what it is). Projects are never shown to people by
// permit number — that's internal plumbing (founder rule, 2026-07-17).
export const PROJECT_NAMES: Record<string, { name: string; blurb: string }> = {
  "24-06748-RNVS": { name: "600 Baronne St", blurb: "4-story corner building — mixed use, decks on top" },
  "14-11290-NEWC": { name: "Liberty Bank — 3002 Gentilly Blvd", blurb: "new bank branch with retail space" },
  "20-29653-RNVS": { name: "1514 Calhoun St", blurb: "interior renovation — two of four units on file" },
};

export function projectName(permit: string): string {
  return PROJECT_NAMES[permit]?.name ?? permit;
}

export function isValidPermit(permit: string): boolean {
  return /^[0-9A-Za-z-]{4,40}$/.test(permit) && !permit.includes("..");
}

function projDir(permit: string): string {
  return path.join(SMOKE, permit);
}
function exists(...segs: string[]): boolean {
  return fs.existsSync(path.join(...segs));
}
function readJson<T>(file: string): T | null {
  try {
    if (!fs.existsSync(file)) return null;
    return JSON.parse(fs.readFileSync(file, "utf8")) as T;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// S8 human decisions (append-only outcomes JSONL). Latest row per id wins.
// The lab's decide API writes S8 records with a `decision` field into the same
// data/geometry_annotations/human/<permit>.outcomes.jsonl the editor appends to
// (one append-only history, per the locked state contract). We only read the
// rows that carry a `decision` here — editor rows (outcome-only) are ignored.
// ---------------------------------------------------------------------------
export interface S8Decision {
  task_id: string;
  decision: string;
  reference_confirmed?: boolean;
  saved_at?: string;
  reviewer?: string;
  notes?: string | null;
}
export function outcomesFile(permit: string): string {
  return path.join(GEO_HUMAN, `${permit}.outcomes.jsonl`);
}
export function latestDecisions(permit: string): Record<string, S8Decision> {
  const file = outcomesFile(permit);
  const out: Record<string, S8Decision> = {};
  if (!fs.existsSync(file)) return out;
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    const s = line.trim();
    if (!s) continue;
    try {
      const r = JSON.parse(s) as Record<string, unknown>;
      // Only S8 lab decisions carry a `decision`; editor rows do not.
      if (typeof r.task_id === "string" && typeof r.decision === "string") {
        out[r.task_id] = {
          task_id: r.task_id,
          decision: r.decision,
          reference_confirmed: typeof r.reference_confirmed === "boolean" ? r.reference_confirmed : undefined,
          saved_at: typeof r.saved_at === "string" ? r.saved_at : undefined,
          reviewer: typeof r.reviewer === "string" ? r.reviewer : undefined,
          notes: typeof r.notes === "string" ? r.notes : null,
        };
      }
    } catch {
      /* skip malformed */
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Pipeline status strip — one chip per stage. Every chip is derived from a
// concrete artifact; when the artifact is absent the chip is "unknown" and the
// UI renders "-" (never a fake green).
// ---------------------------------------------------------------------------
export type StageState = "done" | "unknown";
export interface StageChip {
  key: string; // e.g. "S1"
  label: string; // short human label
  state: StageState;
  detail: string | null; // count or short note, null when unknown
}

// Count kept pages (S1 trimmed views on disk).
function keptPageCount(permit: string): number {
  const dir = path.join(projDir(permit), "kept_pages");
  if (!fs.existsSync(dir)) return 0;
  return fs.readdirSync(dir).filter((f) => /^page_[0-9]{2}\.png$/.test(f)).length;
}

// Roster / identity count: prefer bundle/tasks.json total, else proposals count.
function rosterCount(permit: string): number | null {
  const tasks = readJson<{ counts?: { total?: number } }>(path.join(projDir(permit), "bundle", "tasks.json"));
  if (tasks?.counts?.total != null) return tasks.counts.total;
  const props = readJson<unknown>(path.join(projDir(permit), "results", "proposals_for_editor.json"));
  if (props && typeof props === "object") return Object.keys(props as Record<string, unknown>).length;
  if (Array.isArray(props)) return props.length;
  return null;
}

// Draft outline count: overlays rendered by the vision draft pass (S4).
function draftCount(permit: string): number {
  const dir = path.join(projDir(permit), "claude_vision");
  if (!fs.existsSync(dir)) return 0;
  return fs.readdirSync(dir).filter((f) => /^overlay_.*\.png$/.test(f)).length;
}

// Which gate-results file to trust (edge_gate_full preferred; edge_gate is the
// prototype that already exists for 600 Baronne).
export function gateResultsPath(permit: string): string | null {
  const full = path.join(projDir(permit), "edge_gate_full", "gate_results.json");
  if (fs.existsSync(full)) return full;
  const proto = path.join(projDir(permit), "edge_gate", "gate_results.json");
  if (fs.existsSync(proto)) return proto;
  return null;
}
// The directory the gate proofs live in (matches gateResultsPath choice).
export function gateProofDirs(permit: string): string[] {
  return [
    path.join(projDir(permit), "edge_gate_full"),
    path.join(projDir(permit), "edge_gate"),
  ];
}

// Status-colored floor maps rendered by scripts/render_floor_maps.py.
export function listFloorMaps(permit: string): string[] {
  const out: string[] = [];
  for (const dir of gateProofDirs(permit)) {
    if (!fs.existsSync(dir)) continue;
    for (const f of fs.readdirSync(dir)) if (/^floormap_p[0-9]+\.png$/.test(f) && !out.includes(f)) out.push(f);
  }
  return out.sort();
}

export function stageStrip(permit: string): StageChip[] {
  const dir = projDir(permit);
  const kept = keptPageCount(permit);
  const roster = rosterCount(permit);
  const drafts = draftCount(permit);
  const scaleGate = readJson<unknown>(path.join(dir, "scale_gate.json"));
  const hasMap = exists(dir, "PROJECT_PACKET_NOTES.md");
  const hasCriticize = exists(dir, "inspection");
  const gate = gateResultsPath(permit);
  const decisions = latestDecisions(permit);
  const decidedCount = Object.keys(decisions).length;

  const done = (label: string, key: string, detail: string | null): StageChip => ({ key, label, state: "done", detail });
  const unknown = (label: string, key: string): StageChip => ({ key, label, state: "unknown", detail: null });

  return [
    kept > 0 ? done("pages", "S1", `${kept}`) : unknown("pages", "S1"),
    hasMap ? done("map", "S1.5", null) : unknown("map", "S1.5"),
    scaleGate ? done("scale", "S1.7", null) : unknown("scale", "S1.7"),
    roster != null ? done("roster", "S2", `${roster}`) : unknown("roster", "S2"),
    drafts > 0 ? done("drafts", "S4", `${drafts}`) : unknown("drafts", "S4"),
    hasCriticize ? done("criticized", "S5", null) : unknown("criticized", "S5"),
    gate ? done("measured", "S5.5", null) : unknown("measured", "S5.5"),
    decidedCount > 0 ? done("decided", "S8", `${decidedCount}`) : unknown("decided", "S8"),
  ];
}

// ---------------------------------------------------------------------------
// Index summary (one card per project).
// ---------------------------------------------------------------------------
export interface ProjectSummary {
  permit: string;
  name: string;
  blurb: string;
  stages: StageChip[];
  identitiesDiscovered: number | null; // room identities in the roster
  surfacesResolved: number | null; // consolidated physical surfaces (surfaces.json)
  surfacesConsolidated: boolean; // false => count is identities, "unconsolidated"
}

export function surfacesPath(permit: string): string | null {
  const p = path.join(projDir(permit), "surfaces.json");
  return fs.existsSync(p) ? p : null;
}

function surfaceCount(permit: string): { count: number | null; consolidated: boolean } {
  const sp = surfacesPath(permit);
  if (sp) {
    const raw = readJson<unknown>(sp);
    if (Array.isArray(raw)) return { count: raw.length, consolidated: true };
    if (raw && typeof raw === "object") {
      const obj = raw as { surfaces?: unknown };
      if (Array.isArray(obj.surfaces)) return { count: obj.surfaces.length, consolidated: true };
      return { count: Object.keys(raw as Record<string, unknown>).length, consolidated: true };
    }
  }
  // No consolidation yet: fall back to the identity count, flagged unconsolidated.
  return { count: rosterCount(permit), consolidated: false };
}

export function projectSummary(permit: string): ProjectSummary {
  const surf = surfaceCount(permit);
  return {
    permit,
    name: PROJECT_NAMES[permit]?.name ?? permit,
    blurb: PROJECT_NAMES[permit]?.blurb ?? "",
    stages: stageStrip(permit),
    identitiesDiscovered: rosterCount(permit),
    surfacesResolved: surf.count,
    surfacesConsolidated: surf.consolidated,
  };
}

export function listProjectSummaries(): ProjectSummary[] {
  if (!fs.existsSync(SMOKE)) return [];
  return fs
    .readdirSync(SMOKE)
    .filter((d) => {
      try {
        return fs.statSync(path.join(SMOKE, d)).isDirectory() && isValidPermit(d);
      } catch {
        return false;
      }
    })
    .map(projectSummary)
    .sort((a, b) => (b.identitiesDiscovered ?? 0) - (a.identitiesDiscovered ?? 0));
}

// ---------------------------------------------------------------------------
// Review queue (S5.5 -> S8): the star of the project page. Reads
// edge_gate_full/QUEUE.json when present. Absent => the measuring gate has not
// run yet for this project (graceful; lights up when the file lands).
// ---------------------------------------------------------------------------
export interface QueueItem {
  id: string; // task/surface id used for the S8 decision
  identities: string[]; // room-identity codes on this surface
  identityLabel: string | null; // e.g. space name
  verdict: string; // measured verdict
  worstDeviationIn: number | null; // worst deviation in inches
  reason: string | null; // one-line reason
  proofImages: string[]; // proof filenames (basename), served via ?kind=proof
  edgeZooms: string[];   // raw per-edge strips, click-through zooms only
  referenceConfirmed: boolean | null;
  decision: S8Decision | null; // latest human decision, if any
}

function basename(p: unknown): string | null {
  if (typeof p !== "string" || !p) return null;
  const b = path.basename(p);
  return /^[A-Za-z0-9_.-]+\.png$/.test(b) ? b : null;
}

function asCodes(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  const out: string[] = [];
  for (const e of v) {
    if (typeof e === "string") out.push(e);
    else if (e && typeof e === "object") {
      const c = (e as { code?: unknown }).code;
      if (typeof c === "string") out.push(c);
    }
  }
  return out;
}

// Give the reviewer one readable, whole-room image first. The measurement
// pipeline also emits narrow per-edge crops; those are useful evidence, but
// they belong behind explicit detail controls instead of competing for card
// width with the room image.
function reviewProofBundle(
  permit: string,
  identityCodes: string[],
  id: string,
  rawProofs: string[],
): { proofImages: string[]; edgeZooms: string[] } {
  const proofs = [...new Set(rawProofs)];
  const code = identityCodes[0] ?? id.replace(/^S-/, "");
  for (const dir of gateProofDirs(permit)) {
    if (code && fs.existsSync(path.join(dir, `review_${code}.png`))) {
      return { proofImages: [`review_${code}.png`], edgeZooms: proofs };
    }
  }

  const roomProof = proofs.find((name) => /_room\.png$/.test(name));
  if (roomProof) {
    return { proofImages: [roomProof], edgeZooms: proofs.filter((name) => name !== roomProof) };
  }
  return { proofImages: proofs.slice(0, 1), edgeZooms: proofs.slice(1) };
}

// Tolerant parse: QUEUE.json shape is being finalized by a parallel agent, so we
// accept a top-level array or {tasks|queue|items:[...]} and read several likely
// field names per item. Missing fields degrade to null, never crash.
export function loadReviewQueue(permit: string): { present: boolean; items: QueueItem[] } {
  const file = path.join(projDir(permit), "edge_gate_full", "QUEUE.json");
  if (!fs.existsSync(file)) return { present: false, items: [] };
  const raw = readJson<unknown>(file);
  if (raw == null) return { present: true, items: [] };
  let list: unknown[] = [];
  if (Array.isArray(raw)) list = raw;
  else if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    list = (o.tasks ?? o.queue ?? o.items ?? o.surfaces ?? []) as unknown[];
    if (!Array.isArray(list)) list = [];
  }
  const decisions = latestDecisions(permit);
  const items: QueueItem[] = list
    .filter((e): e is Record<string, unknown> => !!e && typeof e === "object")
    .map((e) => {
      const id = String(e.surface_id ?? e.task_id ?? e.id ?? e.code ?? "");
      const identities = asCodes(e.identities ?? e.members ?? e.identity_codes);
      const proofRaw = (e.proof_images ?? e.proofs ?? e.proof) as unknown;
      const proofs: string[] = [];
      if (Array.isArray(proofRaw)) for (const p of proofRaw) { const b = basename(p); if (b) proofs.push(b); }
      else { const b = basename(proofRaw); if (b) proofs.push(b); }
      const rb = basename(e.room_proof_image);
      if (rb && !proofs.includes(rb)) proofs.push(rb);
      const bundle = reviewProofBundle(permit, identities, id, proofs);
      const dev = e.worst_edge_dev_in ?? e.worst_deviation_in ?? e.max_deviation_in ?? e.worst_deviation ?? null;
      const spaceNames = Array.isArray(e.space_names) ? e.space_names : [];
      const firstSpaceName = spaceNames.find((name): name is string => typeof name === "string");
      return {
        id,
        identities: identities.length ? identities : id ? [id] : [],
        identityLabel: typeof e.space_name === "string" ? e.space_name : firstSpaceName ?? (typeof e.name === "string" ? e.name : null),
        verdict: String(e.verdict ?? e.measured_verdict ?? "unknown"),
        worstDeviationIn: typeof dev === "number" ? dev : null,
        reason: typeof e.reason === "string"
          ? e.reason
          : typeof e.one_line_reason === "string"
            ? e.one_line_reason
            : typeof e.one_line === "string"
              ? e.one_line
              : typeof e.rationale === "string"
                ? e.rationale
                : null,
        proofImages: bundle.proofImages,
        edgeZooms: bundle.edgeZooms,
        referenceConfirmed: typeof e.reference_confirmed === "boolean" ? e.reference_confirmed : null,
        decision: id ? decisions[id] ?? null : null,
      };
    })
    .filter((i) => i.id);
  return { present: true, items };
}

// ---------------------------------------------------------------------------
// Surfaces section — grouped by measured verdict. Fed from the gate results
// (edge_gate_full preferred, edge_gate prototype fallback), and when neither
// gate output exists yet, from the old inspection/proposal groupings.
// ---------------------------------------------------------------------------
export interface SurfaceCard {
  id: string;
  identities: string[];
  spaceName: string | null;
  verdict: string;
  worstDeviationIn: number | null;
  reason: string | null;
  proofImages: string[]; // basenames served via ?kind=proof
  edgeZooms: string[]; // secondary room / edge evidence
  overlayCode: string | null; // fallback: claude_vision overlay code (?kind=overlay)
  decision: S8Decision | null;
}
export interface SurfaceGroup {
  verdict: string;
  title: string;
  cards: SurfaceCard[];
}

// Verdict groups in the order the founder reviews them (worst last so decisions
// front-load on clean, hardest surfaces flagged for founder attention).
export const VERDICT_GROUPS: { key: string; title: string }[] = [
  { key: "pass_measured", title: "Passed measurement" },
  { key: "minor_adjustment", title: "Minor adjustment" },
  { key: "major_redraw", title: "Major redraw" },
  { key: "ambiguous", title: "Ambiguous" },
  { key: "needs_founder", title: "Specialty / shaft — needs founder" },
  { key: "wrong_surface_model", title: "Wrong surface model" },
];

// Map any raw verdict to one of the group keys.
function groupOf(verdict: string): string {
  const v = verdict.toLowerCase();
  if (v.includes("wrong_surface")) return "wrong_surface_model";
  if (v.includes("specialty") || v.includes("shaft") || v.includes("needs_founder")) return "needs_founder";
  if (v.includes("ambiguous") || v.includes("unresolved")) return "ambiguous";
  if (v.includes("major")) return "major_redraw";
  if (v.includes("minor")) return "minor_adjustment";
  if (v.includes("pass")) return "pass_measured";
  return "ambiguous"; // unknown verdicts fall to the human-judgment bucket
}

// Worst-first severity for deriving a surface verdict from its edges.
const SEVERITY = ["wrong_surface_model", "needs_founder", "major_redraw", "ambiguous", "minor_adjustment", "pass_measured"];
function worstVerdict(verdicts: string[]): string {
  let worst = "pass_measured";
  let worstRank = SEVERITY.length;
  for (const raw of verdicts) {
    const g = groupOf(raw);
    const r = SEVERITY.indexOf(g);
    if (r >= 0 && r < worstRank) {
      worstRank = r;
      worst = g;
    }
  }
  return worst;
}

interface GateEdge {
  max_deviation_in?: number;
  endpoint_deviation_in?: number;
  verdict?: string;
  proof_image?: string;
}
interface GateSurface {
  code?: string;
  space_name?: string;
  verdict?: string;
  identities?: unknown;
  reason?: string;
  note?: string;
  room_proof_image?: string;
  edges?: GateEdge[];
}

// surfaces.json membership map: id -> identity codes (best-effort).
function surfaceMembership(permit: string): Record<string, string[]> {
  const sp = surfacesPath(permit);
  const raw = sp ? readJson<unknown>(sp) : null;
  const out: Record<string, string[]> = {};
  const put = (id: string, codes: string[]) => { if (id) out[id] = codes; };
  if (Array.isArray(raw)) {
    for (const s of raw) {
      if (s && typeof s === "object") {
        const o = s as Record<string, unknown>;
        put(String(o.surface_id ?? o.id ?? ""), asCodes(o.identities ?? o.members));
      }
    }
  } else if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    const dict = (obj.surfaces && typeof obj.surfaces === "object" ? obj.surfaces : obj) as Record<string, unknown>;
    for (const [id, s] of Object.entries(dict)) {
      if (s && typeof s === "object") put(id, asCodes((s as Record<string, unknown>).identities ?? (s as Record<string, unknown>).members));
    }
  }
  return out;
}

export interface SurfacesResult {
  source: "gate" | "fallback" | "none";
  groups: SurfaceGroup[];
}

export function loadSurfaceGroups(permit: string): SurfacesResult {
  const decisions = latestDecisions(permit);
  const gatePath = gateResultsPath(permit);
  if (gatePath) {
    const gateEnvelope = readJson<Record<string, unknown>>(gatePath);
    const nestedSurfaces = gateEnvelope?.surfaces;
    const gate = nestedSurfaces && typeof nestedSurfaces === "object" && !Array.isArray(nestedSurfaces)
      ? nestedSurfaces as Record<string, GateSurface>
      : gateEnvelope as Record<string, GateSurface> | null;
    const membership = surfaceMembership(permit);
    const cards: SurfaceCard[] = [];
    if (gate) {
      for (const [id, s] of Object.entries(gate)) {
        if (id.startsWith("_")) continue; // topology/diagnostic entries
        if (!s || typeof s !== "object") continue;
        const edges = Array.isArray(s.edges) ? s.edges : [];
        const verdict = s.verdict ? groupOf(s.verdict) : worstVerdict(edges.map((e) => e.verdict ?? "pass_measured"));
        let worst: number | null = null;
        for (const e of edges) {
          for (const d of [e.max_deviation_in, e.endpoint_deviation_in]) {
            if (typeof d === "number" && (worst == null || d > worst)) worst = d;
          }
        }
        const proofs: string[] = [];
        const rb = basename(s.room_proof_image);
        if (rb) proofs.push(rb);
        for (const e of edges) { const b = basename(e.proof_image); if (b) proofs.push(b); }
        const ownIdentities = asCodes(s.identities);
        const identities = ownIdentities.length ? ownIdentities : membership[id]?.length ? membership[id] : [s.code ?? id.replace(/^S-/, "")];
        const bundle = reviewProofBundle(permit, identities, id, proofs);
        cards.push({
          id,
          identities,
          spaceName: typeof s.space_name === "string" ? s.space_name : null,
          verdict,
          worstDeviationIn: worst,
          reason: typeof s.reason === "string" ? s.reason : typeof s.note === "string" ? s.note : null,
          proofImages: bundle.proofImages,
          edgeZooms: bundle.edgeZooms,
          overlayCode: null,
          decision: decisions[id] ?? null,
        });
      }
    }
    return { source: "gate", groups: groupCards(cards) };
  }

  // Fallback: no gate output yet (bank / Calhoun). Group the machine proposals
  // by their inspection verdict / outcome suggestion — clearly labelled as the
  // pre-measurement view.
  const fallback = fallbackCards(permit, decisions);
  return { source: fallback.length ? "fallback" : "none", groups: groupCards(fallback) };
}

function groupCards(cards: SurfaceCard[]): SurfaceGroup[] {
  const byGroup: Record<string, SurfaceCard[]> = {};
  for (const c of cards) (byGroup[c.verdict] ??= []).push(c);
  const groups: SurfaceGroup[] = [];
  for (const g of VERDICT_GROUPS) {
    const cs = byGroup[g.key];
    if (cs && cs.length) {
      cs.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
      groups.push({ verdict: g.key, title: g.title, cards: cs });
    }
  }
  return groups;
}

// Pre-measurement fallback: proposals + edge-inspection verdicts.
function fallbackCards(permit: string, decisions: Record<string, S8Decision>): SurfaceCard[] {
  const dir = projDir(permit);
  const props = readJson<Record<string, { code?: string; space_name?: string; outcome_suggestion?: string }>>(
    path.join(dir, "results", "proposals_for_editor.json"),
  );
  if (!props || typeof props !== "object") return [];
  // Inspection verdicts by room code (only 600 Baronne currently).
  const inspection: Record<string, string> = {};
  const insp = readJson<unknown>(path.join(dir, "inspection", "edge_inspection.json"));
  if (insp) {
    const arr = Array.isArray(insp) ? insp : ((insp as { rooms?: unknown }).rooms ?? Object.values(insp as object));
    if (Array.isArray(arr)) {
      for (const r of arr) {
        if (r && typeof r === "object" && "code" in r) {
          const rr = r as Record<string, unknown>;
          inspection[String(rr.code)] = String(rr.room_verdict ?? "");
        }
      }
    }
  }
  const cards: SurfaceCard[] = [];
  for (const [taskId, p] of Object.entries(props)) {
    const code = String(p.code ?? taskId);
    const inspVerdict = inspection[code];
    // Map the pre-measurement signal onto the same group vocabulary.
    let verdict = "ambiguous";
    if (inspVerdict === "pass") verdict = "pass_measured";
    else if (inspVerdict === "needs_repair") verdict = "major_redraw";
    else if (inspVerdict === "unresolved") verdict = "ambiguous";
    else if (typeof p.outcome_suggestion === "string" && p.outcome_suggestion) verdict = groupOf(p.outcome_suggestion);
    const overlay = exists(dir, "claude_vision", `overlay_${code}.png`) ? code : null;
    cards.push({
      id: taskId,
      identities: [code],
      spaceName: typeof p.space_name === "string" ? p.space_name : null,
      verdict,
      worstDeviationIn: null,
      reason: inspVerdict ? `edge-inspection: ${inspVerdict}` : p.outcome_suggestion ?? null,
      proofImages: [],
      edgeZooms: [],
      overlayCode: overlay,
      decision: decisions[taskId] ?? null,
    });
  }
  return cards;
}

// ---------------------------------------------------------------------------
// Project detail (buttons + page availability) for the project page header.
// ---------------------------------------------------------------------------
export interface ProjectDetail {
  permit: string;
  name: string;
  blurb: string;
  activeDoc: string | null; // full plan set (source PDF) id
  hasKeptImages: boolean;
  hasReport: boolean;
  hasEditor: boolean; // geometry packet exists -> /v2/annotate editor works
}
export function loadProjectDetail(permit: string): ProjectDetail | null {
  if (!isValidPermit(permit) || !fs.existsSync(projDir(permit))) return null;
  const docs = (PROJECT_DOCS[permit] ?? []).filter((d) => fs.existsSync(path.join(PDF_DIR, `${d}.pdf`)));
  return {
    permit,
    name: PROJECT_NAMES[permit]?.name ?? permit,
    blurb: PROJECT_NAMES[permit]?.blurb ?? "",
    activeDoc: docs[0] ?? null,
    hasKeptImages: keptPageCount(permit) > 0,
    hasReport: exists(projDir(permit), "PIPELINE_REPORT.md"),
    hasEditor: fs.existsSync(
      path.join(ROOT, "data", "geometry_annotations", `${permit}.geometry_annotation_packet_v1.json`),
    ),
  };
}
