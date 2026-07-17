// Shared types + pure geometry helpers for the geometry annotation editor.
// NO node/`fs` imports here so this module is safe to import from the client
// component. Server-only IO lives in lib/annotate.ts.
//
// Coordinate systems (read GEOMETRY_REBOOT_V1.md "Data contract"):
//   - PIXEL space  = the viewport PNG's own pixels (e.g. 899 x 2506 at
//     24 px/foot). The UI draws and stores vertices here.
//   - PDF space    = source PDF points as the annotation packet records them
//     (fitz device points, y-down, viewport_bbox origin at top-left). This is
//     the contract coordinate system written to the JSONL on save.
// The per-page affine in the sam_smoke bundle transforms.json converts between
// the two; its self-test round-trips < 1e-12 px.

export const OUTCOMES = [
  "enclosed_polygon",
  "open_zone",
  "finish_zone",
  "not_in_scope",
  "unresolved",
] as const;
export type Outcome = (typeof OUTCOMES)[number];

export const BOUNDARY_TYPES = [
  "wall",
  "finish",
  "exterior",
  "open_split",
  "mixed",
  "unresolved",
] as const;
export type BoundaryType = (typeof BOUNDARY_TYPES)[number];

// Outcomes that REQUIRE a closed polygon vs. those that must NOT have one.
export const POLYGON_OUTCOMES: ReadonlySet<Outcome> = new Set<Outcome>([
  "enclosed_polygon",
  "open_zone",
  "finish_zone",
]);
export const NO_POLYGON_OUTCOMES: ReadonlySet<Outcome> = new Set<Outcome>([
  "not_in_scope",
  "unresolved",
]);

export const PX_PER_FOOT = 24;

export type Pt = [number, number];

// One page's PDF<->pixel affine, lifted from the sam_smoke bundle transforms.
export interface PageTransform {
  page_index: number;
  sheet_number: string;
  pixel_size: [number, number]; // [w, h]
  // affine rows are [coef_a, coef_b, offset]: out = a*inX + b*inY + offset
  forward_affine: { px_x: [number, number, number]; px_y: [number, number, number] };
  inverse_affine: { pdf_x: [number, number, number]; pdf_y: [number, number, number] };
  image_source: "sam_smoke_bundle" | "local_render";
}

// One append-only row in data/geometry_annotations/human/<permit>.outcomes.jsonl.
export interface OutcomeRow {
  // V1 rows are retained as proposals for V2 re-review. This explicit marker
  // prevents a saved editor row from being mistaken for qualified truth.
  record_status?: "v1_provisional_not_eligible";
  task_id: string;
  saved_at: string;
  reviewer: string;
  outcome: Outcome;
  boundary_types: BoundaryType[];
  polygon_pdf: Pt[] | null;
  open_zone_members: string[];
  notes: string | null;
  // 0-based line index in the JSONL of the previous winning row for this
  // task_id, or null if this is the first row for the task. Latest row wins.
  supersedes: number | null;
  // Provenance of the starting polygon the human edited. "drawn_from_scratch"
  // or a machine-proposal id like "sam_smoke_v1:variant_b".
  proposal_source: string;
}

// A machine proposal offered as a starting polygon (loaded only if the results
// file exists; the human still edits + confirms it).
export interface Proposal {
  polygon_px: Pt[];
  source: string; // e.g. "sam_smoke_v1:variant_b"
}

// One task as handed to the editor: packet fields + bundle transform + anchor
// + any latest human outcome + any machine proposal.
export interface TaskView {
  task_id: string;
  level: string;
  page_index: number;
  sheet_number: string;
  code: string;
  name: string;
  schedule_area_sf_reference: number | null;
  floor_material_reference: string | null;
  allowed_outcomes: Outcome[];
  allowed_boundary_types: BoundaryType[];
  anchor_px: Pt | null; // room-label location marker, from bundle tasks.json
  transform: PageTransform;
  proposal: Proposal | null;
  latest: OutcomeRow | null;
  // latest.polygon_pdf converted back into pixel space for re-editing.
  latest_polygon_px: Pt[] | null;
}

export interface BoardData {
  permit: string;
  imageSourceNote: string;
  tasks: TaskView[];
  // codes present on each level (for the open-zone member multi-select).
  levelCodes: Record<string, { code: string; name: string }[]>;
}

// ---- pure affine + area helpers (shared by server and client) ----

export function pxToPdf(p: Pt, t: PageTransform): Pt {
  const [px, py] = p;
  const ax = t.inverse_affine.pdf_x;
  const ay = t.inverse_affine.pdf_y;
  return [ax[0] * px + ax[1] * py + ax[2], ay[0] * px + ay[1] * py + ay[2]];
}

export function pdfToPx(p: Pt, t: PageTransform): Pt {
  const [x, y] = p;
  const ax = t.forward_affine.px_x;
  const ay = t.forward_affine.px_y;
  return [ax[0] * x + ax[1] * y + ax[2], ay[0] * x + ay[1] * y + ay[2]];
}

// Shoelace area in pixels^2 (absolute value).
export function polygonAreaPx2(pts: Pt[]): number {
  if (pts.length < 3) return 0;
  let a = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i];
    const [x2, y2] = pts[(i + 1) % pts.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}

// Pixel polygon -> square feet (display + diagnostic only; never a target).
export function polygonAreaSf(pts: Pt[]): number {
  return polygonAreaPx2(pts) / (PX_PER_FOOT * PX_PER_FOOT);
}
