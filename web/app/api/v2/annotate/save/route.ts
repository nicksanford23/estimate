import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import {
  isValidPermit,
  loadPacket,
  outcomesPath,
  readLatestOutcomes,
} from "@/lib/annotate";
import {
  BOUNDARY_TYPES,
  NO_POLYGON_OUTCOMES,
  OUTCOMES,
  POLYGON_OUTCOMES,
  pxToPdf,
  type BoundaryType,
  type Outcome,
  type OutcomeRow,
  type PageTransform,
  type Pt,
} from "@/lib/annotateTypes";
import { loadBoardData } from "@/lib/annotate";

// Append-only save for a human geometry outcome. Writes ONE row to
// data/geometry_annotations/human/<permit>.outcomes.jsonl and never mutates
// the immutable packet. Validates the row against the packet's allowed
// outcomes/boundary types and the polygon<->outcome invariants BEFORE writing,
// then converts the pixel polygon to PDF/contract coordinates server-side.
const OUTCOME_SET = new Set<string>(OUTCOMES);
const BOUNDARY_SET = new Set<string>(BOUNDARY_TYPES);

export async function POST(req: Request) {
  let body: {
    permit?: string;
    task_id?: string;
    outcome?: string;
    boundary_types?: unknown;
    polygon_px?: unknown;
    open_zone_members?: unknown;
    notes?: unknown;
    proposal_source?: unknown;
    reviewer?: unknown;
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const permit = typeof body.permit === "string" ? body.permit : "";
  if (!isValidPermit(permit)) return NextResponse.json({ error: "bad permit" }, { status: 400 });

  const packet = loadPacket(permit);
  if (!packet) return NextResponse.json({ error: "no packet for permit" }, { status: 404 });

  const task = packet.tasks.find((t) => t.task_id === body.task_id);
  if (!task) return NextResponse.json({ error: "task_id not in packet" }, { status: 404 });

  // outcome must be in the packet's allowed set for this task.
  const outcome = body.outcome;
  if (typeof outcome !== "string" || !OUTCOME_SET.has(outcome) || !task.allowed_outcomes.includes(outcome as Outcome)) {
    return NextResponse.json({ error: "outcome not allowed for this task" }, { status: 400 });
  }

  // boundary types: subset of the packet's allowed set for this task.
  const boundaryTypes: BoundaryType[] = Array.isArray(body.boundary_types)
    ? (body.boundary_types.filter((b) => typeof b === "string") as BoundaryType[])
    : [];
  for (const b of boundaryTypes) {
    if (!BOUNDARY_SET.has(b) || !task.allowed_boundary_types.includes(b)) {
      return NextResponse.json({ error: `boundary type '${b}' not allowed for this task` }, { status: 400 });
    }
  }

  // polygon (pixel coords from the UI) — validate shape, then enforce the
  // outcome<->polygon invariant (contract: polygon outcomes need a closed ring;
  // not_in_scope/unresolved must carry none).
  let polygonPx: Pt[] | null = null;
  if (body.polygon_px != null) {
    if (
      !Array.isArray(body.polygon_px) ||
      !body.polygon_px.every(
        (p) => Array.isArray(p) && p.length === 2 && p.every((n) => typeof n === "number" && Number.isFinite(n))
      )
    ) {
      return NextResponse.json({ error: "polygon_px must be an array of [x,y] numbers" }, { status: 400 });
    }
    polygonPx = body.polygon_px as Pt[];
  }

  if (POLYGON_OUTCOMES.has(outcome as Outcome)) {
    if (!polygonPx || polygonPx.length < 3) {
      return NextResponse.json({ error: `${outcome} requires a closed polygon (>= 3 vertices)` }, { status: 400 });
    }
    if (boundaryTypes.length < 1) {
      return NextResponse.json({ error: `${outcome} requires at least one boundary type` }, { status: 400 });
    }
  }
  if (NO_POLYGON_OUTCOMES.has(outcome as Outcome) && polygonPx && polygonPx.length > 0) {
    return NextResponse.json({ error: `${outcome} must not carry a polygon` }, { status: 400 });
  }

  // open_zone_members: codes that exist on the same level.
  const levelCodes = new Set(packet.tasks.filter((t) => t.level === task.level).map((t) => t.space.code));
  const openZoneMembers: string[] = Array.isArray(body.open_zone_members)
    ? (body.open_zone_members.filter((c) => typeof c === "string") as string[])
    : [];
  for (const c of openZoneMembers) {
    if (!levelCodes.has(c)) {
      return NextResponse.json({ error: `open-zone member '${c}' is not a code on this level` }, { status: 400 });
    }
  }

  // Convert pixel polygon -> PDF/contract coords using this page's transform.
  let polygonPdf: Pt[] | null = null;
  if (polygonPx && polygonPx.length >= 3) {
    const board = loadBoardData(permit);
    const transform: PageTransform | undefined = board?.tasks.find((t) => t.task_id === task.task_id)?.transform;
    if (!transform) return NextResponse.json({ error: "no viewport transform for this task" }, { status: 500 });
    polygonPdf = polygonPx.map((p) => pxToPdf(p, transform));
  }

  const notes = typeof body.notes === "string" && body.notes.trim() ? body.notes.trim() : null;
  const reviewer = typeof body.reviewer === "string" && body.reviewer.trim() ? body.reviewer.trim() : "nick";
  const proposalSource =
    typeof body.proposal_source === "string" && body.proposal_source.trim()
      ? body.proposal_source.trim()
      : "drawn_from_scratch";

  // supersedes = 0-based line index of the previous winning row for this
  // task_id in the current file (null if first). Latest row wins on read.
  const file = outcomesPath(permit);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  let supersedes: number | null = null;
  if (fs.existsSync(file)) {
    const lines = fs.readFileSync(file, "utf8").split("\n");
    let count = -1; // index among non-empty lines
    for (const line of lines) {
      const s = line.trim();
      if (!s) continue;
      count++;
      try {
        const row = JSON.parse(s) as OutcomeRow;
        if (row.task_id === task.task_id) supersedes = count;
      } catch {
        /* skip */
      }
    }
  }

  const row: OutcomeRow = {
    task_id: task.task_id,
    saved_at: new Date().toISOString(),
    reviewer,
    outcome: outcome as Outcome,
    boundary_types: boundaryTypes,
    polygon_pdf: polygonPdf,
    open_zone_members: openZoneMembers,
    notes,
    supersedes,
    proposal_source: proposalSource,
  };

  // APPEND-ONLY. Never rewrite existing lines.
  fs.appendFileSync(file, JSON.stringify(row) + "\n");

  return NextResponse.json({ ok: true, row, latest: readLatestOutcomes(permit) });
}
