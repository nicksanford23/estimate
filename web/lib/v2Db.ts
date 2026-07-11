import { q } from "./db";
export { TAXONOMY_V2 } from "./v2Taxonomy";

// Thin Page Review on V2 (slice S1). Reads v2.* identity/claims tables and
// joins back to legacy estimate.document.id ONLY to reuse the existing
// /api/thumb and /api/opspage image routes (they key on the legacy numeric
// document id, not onestop_doc_id).

export type BuildingListRow = {
  building_id: number;
  building_name: string;
  permit_num: string;
  page_count: number;
  doc_count: number;
};

export async function listPilotBuildings(): Promise<BuildingListRow[]> {
  return q<BuildingListRow>(
    `SELECT b.id AS building_id, b.name AS building_name, p.permit_num,
            COUNT(DISTINCT pg.id)::int AS page_count,
            COUNT(DISTINCT d.id)::int AS doc_count
     FROM v2.building b
     JOIN v2.permit_building pb ON pb.building_id = b.id
     JOIN v2.permit p ON p.id = pb.permit_id
     LEFT JOIN v2.document d ON d.permit_id = p.id
     LEFT JOIN v2.page pg ON pg.document_id = d.id
     GROUP BY b.id, b.name, p.permit_num
     ORDER BY b.id`
  );
}

export type V2PageRow = {
  page_id: number;
  pdf_page_index: number;
  document_id: number;
  onestop_doc_id: string;
  filename: string | null;
  legacy_doc_id: number | null; // for /api/thumb, /api/opspage
  sheet_title: string | null;
  claimed_category: string | null;
  claimed_source: string | null;
  binding_category: string | null;
  binding_decision_id: number | null;
};

export async function getBuildingDetail(permit: string) {
  const permitRows = await q<{ id: number; permit_num: string }>(
    `SELECT id, permit_num FROM v2.permit WHERE permit_num = $1`,
    [permit]
  );
  const permitRow = permitRows[0];
  if (!permitRow) return null;

  const buildingRows = await q<{ building_id: number; building_name: string }>(
    `SELECT b.id AS building_id, b.name AS building_name
     FROM v2.building b JOIN v2.permit_building pb ON pb.building_id = b.id
     WHERE pb.permit_id = $1 LIMIT 1`,
    [permitRow.id]
  );
  const building = buildingRows[0] ?? null;

  const docs = await q<{ document_id: number; onestop_doc_id: string; filename: string | null }>(
    `SELECT id AS document_id, onestop_doc_id::text AS onestop_doc_id, filename
     FROM v2.document WHERE permit_id = $1 ORDER BY id`,
    [permitRow.id]
  );

  // legacy estimate.document.id, keyed by onestop_doc_id — for image routes
  const legacyRows = await q<{ onestop_doc_id: string; legacy_id: number }>(
    `SELECT onestop_doc_id::text AS onestop_doc_id, id AS legacy_id
     FROM estimate.document WHERE permit_num = $1`,
    [permit]
  );
  const legacyByOnestop = new Map(legacyRows.map((r) => [r.onestop_doc_id, r.legacy_id]));

  const docIds = docs.map((d) => d.document_id);
  const pages = docIds.length
    ? await q<{ page_id: number; document_id: number; pdf_page_index: number }>(
        `SELECT id AS page_id, document_id, pdf_page_index FROM v2.page WHERE document_id = ANY($1) ORDER BY document_id, pdf_page_index`,
        [docIds]
      )
    : [];
  const pageIds = pages.map((p) => p.page_id);

  const catObs = pageIds.length
    ? await q<{ target_id: number; value_json: { category?: string }; source: string; created_at: string }>(
        `SELECT target_id, value_json, source, created_at::text FROM v2.machine_observation
         WHERE target_type = 'page' AND claim = 'page_category' AND target_id = ANY($1)
         ORDER BY created_at DESC`,
        [pageIds]
      )
    : [];
  const titleObs = pageIds.length
    ? await q<{ target_id: number; value_json: { title?: string } }>(
        `SELECT target_id, value_json FROM v2.machine_observation
         WHERE target_type = 'page' AND claim = 'sheet_title' AND target_id = ANY($1)
         ORDER BY created_at DESC`,
        [pageIds]
      )
    : [];
  const bindingDecisions = pageIds.length
    ? await q<{ id: number; target_id: number; value_json: { category?: string } }>(
        `SELECT id, target_id, value_json FROM v2.human_decision
         WHERE target_type = 'page' AND claim = 'page_category' AND target_id = ANY($1)
           AND binding = TRUE
         ORDER BY decided_at DESC`,
        [pageIds]
      )
    : [];
  const supersededIds = pageIds.length
    ? new Set(
        (
          await q<{ to_decision_id: number }>(
            `SELECT dr.to_decision_id FROM v2.decision_relation dr
             JOIN v2.human_decision hd ON hd.id = dr.to_decision_id
             WHERE dr.relation = 'supersedes' AND hd.target_id = ANY($1) AND hd.target_type = 'page' AND hd.claim = 'page_category'`,
            [pageIds]
          )
        ).map((r) => r.to_decision_id)
      )
    : new Set<number>();

  const firstCatByPage = new Map<number, { category: string | null; source: string }>();
  for (const o of catObs) {
    if (!firstCatByPage.has(o.target_id)) {
      firstCatByPage.set(o.target_id, { category: o.value_json?.category ?? null, source: o.source });
    }
  }
  const firstTitleByPage = new Map<number, string | null>();
  for (const o of titleObs) {
    if (!firstTitleByPage.has(o.target_id)) {
      firstTitleByPage.set(o.target_id, o.value_json?.title ?? null);
    }
  }
  const bindingByPage = new Map<number, { id: number; category: string | null }>();
  for (const d of bindingDecisions) {
    if (supersededIds.has(d.id)) continue;
    if (!bindingByPage.has(d.target_id)) {
      bindingByPage.set(d.target_id, { id: d.id, category: d.value_json?.category ?? null });
    }
  }

  const docsWithPages = docs.map((d) => {
    const legacyDocId = legacyByOnestop.get(d.onestop_doc_id) ?? null;
    const docPages: V2PageRow[] = pages
      .filter((p) => p.document_id === d.document_id)
      .map((p) => {
        const claim = firstCatByPage.get(p.page_id);
        const binding = bindingByPage.get(p.page_id);
        return {
          page_id: p.page_id,
          pdf_page_index: p.pdf_page_index,
          document_id: p.document_id,
          onestop_doc_id: d.onestop_doc_id,
          filename: d.filename,
          legacy_doc_id: legacyDocId,
          sheet_title: firstTitleByPage.get(p.page_id) ?? null,
          claimed_category: claim?.category ?? null,
          claimed_source: claim?.source ?? null,
          binding_category: binding?.category ?? null,
          binding_decision_id: binding?.id ?? null,
        };
      });
    return { document_id: d.document_id, onestop_doc_id: d.onestop_doc_id, filename: d.filename, legacy_doc_id: legacyDocId, pages: docPages };
  });

  return { permit: permitRow.permit_num, building, docs: docsWithPages };
}
