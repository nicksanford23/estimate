// APPEND-ONLY S8 human-gate decision for the temp ML workbench. Writes ONE row
// to data/geometry_annotations/human/<permit>.outcomes.jsonl per the LOCKED
// state contract (docs/pilot/FULL_PROCESS_LOCKED.md S8). Never mutates an
// existing line; latest row per id wins on read. Server-side validation only —
// no client value is trusted into a path or a decision vocabulary.
//
// FOUNDER CAVEAT: functional slice, pending founder visual sign-off.
import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { isValidPermit, outcomesFile } from "@/lib/lab";

export const dynamic = "force-dynamic";

// The four S8 lab actions (map 1:1 to the review-queue buttons).
const DECISIONS = new Set(["accept", "reject_reference", "needs_judgment", "skip"]);
const PROCESS_VERSION = "FULL_PROCESS_LOCKED v1.0";

export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const permit = typeof body.permit === "string" ? body.permit : "";
  if (!isValidPermit(permit)) return NextResponse.json({ error: "bad permit" }, { status: 400 });

  // task/surface id — the canonical id the decision attaches to.
  const taskId = typeof body.task_id === "string" ? body.task_id.trim() : "";
  if (!taskId || taskId.length > 200) return NextResponse.json({ error: "missing task/surface id" }, { status: 400 });

  const decision = typeof body.decision === "string" ? body.decision : "";
  if (!DECISIONS.has(decision)) {
    return NextResponse.json({ error: "decision must be one of accept|reject_reference|needs_judgment|skip" }, { status: 400 });
  }

  // identities[] — room-identity memberships of this surface (codes only).
  const identities: string[] = Array.isArray(body.identities)
    ? body.identities.filter((c): c is string => typeof c === "string").slice(0, 100)
    : [];

  // reference_confirmed — accept implies the reference was confirmed; a bare
  // reject means it was not. Explicit bool wins when provided.
  let referenceConfirmed: boolean;
  if (typeof body.reference_confirmed === "boolean") referenceConfirmed = body.reference_confirmed;
  else referenceConfirmed = decision === "accept";

  const notes = typeof body.notes === "string" && body.notes.trim() ? body.notes.trim().slice(0, 4000) : null;

  const file = outcomesFile(permit);
  fs.mkdirSync(path.dirname(file), { recursive: true });

  // supersedes = 0-based index (among non-empty lines) of the previous winning
  // row for this task_id, or null if this is the first.
  let supersedes: number | null = null;
  if (fs.existsSync(file)) {
    const lines = fs.readFileSync(file, "utf8").split("\n");
    let count = -1;
    for (const line of lines) {
      const s = line.trim();
      if (!s) continue;
      count++;
      try {
        const row = JSON.parse(s) as { task_id?: unknown };
        if (row.task_id === taskId) supersedes = count;
      } catch {
        /* skip malformed */
      }
    }
  }

  const row = {
    record_status: "v1_provisional_not_eligible" as const,
    task_id: taskId,
    identities,
    decision,
    reference_confirmed: referenceConfirmed,
    saved_at: new Date().toISOString(),
    reviewer: "nick:lab",
    notes,
    supersedes,
    versions: { process: PROCESS_VERSION },
  };

  // APPEND-ONLY. Never rewrite existing lines.
  fs.appendFileSync(file, JSON.stringify(row) + "\n");

  return NextResponse.json({ ok: true, row });
}
