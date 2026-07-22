// Server-only loader for the Floor Areas workspace
// (V2_PRODUCT_REBUILD_PLAN_V1.md §6.4, §7, §17). It reads the IMMUTABLE
// geometry annotation packet, the sam_smoke viewport bundle (transforms +
// label anchors), the machine proposals, and the APPEND-ONLY human outcomes,
// and merges them into one FloorAreaRoom per queue entry.
//
// Honesty rules baked in here (not styling — data):
//   - Machine proposals are `machine`/`provisional`, never V2-approved truth.
//   - Human V1 outlines are `provisional`, never approved V2 geometry.
//   - There is NO approved geometry in this dataset yet, so `approved` is
//     always absent. The product must not manufacture a green state.
//   - Schedule area is carried but flagged diagnostic-only; the UI hides it
//     during inspection (§13). It never selects or reshapes a polygon.
//
// The proposals_for_editor.json polygons are in PDF space (`polygon_pdf`); we
// convert them to pixel space with each page's affine so the canvas can draw
// them over the viewport PNG.

import fs from "node:fs";
import { loadBoardData, proposalsPath } from "./annotate";
import { pdfToPx, polygonAreaSf, type PageTransform, type Pt } from "./annotateTypes";

export type FloorAreaStatus = "proposal" | "provisional" | "unresolved" | "no_proposal";

export interface FloorAreaProposal {
  polygonPx: Pt[];
  source: string;
  confidence: number | null;
  outcomeSuggestion: string | null;
  // Per-edge notes the proposer wrote about its OWN boundary choices. These
  // are the proposal's stated reasoning, NOT an independent edge inspection —
  // real critique is a later slice (§8.2). Surfaced honestly as such.
  boundaryNotes: string[];
  measuredSf: number;
}

export interface FloorAreaHuman {
  polygonPx: Pt[] | null;
  outcome: string;
  boundaryTypes: string[];
  notes: string | null;
  savedAt: string;
  reviewer: string;
  measuredSf: number | null;
}

export interface FloorAreaRoom {
  taskId: string;
  code: string;
  name: string;
  level: string;
  pageIndex: number;
  sheetNumber: string;
  imgW: number;
  imgH: number;
  anchorPx: Pt | null;
  scheduleAreaSf: number | null;
  floorMaterial: string | null;
  proposal: FloorAreaProposal | null;
  human: FloorAreaHuman | null;
  status: FloorAreaStatus;
}

export interface FloorAreasData {
  permit: string;
  imageSourceNote: string;
  rooms: FloorAreaRoom[];
  counts: FloorAreaCounts;
}

export interface FloorAreaCounts {
  total: number;
  withProposal: number;
  provisional: number; // human provisional outline saved
  unresolved: number;
  approved: number; // V2 human-approved geometry — 0 in this dataset by design
}

interface RawProposalEntry {
  polygon_pdf?: Pt[];
  source?: string;
  proposal_source?: string;
  confidence?: number;
  outcome_suggestion?: string;
  boundary_notes?: string[];
}

function readRawProposals(permit: string): Record<string, RawProposalEntry> {
  const file = proposalsPath(permit);
  if (!fs.existsSync(file)) return {};
  try {
    const raw = JSON.parse(fs.readFileSync(file, "utf8")) as unknown;
    if (raw && typeof raw === "object" && !Array.isArray(raw)) {
      return raw as Record<string, RawProposalEntry>;
    }
  } catch {
    /* absent/malformed proposals are fine — rooms just show no proposal */
  }
  return {};
}

function proposalFor(
  entry: RawProposalEntry | undefined,
  transform: PageTransform | undefined
): FloorAreaProposal | null {
  if (!entry || !transform) return null;
  const pdf = entry.polygon_pdf;
  if (!Array.isArray(pdf) || pdf.length < 3) return null;
  const polygonPx = pdf.map((p) => pdfToPx([p[0], p[1]], transform));
  return {
    polygonPx,
    source: entry.source ?? entry.proposal_source ?? "machine proposal",
    confidence: typeof entry.confidence === "number" ? entry.confidence : null,
    outcomeSuggestion: entry.outcome_suggestion ?? null,
    boundaryNotes: Array.isArray(entry.boundary_notes)
      ? entry.boundary_notes.filter((n): n is string => typeof n === "string")
      : [],
    measuredSf: polygonAreaSf(polygonPx),
  };
}

function statusFor(proposal: FloorAreaProposal | null, human: FloorAreaHuman | null): FloorAreaStatus {
  if (human) return human.outcome === "unresolved" ? "unresolved" : "provisional";
  if (proposal) return "proposal";
  return "no_proposal";
}

// Returns null when the permit has no geometry annotation packet or viewport
// bundle on disk (i.e. Floor Areas is not available for this project yet).
export function loadFloorAreas(permit: string): FloorAreasData | null {
  const board = loadBoardData(permit);
  if (!board) return null;
  const rawProposals = readRawProposals(permit);

  const rooms: FloorAreaRoom[] = board.tasks
    // A task with no page transform can't be drawn on the canvas; drop it
    // rather than crash. (Transforms come from the sam_smoke bundle.)
    .filter((t) => t.transform && Array.isArray(t.transform.pixel_size))
    .map((t): FloorAreaRoom => {
    const proposal = proposalFor(rawProposals[t.task_id], t.transform);
    const latest = t.latest;
    const human: FloorAreaHuman | null = latest
      ? {
          polygonPx: t.latest_polygon_px,
          outcome: latest.outcome,
          boundaryTypes: [...latest.boundary_types],
          notes: latest.notes,
          savedAt: latest.saved_at,
          reviewer: latest.reviewer,
          measuredSf: t.latest_polygon_px ? polygonAreaSf(t.latest_polygon_px) : null,
        }
      : null;
    return {
      taskId: t.task_id,
      code: t.code,
      name: t.name,
      level: t.level,
      pageIndex: t.page_index,
      sheetNumber: t.sheet_number,
      imgW: t.transform.pixel_size[0],
      imgH: t.transform.pixel_size[1],
      anchorPx: t.anchor_px,
      scheduleAreaSf: t.schedule_area_sf_reference,
      floorMaterial: t.floor_material_reference,
      proposal,
      human,
      status: statusFor(proposal, human),
    };
  });

  // Queue order: level, then room code numerically.
  rooms.sort(
    (a, b) =>
      a.level.localeCompare(b.level) ||
      a.code.localeCompare(b.code, undefined, { numeric: true })
  );

  const counts: FloorAreaCounts = {
    total: rooms.length,
    withProposal: rooms.filter((r) => r.proposal).length,
    provisional: rooms.filter((r) => r.status === "provisional").length,
    unresolved: rooms.filter((r) => r.status === "unresolved").length,
    approved: 0,
  };

  return { permit: board.permit, imageSourceNote: board.imageSourceNote, rooms, counts };
}

// Lightweight status for a project card / overview without shipping polygons
// to the client. Returns null if the project has no Floor Areas data.
export function floorAreaSummary(permit: string): FloorAreaCounts | null {
  const data = loadFloorAreas(permit);
  return data ? data.counts : null;
}
