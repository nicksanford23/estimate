import { NextResponse } from "next/server";
import { q } from "@/lib/db";

// Quick-label shortcut for the Ops Pages tab. INSERT-only into
// estimate.page_label (append-only — never UPDATE/DELETE, see CLAUDE.md).
// This is a fast-labeling path, not the full agent labeling schema: it only
// records category/keep/confidence, leaving sheet_title/scale_visible/etc
// NULL/0.
const CATEGORIES = new Set([
  "floor_plan",
  "finish_plan",
  "finish_schedule",
  "demo_plan",
  "reflected_ceiling",
  "furniture_plan",
  "site_plan",
  "elevation_section",
  "detail",
  "schedule_other",
  "structural",
  "mep",
  "life_safety",
  "cover_index",
  "specs_notes",
  "other",
]);

const KEEP_CATEGORIES = new Set(["floor_plan", "finish_plan", "finish_schedule", "demo_plan"]);

export async function POST(req: Request) {
  let body: { doc_id?: string; page?: number; category?: string; permit?: string; note?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const { doc_id, page, category, permit, note } = body;
  if (typeof doc_id !== "string" || !/^\d+$/.test(doc_id)) {
    return NextResponse.json({ error: "doc_id must be a numeric string" }, { status: 400 });
  }
  if (typeof page !== "number" || !Number.isInteger(page) || page < 0) {
    return NextResponse.json({ error: "page must be a non-negative integer (0-indexed)" }, { status: 400 });
  }
  if (typeof category !== "string" || !CATEGORIES.has(category)) {
    return NextResponse.json({ error: "category not in the 16-slug taxonomy" }, { status: 400 });
  }

  const docRows = await q<{ id: number }>(
    permit
      ? `SELECT id FROM estimate.document WHERE onestop_doc_id::text = $1 AND permit_num = $2 LIMIT 1`
      : `SELECT id FROM estimate.document WHERE onestop_doc_id::text = $1 LIMIT 1`,
    permit ? [doc_id, permit] : [doc_id]
  );
  const documentId = docRows[0]?.id;
  if (documentId == null) {
    return NextResponse.json({ error: "no estimate.document row for that doc_id/permit" }, { status: 404 });
  }

  const pageRows = await q<{ id: number }>(
    `SELECT id FROM estimate.page WHERE document_id = $1 AND page_index = $2 LIMIT 1`,
    [documentId, page]
  );
  const pageId = pageRows[0]?.id;
  if (pageId == null) {
    return NextResponse.json({ error: "no estimate.page row for that document/page_index" }, { status: 404 });
  }

  const keep = KEEP_CATEGORIES.has(category) ? 1 : 0;
  // page_label has no dedicated "notes" column — evidence is the closest
  // free-text field, so an optional UI note (e.g. smoke-test marker) rides
  // along there, appended to the default note.
  const evidence = note && typeof note === "string" && note.trim()
    ? `labeled via ops UI; note: ${note.trim()}`
    : "labeled via ops UI";
  const inserted = await q<{ id: number; page_id: number; category: string; keep: number }>(
    `INSERT INTO estimate.page_label (page_id, source, category, keep, confidence, evidence)
     VALUES ($1, 'nick_ui', $2, $3, 1.0, $4)
     RETURNING id, page_id, category, keep`,
    [pageId, category, keep, evidence]
  );

  return NextResponse.json({ ok: true, label: inserted[0] });
}
