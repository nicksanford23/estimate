import { q } from "./db";

export type DiscoveryProgress = {
  discoveredPermits: number;
  latestRun: {
    run_id: number;
    pod_id: string;
    started_at: string;
    ended_at: string | null;
    final_state: string;
    settled: number | null;
    docs: number | null;
    note: string | null;
  } | null;
};

// estimate.discovered_docs / estimate.discovery_runs — the one-time full
// enumeration crawl (SELECT only, per CLAUDE.md).
export async function getDiscoveryProgress(): Promise<DiscoveryProgress> {
  const [{ n }] = await q<{ n: number }>(
    `SELECT COUNT(DISTINCT permit_num)::int n FROM estimate.discovered_docs`
  );
  const runs = await q<DiscoveryProgress["latestRun"] & Record<string, unknown>>(
    `SELECT run_id, pod_id, started_at::text, ended_at::text, final_state, settled, docs, note
     FROM estimate.discovery_runs ORDER BY run_id DESC LIMIT 1`
  );
  return { discoveredPermits: n, latestRun: runs[0] ?? null };
}

export async function getPermitsUniverse(): Promise<number> {
  const [{ n }] = await q<{ n: number }>(`SELECT COUNT(*)::int n FROM estimate.permits`);
  return n;
}

// ---------------------------------------------- Permit Workbench queries ---

export type PermitRecord = {
  permit_num: string;
  address: string | null;
  description: string | null;
  cost: number | null;
  sqft: number | null;
  status: string | null;
  contractor: string | null;
};

export async function getPermitRecord(permit: string): Promise<PermitRecord | null> {
  const rows = await q<PermitRecord>(
    `SELECT permit_num, address, description, cost, sqft, status, contractor
     FROM estimate.permits WHERE permit_num = $1 LIMIT 1`,
    [permit]
  );
  return rows[0] ?? null;
}

export type DocInventoryRow = { doc_id: string; name: string | null };

// Full inventory of documents NOLA lists for this permit (Documents tab).
export async function getDocumentsInventory(permit: string): Promise<DocInventoryRow[]> {
  const rows = await q<{ doc_id: string; name: string | null }>(
    `SELECT doc_id::text AS doc_id, name FROM estimate.documents WHERE permit_num = $1 ORDER BY doc_id`,
    [permit]
  );
  return rows;
}

export type ProcessedDocRow = {
  id: number;
  onestop_doc_id: string;
  filename: string | null;
  page_count: number | null;
  downloaded_at: string | null;
};

// Docs actually downloaded/processed by the pipeline (estimate.document —
// singular). Joined to page_count via a subquery so it's honest even if the
// document.page_count column itself is stale/null.
export async function getProcessedDocuments(permit: string): Promise<ProcessedDocRow[]> {
  const rows = await q<ProcessedDocRow & { real_page_count: number }>(
    `SELECT d.id, d.onestop_doc_id::text AS onestop_doc_id, d.filename, d.page_count,
            d.downloaded_at,
            COUNT(p.id)::int AS real_page_count
     FROM estimate.document d
     LEFT JOIN estimate.page p ON p.document_id = d.id
     WHERE d.permit_num = $1
     GROUP BY d.id
     ORDER BY real_page_count DESC`,
    [permit]
  );
  return rows.map((r) => ({
    id: r.id,
    onestop_doc_id: r.onestop_doc_id,
    filename: r.filename,
    page_count: r.real_page_count || r.page_count,
    downloaded_at: r.downloaded_at,
  }));
}

// Honest "pages labeled" checklist number: distinct pages with >=1
// page_label row vs total pages, across all processed docs for this permit.
export async function getLabeledPageProgress(permit: string): Promise<{ labeled: number; total: number }> {
  const rows = await q<{ labeled: number; total: number }>(
    `SELECT COUNT(DISTINCT p.id) FILTER (WHERE pl.id IS NOT NULL)::int AS labeled,
            COUNT(DISTINCT p.id)::int AS total
     FROM estimate.page p
     JOIN estimate.document d ON d.id = p.document_id
     LEFT JOIN estimate.page_label pl ON pl.page_id = p.id
     WHERE d.permit_num = $1`,
    [permit]
  );
  return rows[0] ?? { labeled: 0, total: 0 };
}

export type PageLatestLabel = {
  page_id: number;
  document_id: number;
  page_index: number;
  category: string | null;
};

// Latest page_label row per page (or null category if never labeled), for
// every processed doc under this permit — one batched query, not N+1.
export async function getLatestLabelsForPermit(permit: string): Promise<PageLatestLabel[]> {
  const rows = await q<PageLatestLabel>(
    `SELECT DISTINCT ON (p.id) p.id AS page_id, p.document_id, p.page_index, pl.category
     FROM estimate.page p
     JOIN estimate.document d ON d.id = p.document_id
     LEFT JOIN estimate.page_label pl ON pl.page_id = p.id
     WHERE d.permit_num = $1
     ORDER BY p.id, pl.created_at DESC NULLS LAST, pl.id DESC NULLS LAST`,
    [permit]
  );
  return rows;
}
