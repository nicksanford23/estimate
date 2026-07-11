import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { TAXONOMY_V2 } from "@/lib/v2Taxonomy";

// Thin Page Review on V2 — binding human decision for claim=page_category.
// INSERT-only into v2.human_decision (append-only, SCHEMA_V2.md §4); if a
// prior binding decision exists for the same target+claim, record a
// decision_relation(supersedes) from the new decision to the old one so the
// supersession graph (walked, never mutated) resolves the new one as truth.
const CATEGORIES = new Set<string>(TAXONOMY_V2);

export async function POST(req: Request) {
  let body: { page_id?: number; category?: string; claim?: string; value_json?: unknown; actor_id?: string; note?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const { page_id, category } = body;
  // Default claim stays 'page_category' for back-compat with the original
  // caller shape; page_flags (and any future claim) reuses the same
  // append-only insert + supersession-walk so the flags toggles in the
  // page-review side panel can POST here too (SCHEMA_V2.md §14).
  const claim = typeof body.claim === "string" && body.claim ? body.claim : "page_category";
  const actor_id = typeof body.actor_id === "string" && body.actor_id ? body.actor_id : "nick";
  const note = typeof body.note === "string" ? body.note : null;

  if (typeof page_id !== "number" || !Number.isInteger(page_id) || page_id <= 0) {
    return NextResponse.json({ error: "page_id must be a positive integer" }, { status: 400 });
  }

  let valueJson: unknown;
  if (claim === "page_category") {
    if (typeof category !== "string" || !CATEGORIES.has(category)) {
      return NextResponse.json({ error: "category not in the 16-slug v2 taxonomy" }, { status: 400 });
    }
    valueJson = { category };
  } else {
    if (typeof body.value_json !== "object" || body.value_json === null) {
      return NextResponse.json({ error: "value_json object required for this claim" }, { status: 400 });
    }
    valueJson = body.value_json;
  }

  const pageRows = await q<{ id: number }>(`SELECT id FROM v2.page WHERE id = $1`, [page_id]);
  if (!pageRows[0]) {
    return NextResponse.json({ error: "no v2.page row for that page_id" }, { status: 404 });
  }

  // Find any existing binding decision for the same target+claim that is not
  // already superseded — walk the supersession graph rather than trusting a
  // single "latest row" (append-only + explicit supersession, SCHEMA_V2.md §4).
  const priorRows = await q<{ id: number }>(
    `SELECT hd.id FROM v2.human_decision hd
     WHERE hd.target_type = 'page' AND hd.target_id = $1 AND hd.claim = $2
       AND hd.binding = TRUE
       AND NOT EXISTS (
         SELECT 1 FROM v2.decision_relation dr
         WHERE dr.relation = 'supersedes' AND dr.to_decision_id = hd.id
       )
     ORDER BY hd.decided_at DESC`,
    [page_id, claim]
  );

  const insertRows = await q<{ id: number }>(
    `INSERT INTO v2.human_decision
        (target_type, target_id, claim, value_json, actor_type, actor_id, binding, taxonomy_version, note)
     VALUES ('page', $1, $2, $3::jsonb, 'human', $4, TRUE, 'v2.0', $5)
     RETURNING id`,
    [page_id, claim, JSON.stringify(valueJson), actor_id, note]
  );
  const newDecisionId = insertRows[0].id;

  let supersededId: number | null = null;
  if (priorRows.length) {
    supersededId = priorRows[0].id;
    await q(
      `INSERT INTO v2.decision_relation (from_decision_id, to_decision_id, relation, actor_type, actor_id)
       VALUES ($1, $2, 'supersedes', 'human', $3)
       ON CONFLICT (from_decision_id, to_decision_id, relation) DO NOTHING`,
      [newDecisionId, supersededId, actor_id]
    );
  }

  return NextResponse.json({ decision_id: newDecisionId, superseded_decision_id: supersededId });
}
