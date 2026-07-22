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
  let body: {
    page_id?: number;
    target_id?: number;
    target_type?: string;
    category?: string;
    claim?: string;
    value_json?: unknown;
    actor_id?: string;
    note?: string;
    binding?: boolean;
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const { category } = body;
  // Default claim stays 'page_category' for back-compat with the original
  // caller shape; page_flags (and any future claim) reuses the same
  // append-only insert + supersession-walk so the flags toggles in the
  // page-review side panel can POST here too (SCHEMA_V2.md §14).
  const claim = typeof body.claim === "string" && body.claim ? body.claim : "page_category";
  const actor_id = typeof body.actor_id === "string" && body.actor_id ? body.actor_id : "nick";
  const note = typeof body.note === "string" ? body.note : null;
  // binding defaults to TRUE (a real human decision = truth). A caller may pass
  // binding:false to record a NON-binding marker — e.g. the "trusted" breadcrumb
  // (claim='page_review_status') where the human defers to the machine without
  // making it truth. Non-binding rows never supersede a binding decision.
  const binding = body.binding !== false;
  // target_type/target_id generalize this route beyond 'page' (Rooms &
  // Finishes posts schedule_row_confirm against schedule_row; Geometry
  // Review posts room_verdict against polygon_prediction and
  // region_geometry_verdict/run_verdict against region/geometry_run) — same
  // append-only insert + supersession-walk, just a different target table.
  // `page_id` stays the back-compat alias for target_type='page'.
  const target_type = typeof body.target_type === "string" && body.target_type ? body.target_type : "page";
  const rawTarget = target_type === "page" ? body.page_id : body.target_id;

  // v2 primary keys are bigint; node-postgres returns bigint columns as
  // strings, so the browser holds (and sends) page_id/target_id as a numeric
  // string like "224". Accept both string and number, validate as a positive
  // integer, and keep it as a STRING for the parameterized query so large
  // bigints never lose precision through JS number.
  const targetStr = typeof rawTarget === "number" ? String(rawTarget) : rawTarget;
  // /^[1-9][0-9]*$/ = a positive integer with no leading zero — rejects "0",
  // "", negatives, and floats without needing BigInt (project target < ES2020).
  if (typeof targetStr !== "string" || !/^[1-9][0-9]*$/.test(targetStr)) {
    return NextResponse.json({ error: "target_id (or page_id) must be a positive integer" }, { status: 400 });
  }
  const target_id = targetStr;

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

  const tableByType: Record<string, string> = {
    page: "v2.page",
    schedule_row: "v2.schedule_row",
    polygon_prediction: "v2.polygon_prediction",
    region: "v2.region",
    geometry_run: "v2.geometry_run",
    space: "v2.space",
  };
  const table = tableByType[target_type];
  if (!table) {
    return NextResponse.json({ error: `unsupported target_type '${target_type}'` }, { status: 400 });
  }
  const targetRows = await q<{ id: number }>(`SELECT id FROM ${table} WHERE id = $1`, [target_id]);
  if (!targetRows[0]) {
    return NextResponse.json({ error: `no ${table} row for that target_id` }, { status: 404 });
  }

  // Find any existing binding decision for the same target+claim that is not
  // already superseded — walk the supersession graph rather than trusting a
  // single "latest row" (append-only + explicit supersession, SCHEMA_V2.md §4).
  // Only binding decisions participate in supersession; a non-binding marker
  // (trusted breadcrumb) neither supersedes nor is superseded.
  const priorRows = binding
    ? await q<{ id: number }>(
        `SELECT hd.id FROM v2.human_decision hd
         WHERE hd.target_type = $1 AND hd.target_id = $2 AND hd.claim = $3
           AND hd.binding = TRUE
           AND NOT EXISTS (
             SELECT 1 FROM v2.decision_relation dr
             WHERE dr.relation = 'supersedes' AND dr.to_decision_id = hd.id
           )
         ORDER BY hd.decided_at DESC`,
        [target_type, target_id, claim]
      )
    : [];

  const insertRows = await q<{ id: number }>(
    `INSERT INTO v2.human_decision
        (target_type, target_id, claim, value_json, actor_type, actor_id, binding, taxonomy_version, note)
     VALUES ($1, $2, $3, $4::jsonb, 'human', $5, $6, 'v2.0', $7)
     RETURNING id`,
    [target_type, target_id, claim, JSON.stringify(valueJson), actor_id, binding, note]
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
