// Server-only IO for the geometry annotation editor. Reads the IMMUTABLE
// annotation packet + the sam_smoke bundle (viewport transforms + label
// anchors) + the APPEND-ONLY human outcomes JSONL, and merges them into a
// BoardData for the editor. Nothing here mutates the packet or the bundle.
import fs from "node:fs";
import path from "node:path";
import {
  type BoardData,
  type OutcomeRow,
  type PageTransform,
  type Proposal,
  type Pt,
  type TaskView,
  type Outcome,
  type BoundaryType,
  pdfToPx,
} from "./annotateTypes";

const DATA_ROOT = process.env.DATA_ROOT ?? "/workspaces/estimate";

// Permit ids look like "24-06748-RNVS". Constrain to that shape so nothing in
// a path is attacker-controlled beyond this whitelist.
export function isValidPermit(permit: string): boolean {
  return /^[0-9A-Za-z-]{4,40}$/.test(permit) && !permit.includes("..");
}

function dataPath(...segs: string[]): string {
  return path.join(DATA_ROOT, "data", ...segs);
}

export function packetPath(permit: string): string {
  return dataPath("geometry_annotations", `${permit}.geometry_annotation_packet_v1.json`);
}
export function bundleDir(permit: string): string {
  return dataPath("sam_smoke", permit, "bundle");
}
export function outcomesPath(permit: string): string {
  return dataPath("geometry_annotations", "human", `${permit}.outcomes.jsonl`);
}
export function proposalsPath(permit: string): string {
  return dataPath("sam_smoke", permit, "results", "proposals_for_editor.json");
}
// Local-render fallback dir (only used if the sam_smoke bundle is absent).
export function renderDir(permit: string): string {
  return dataPath("geometry_annotations", "render", permit);
}

// Resolve the viewport PNG for a page. Prefer the sam_smoke bundle; fall back
// to a locally-rendered equivalent. Returns null if neither exists.
export function viewportImagePath(permit: string, page: number): string | null {
  const bundle = path.join(bundleDir(permit), `viewport_p${page}.png`);
  if (fs.existsSync(bundle)) return bundle;
  const local = path.join(renderDir(permit), `viewport_p${page}.png`);
  if (fs.existsSync(local)) return local;
  return null;
}

interface RawTransforms {
  pages: Record<
    string,
    {
      sheet_number: string;
      pixel_size: [number, number];
      forward_affine: { px_x: [number, number, number]; px_y: [number, number, number] };
      inverse_affine: { pdf_x: [number, number, number]; pdf_y: [number, number, number] };
      image: string;
    }
  >;
}

function loadTransforms(permit: string): { map: Record<number, PageTransform>; source: PageTransform["image_source"] } | null {
  const bundleFile = path.join(bundleDir(permit), "transforms.json");
  let source: PageTransform["image_source"] = "sam_smoke_bundle";
  let file = bundleFile;
  if (!fs.existsSync(bundleFile)) {
    const local = path.join(renderDir(permit), "transforms.json");
    if (!fs.existsSync(local)) return null;
    file = local;
    source = "local_render";
  }
  const raw = JSON.parse(fs.readFileSync(file, "utf8")) as RawTransforms;
  const map: Record<number, PageTransform> = {};
  for (const [pageStr, p] of Object.entries(raw.pages)) {
    const page = Number(pageStr);
    map[page] = {
      page_index: page,
      sheet_number: p.sheet_number,
      pixel_size: p.pixel_size,
      forward_affine: p.forward_affine,
      inverse_affine: p.inverse_affine,
      image_source: source,
    };
  }
  return { map, source };
}

// Label-anchor pixel points per task_id, from the bundle tasks.json (used to
// mark the room label location in the editor). Best-effort.
function loadAnchors(permit: string): Record<string, Pt> {
  const file = path.join(bundleDir(permit), "tasks.json");
  if (!fs.existsSync(file)) return {};
  try {
    const raw = JSON.parse(fs.readFileSync(file, "utf8")) as {
      tasks?: { task_id: string; anchor_px?: [number, number] | null }[];
    };
    const out: Record<string, Pt> = {};
    for (const t of raw.tasks ?? []) {
      if (t.anchor_px && Array.isArray(t.anchor_px)) out[t.task_id] = [t.anchor_px[0], t.anchor_px[1]];
    }
    return out;
  } catch {
    return {};
  }
}

// Machine proposals keyed by task_id, offered as starting polygons. Tolerant
// of two shapes: an object {task_id: {...}} or an array of {task_id, ...}.
// It is fine for this file to be absent (the hook is future-facing).
function loadProposals(permit: string): Record<string, Proposal> {
  const file = proposalsPath(permit);
  if (!fs.existsSync(file)) return {};
  try {
    const raw = JSON.parse(fs.readFileSync(file, "utf8")) as unknown;
    const out: Record<string, Proposal> = {};
    const put = (taskId: string, entry: { polygon_px?: Pt[]; polygon?: Pt[]; source?: string; variant?: string }) => {
      const poly = entry.polygon_px ?? entry.polygon;
      if (!Array.isArray(poly) || poly.length < 3) return;
      out[taskId] = { polygon_px: poly as Pt[], source: entry.source ?? entry.variant ?? "sam_smoke_v1" };
    };
    if (Array.isArray(raw)) {
      for (const e of raw as { task_id: string }[]) put(e.task_id, e as never);
    } else if (raw && typeof raw === "object") {
      const obj = raw as { proposals?: Record<string, never> } & Record<string, never>;
      const dict = obj.proposals ?? obj;
      for (const [taskId, e] of Object.entries(dict)) {
        if (e && typeof e === "object") put(taskId, e as never);
      }
    }
    return out;
  } catch {
    return {};
  }
}

// Read the append-only JSONL and resolve the LATEST row per task_id
// (last line wins). Ignores malformed lines rather than throwing so a partial
// write never bricks the board.
export function readLatestOutcomes(permit: string): Record<string, OutcomeRow> {
  const file = outcomesPath(permit);
  if (!fs.existsSync(file)) return {};
  const latest: Record<string, OutcomeRow> = {};
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    const s = line.trim();
    if (!s) continue;
    try {
      const row = JSON.parse(s) as OutcomeRow;
      if (row && typeof row.task_id === "string") latest[row.task_id] = row;
    } catch {
      /* skip malformed line */
    }
  }
  return latest;
}

interface PacketTask {
  task_id: string;
  level: string;
  page_index: number;
  sheet_number: string;
  space: { code: string; name: string; schedule_area_sf_reference?: number; floor_material_reference?: string };
  allowed_outcomes: Outcome[];
  allowed_boundary_types: BoundaryType[];
}
interface Packet {
  permit: string;
  tasks: PacketTask[];
}

export function loadPacket(permit: string): Packet | null {
  const file = packetPath(permit);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8")) as Packet;
}

// Assemble the full BoardData for the editor page. Returns null when the
// packet or the viewport transforms are missing.
export function loadBoardData(permit: string): BoardData | null {
  const packet = loadPacket(permit);
  if (!packet) return null;
  const transforms = loadTransforms(permit);
  if (!transforms) return null;
  const anchors = loadAnchors(permit);
  const proposals = loadProposals(permit);
  const latest = readLatestOutcomes(permit);

  const tasks: TaskView[] = packet.tasks.map((t): TaskView => {
    const transform = transforms.map[t.page_index];
    const latestRow = latest[t.task_id] ?? null;
    let latestPolygonPx: Pt[] | null = null;
    if (latestRow?.polygon_pdf && transform) {
      latestPolygonPx = latestRow.polygon_pdf.map((p) => pdfToPx(p, transform));
    }
    return {
      task_id: t.task_id,
      level: t.level,
      page_index: t.page_index,
      sheet_number: t.sheet_number,
      code: t.space.code,
      name: t.space.name,
      schedule_area_sf_reference: t.space.schedule_area_sf_reference ?? null,
      floor_material_reference: t.space.floor_material_reference ?? null,
      allowed_outcomes: t.allowed_outcomes,
      allowed_boundary_types: t.allowed_boundary_types,
      anchor_px: anchors[t.task_id] ?? null,
      transform,
      proposal: proposals[t.task_id] ?? null,
      latest: latestRow,
      latest_polygon_px: latestPolygonPx,
    };
  });

  const levelCodes: BoardData["levelCodes"] = {};
  for (const t of tasks) {
    (levelCodes[t.level] ??= []).push({ code: t.code, name: t.name });
  }

  return {
    permit: packet.permit,
    imageSourceNote:
      transforms.source === "sam_smoke_bundle"
        ? "sam_smoke bundle (24 px/ft)"
        : "local render fallback (24 px/ft) — reconcile with sam_smoke bundle later",
    tasks,
    levelCodes,
  };
}
