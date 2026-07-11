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
  address_raw: string | null;
  city_description: string | null;
  city_sqft: number | null;
};

export async function listPilotBuildings(): Promise<BuildingListRow[]> {
  return q<BuildingListRow>(
    `SELECT b.id AS building_id, b.name AS building_name, p.permit_num,
            p.address_raw, p.city_description, p.city_sqft::float AS city_sqft,
            COUNT(DISTINCT pg.id)::int AS page_count,
            COUNT(DISTINCT d.id)::int AS doc_count
     FROM v2.building b
     JOIN v2.permit_building pb ON pb.building_id = b.id
     JOIN v2.permit p ON p.id = pb.permit_id
     LEFT JOIN v2.document d ON d.permit_id = p.id
     LEFT JOIN v2.page pg ON pg.document_id = d.id
     GROUP BY b.id, b.name, p.permit_num, p.address_raw, p.city_description, p.city_sqft
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
  flags: string[];
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

  const docs = await q<{ document_id: number; onestop_doc_id: string; filename: string | null; filed_date: string | null }>(
    `SELECT id AS document_id, onestop_doc_id::text AS onestop_doc_id, filename, filed_date::text AS filed_date
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
  // Flags are toggled from the page-review side panel and stored the same
  // way as page_category (append-only human_decision, binding=TRUE, no
  // supersession bookkeeping needed since we only ever read the latest
  // per-page flag set). Legacy eyeball_verdicts-imported page_flags rows use
  // a different value_json shape ({verdict, is_floor_plan, ...}) and are
  // simply skipped here since they carry no `flags` array.
  const flagDecisions = pageIds.length
    ? await q<{ target_id: number; value_json: { flags?: string[] }; decided_at: string }>(
        `SELECT target_id, value_json, decided_at::text FROM v2.human_decision
         WHERE target_type = 'page' AND claim = 'page_flags' AND target_id = ANY($1)
         ORDER BY decided_at DESC`,
        [pageIds]
      )
    : [];
  const flagsByPage = new Map<number, string[]>();
  for (const d of flagDecisions) {
    if (!flagsByPage.has(d.target_id) && Array.isArray(d.value_json?.flags)) {
      flagsByPage.set(d.target_id, d.value_json.flags!);
    }
  }

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
          flags: flagsByPage.get(p.page_id) ?? [],
        };
      });
    return {
      document_id: d.document_id,
      onestop_doc_id: d.onestop_doc_id,
      filename: d.filename,
      filed_date: d.filed_date,
      legacy_doc_id: legacyDocId,
      pages: docPages,
    };
  });

  return { permit: permitRow.permit_num, building, docs: docsWithPages };
}

// ---------------------------------------------------------------------
// Rooms & Finishes (S2, design_specs/rooms_finishes_APPROVED.png)
// ---------------------------------------------------------------------

export type ScheduleRowOut = {
  schedule_row_id: number;
  row_index: number;
  raw: Record<string, unknown>;
  confirmed: boolean;
  decision_id: number | null;
};

export type RoomsFinishesData = {
  permit: string;
  building: { building_name: string } | null;
  region_id: number | null;
  legacy_doc_id: number | null;
  pdf_page_index: number | null;
  sheet: string | null;
  printed_total_sf: number | null;
  extracted_total_sf: number;
  rows: ScheduleRowOut[];
} | null;

export async function getRoomsFinishes(permit: string): Promise<RoomsFinishesData> {
  const permitRows = await q<{ id: number }>(`SELECT id FROM v2.permit WHERE permit_num = $1`, [permit]);
  const permitRow = permitRows[0];
  if (!permitRow) return null;

  const buildingRows = await q<{ building_name: string }>(
    `SELECT b.name AS building_name FROM v2.building b
     JOIN v2.permit_building pb ON pb.building_id = b.id WHERE pb.permit_id = $1 LIMIT 1`,
    [permitRow.id]
  );
  const building = buildingRows[0] ?? null;

  // Most recent schedule_table region for this permit's documents (pilot:
  // one schedule page per building backfilled from data/triage/truth_area).
  const regionRows = await q<{
    region_id: number;
    page_id: number;
    document_id: number;
    onestop_doc_id: string;
    pdf_page_index: number;
    legacy_doc_id: number | null;
  }>(
    `SELECT r.id AS region_id, pg.id AS page_id, d.id AS document_id, d.onestop_doc_id::text AS onestop_doc_id,
            pg.pdf_page_index,
            (SELECT ed.id FROM estimate.document ed WHERE ed.permit_num = $1 AND ed.onestop_doc_id::text = d.onestop_doc_id::text LIMIT 1) AS legacy_doc_id
     FROM v2.region r
     JOIN v2.page pg ON pg.id = r.page_id
     JOIN v2.document d ON d.id = pg.document_id
     WHERE d.permit_id = $2 AND r.kind = 'schedule_table'
     ORDER BY r.id DESC LIMIT 1`,
    [permit, permitRow.id]
  );
  const region = regionRows[0] ?? null;
  if (!region) {
    return { permit, building, region_id: null, legacy_doc_id: null, pdf_page_index: null, sheet: null, printed_total_sf: null, extracted_total_sf: 0, rows: [] };
  }

  const extRows = await q<{ id: number; manifest_json: { sheet?: string; printed_total_sf?: number } }>(
    `SELECT id, manifest_json FROM v2.extraction WHERE page_id = $1 AND tier = 'semantic' ORDER BY id DESC LIMIT 1`,
    [region.page_id]
  );
  const ext = extRows[0] ?? null;

  const rows = await q<{ id: number; row_index: number; raw_values_json: Record<string, unknown> }>(
    `SELECT id, row_index, raw_values_json FROM v2.schedule_row WHERE region_id = $1 ORDER BY row_index`,
    [region.region_id]
  );

  const confirmDecisions = rows.length
    ? await q<{ id: number; target_id: number }>(
        `SELECT hd.id, hd.target_id FROM v2.human_decision hd
         WHERE hd.target_type = 'schedule_row' AND hd.claim = 'schedule_row_confirm'
           AND hd.target_id = ANY($1) AND hd.binding = TRUE
           AND NOT EXISTS (SELECT 1 FROM v2.decision_relation dr WHERE dr.relation = 'supersedes' AND dr.to_decision_id = hd.id)
         ORDER BY hd.decided_at DESC`,
        [rows.map((r) => r.id)]
      )
    : [];
  const confirmedByRow = new Map<number, number>();
  for (const d of confirmDecisions) if (!confirmedByRow.has(d.target_id)) confirmedByRow.set(d.target_id, d.id);

  const out: ScheduleRowOut[] = rows.map((r) => ({
    schedule_row_id: r.id,
    row_index: r.row_index,
    raw: r.raw_values_json,
    confirmed: confirmedByRow.has(r.id),
    decision_id: confirmedByRow.get(r.id) ?? null,
  }));

  const extractedTotal = out.reduce((sum, r) => sum + (Number(r.raw.area_sf) || 0), 0);

  return {
    permit,
    building,
    region_id: region.region_id,
    legacy_doc_id: region.legacy_doc_id,
    pdf_page_index: region.pdf_page_index,
    sheet: ext?.manifest_json?.sheet ?? null,
    printed_total_sf: ext?.manifest_json?.printed_total_sf ?? null,
    extracted_total_sf: extractedTotal,
    rows: out,
  };
}

// ---------------------------------------------------------------------
// Geometry Review (S3, design_specs/geometry_review_APPROVED.png)
// ---------------------------------------------------------------------

export type PolyOut = {
  polygon_prediction_id: number;
  poly_index: number | null;
  room: string | null;
  area_sf: number | null;
  product_action: string | null;
  flags: string[];
  confidence: string | null;
  material: string | null;
  verdict: string | null;
  verdict_decision_id: number | null;
};

export type GeometryRunOut = {
  run_id: number;
  region_id: number;
  run_no: number;
  legacy_doc_id: number | null;
  onestop_doc_id: string | null;
  pdf_page_index: number | null;
  sheet_title: string | null;
  scale_text: string | null;
  overlay_path: string | null;
  summary: { n_auto?: number; n_review?: number; n_open?: number; total_sf?: number } | null;
  region_verdict: string | null;
  region_verdict_decision_id: number | null;
  run_verdict: string | null;
  run_verdict_decision_id: number | null;
  polys: PolyOut[];
};

export type GeometryReviewData = {
  permit: string;
  building: { building_name: string } | null;
  runs: GeometryRunOut[];
};

export async function getGeometryReview(permit: string): Promise<GeometryReviewData | null> {
  const permitRows = await q<{ id: number }>(`SELECT id FROM v2.permit WHERE permit_num = $1`, [permit]);
  const permitRow = permitRows[0];
  if (!permitRow) return null;

  const buildingRows = await q<{ building_name: string }>(
    `SELECT b.name AS building_name FROM v2.building b
     JOIN v2.permit_building pb ON pb.building_id = b.id WHERE pb.permit_id = $1 LIMIT 1`,
    [permitRow.id]
  );
  const building = buildingRows[0] ?? null;

  const runRows = await q<{
    run_id: number;
    region_id: number;
    run_no: number;
    manifest_json: {
      sheet_title?: string;
      scale_text?: string;
      overlay_path?: string;
      summary?: { n_auto?: number; n_review?: number; n_open?: number; total_sf?: number };
      onestop_doc_id?: string;
      pdf_page_index?: number;
    };
  }>(
    `SELECT gr.id AS run_id, gr.region_id, gr.run_no, gr.manifest_json
     FROM v2.geometry_run gr
     JOIN v2.region r ON r.id = gr.region_id
     JOIN v2.page pg ON pg.id = r.page_id
     JOIN v2.document d ON d.id = pg.document_id
     WHERE d.permit_id = $1
     ORDER BY gr.id`,
    [permitRow.id]
  );
  if (!runRows.length) return { permit, building, runs: [] };

  const legacyRows = await q<{ onestop_doc_id: string; legacy_id: number }>(
    `SELECT onestop_doc_id::text AS onestop_doc_id, id AS legacy_id FROM estimate.document WHERE permit_num = $1`,
    [permit]
  );
  const legacyByOnestop = new Map(legacyRows.map((r) => [r.onestop_doc_id, r.legacy_id]));

  const runIds = runRows.map((r) => r.run_id);
  const regionIds = [...new Set(runRows.map((r) => r.region_id))];

  const polyRows = await q<{
    id: number;
    run_id: number;
    geom_json: { poly_index?: number };
    label_match: string | null;
    area_sf: number | null;
    product_action: string | null;
    flags: { flags?: string[]; confidence?: string | null; material?: string | null };
  }>(
    `SELECT id, run_id, geom_json, label_match, area_sf::float AS area_sf, product_action, flags
     FROM v2.polygon_prediction WHERE run_id = ANY($1) ORDER BY id`,
    [runIds]
  );

  const verdictDecisions = polyRows.length
    ? await q<{ id: number; target_id: number; value_json: { value?: string } | string }>(
        `SELECT hd.id, hd.target_id, hd.value_json FROM v2.human_decision hd
         WHERE hd.target_type = 'polygon_prediction' AND hd.claim = 'room_verdict'
           AND hd.target_id = ANY($1) AND hd.binding = TRUE
           AND NOT EXISTS (SELECT 1 FROM v2.decision_relation dr WHERE dr.relation = 'supersedes' AND dr.to_decision_id = hd.id)
         ORDER BY hd.decided_at DESC`,
        [polyRows.map((p) => p.id)]
      )
    : [];
  const verdictByPoly = new Map<number, { verdict: string; decisionId: number }>();
  for (const d of verdictDecisions) {
    if (verdictByPoly.has(d.target_id)) continue;
    const v = typeof d.value_json === "string" ? d.value_json : (d.value_json as { verdict?: string })?.verdict;
    if (v) verdictByPoly.set(d.target_id, { verdict: v, decisionId: d.id });
  }

  const regionVerdictRows = await q<{ id: number; target_id: number; value_json: { verdict?: string } }>(
    `SELECT hd.id, hd.target_id, hd.value_json FROM v2.human_decision hd
     WHERE hd.target_type = 'region' AND hd.claim = 'region_geometry_verdict'
       AND hd.target_id = ANY($1) AND hd.binding = TRUE
       AND NOT EXISTS (SELECT 1 FROM v2.decision_relation dr WHERE dr.relation = 'supersedes' AND dr.to_decision_id = hd.id)
     ORDER BY hd.decided_at DESC`,
    [regionIds]
  );
  const regionVerdictByRegion = new Map<number, { verdict: string; decisionId: number }>();
  for (const d of regionVerdictRows) {
    if (regionVerdictByRegion.has(d.target_id)) continue;
    if (d.value_json?.verdict) regionVerdictByRegion.set(d.target_id, { verdict: d.value_json.verdict, decisionId: d.id });
  }

  const runVerdictRows = await q<{ id: number; target_id: number; value_json: { verdict?: string } }>(
    `SELECT hd.id, hd.target_id, hd.value_json FROM v2.human_decision hd
     WHERE hd.target_type = 'geometry_run' AND hd.claim = 'run_verdict'
       AND hd.target_id = ANY($1) AND hd.binding = TRUE
       AND NOT EXISTS (SELECT 1 FROM v2.decision_relation dr WHERE dr.relation = 'supersedes' AND dr.to_decision_id = hd.id)
     ORDER BY hd.decided_at DESC`,
    [runIds]
  );
  const runVerdictByRun = new Map<number, { verdict: string; decisionId: number }>();
  for (const d of runVerdictRows) {
    if (runVerdictByRun.has(d.target_id)) continue;
    if (d.value_json?.verdict) runVerdictByRun.set(d.target_id, { verdict: d.value_json.verdict, decisionId: d.id });
  }

  const runs: GeometryRunOut[] = runRows.map((r) => {
    const onestop = r.manifest_json?.onestop_doc_id ?? null;
    const polys = polyRows
      .filter((p) => p.run_id === r.run_id)
      .map((p) => {
        const v = verdictByPoly.get(p.id);
        return {
          polygon_prediction_id: p.id,
          poly_index: p.geom_json?.poly_index ?? null,
          room: p.label_match,
          area_sf: p.area_sf,
          product_action: p.product_action,
          flags: p.flags?.flags ?? [],
          confidence: p.flags?.confidence ?? null,
          material: p.flags?.material ?? null,
          verdict: v?.verdict ?? null,
          verdict_decision_id: v?.decisionId ?? null,
        };
      });
    const rv = regionVerdictByRegion.get(r.region_id);
    const runv = runVerdictByRun.get(r.run_id);
    return {
      run_id: r.run_id,
      region_id: r.region_id,
      run_no: r.run_no,
      legacy_doc_id: onestop ? legacyByOnestop.get(onestop) ?? null : null,
      onestop_doc_id: onestop,
      pdf_page_index: r.manifest_json?.pdf_page_index ?? null,
      sheet_title: r.manifest_json?.sheet_title ?? null,
      scale_text: r.manifest_json?.scale_text ?? null,
      overlay_path: r.manifest_json?.overlay_path ?? null,
      summary: r.manifest_json?.summary ?? null,
      region_verdict: rv?.verdict ?? null,
      region_verdict_decision_id: rv?.decisionId ?? null,
      run_verdict: runv?.verdict ?? null,
      run_verdict_decision_id: runv?.decisionId ?? null,
      polys,
    };
  });

  return { permit, building, runs };
}
