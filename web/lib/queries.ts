import { q } from "./db";
import { r2Set } from "./r2";
import { KEEP_CATS } from "./labels";

export const CODE_LABEL: Record<string, string> = {
  NEWC: "New construction",
  RNVS: "Renovation · structural",
  RNVN: "Renovation · non-structural",
};

export type Funnel = {
  permitsTotal: number;
  permitsWithDocs: number;
  docsTotal: number;
  downloaded: number;
  renderedDocs: number;
  labeledDocs: number;
  labels: number;
};

export async function getFunnel(): Promise<Funnel> {
  const [permits] = await q<{ total: number; with_docs: number }>(
    `SELECT COUNT(*)::int total, COUNT(*) FILTER (WHERE doc_count > 0)::int with_docs
     FROM estimate.permits`
  );
  const [docs] = await q<{ total: number }>(
    `SELECT COUNT(*)::int total FROM estimate.documents`
  );
  const [rendered] = await q<{ docs: number }>(
    `SELECT COUNT(DISTINCT document_id)::int docs FROM estimate.page`
  );
  const [labeled] = await q<{ docs: number; labels: number }>(
    `SELECT COUNT(DISTINCT d.onestop_doc_id)::int docs, COUNT(*)::int labels
     FROM estimate.page_label pl
     JOIN estimate.page p ON p.id = pl.page_id
     JOIN estimate.document d ON d.id = p.document_id`
  );
  const r2 = await r2Set();
  return {
    permitsTotal: permits.total,
    permitsWithDocs: permits.with_docs,
    docsTotal: docs.total,
    downloaded: r2.size,
    renderedDocs: rendered.docs,
    labeledDocs: labeled.docs,
    labels: labeled.labels,
  };
}

export type CodeRow = {
  code: string;
  label: string;
  permits: number;
  downloadedDocs: number;
  downloadedPermits: number;
};

export async function getCodeBreakdown(): Promise<CodeRow[]> {
  const all = await q<{ code: string; permits: number }>(
    `SELECT code, COUNT(*)::int permits FROM estimate.permits GROUP BY code`
  );
  const ids = [...(await r2Set())];
  const dl = await q<{ code: string; docs: number; permits: number }>(
    `SELECT p.code, COUNT(*)::int docs, COUNT(DISTINCT d.permit_num)::int permits
     FROM estimate.documents d JOIN estimate.permits p ON p.permit_num = d.permit_num
     WHERE d.doc_id::text = ANY($1) GROUP BY p.code`,
    [ids]
  );
  const dlMap = new Map(dl.map((r) => [r.code, r]));
  return all
    .filter((r) => r.code)
    .map((r) => ({
      code: r.code,
      label: CODE_LABEL[r.code] ?? r.code,
      permits: r.permits,
      downloadedDocs: dlMap.get(r.code)?.docs ?? 0,
      downloadedPermits: dlMap.get(r.code)?.permits ?? 0,
    }))
    .sort((a, b) => b.downloadedDocs - a.downloadedDocs);
}

export type PermitRow = {
  permit_num: string;
  code: string | null;
  description: string | null;
  address: string | null;
  permit_class: string | null;
  contractor: string | null;
  sqft: number | null;
  doc_count: number | null;
  downloaded: number;
};

export type PermitListParams = {
  code?: string;
  pclass?: string;
  search?: string;
  onlyDownloaded?: boolean;
  onlyLabeled?: boolean;
  page?: number;
  pageSize?: number;
};

// permits that have at least one labeled document (cached)
let _labeledPermits: Set<string> | null = null;
let _lpTs = 0;
export async function labeledPermitSet(): Promise<Set<string>> {
  if (_labeledPermits && Date.now() - _lpTs < 5 * 60 * 1000) return _labeledPermits;
  const rows = await q<{ permit_num: string }>(
    `SELECT DISTINCT dd.permit_num
     FROM estimate.documents dd
     WHERE dd.doc_id::text IN (
       SELECT DISTINCT d.onestop_doc_id::text
       FROM estimate.page_label pl
       JOIN estimate.page p ON p.id = pl.page_id
       JOIN estimate.document d ON d.id = p.document_id
     )`
  );
  _labeledPermits = new Set(rows.map((r) => r.permit_num));
  _lpTs = Date.now();
  return _labeledPermits;
}

export async function listPermits(params: PermitListParams) {
  const pageSize = params.pageSize ?? 30;
  const page = Math.max(1, params.page ?? 1);
  const where: string[] = [];
  const args: unknown[] = [];
  if (params.code) {
    args.push(params.code);
    where.push(`code = $${args.length}`);
  }
  if (params.pclass) {
    args.push(params.pclass);
    where.push(`permit_class = $${args.length}`);
  }
  if (params.search) {
    args.push(`%${params.search}%`);
    const i = args.length;
    where.push(
      `(permit_num ILIKE $${i} OR description ILIKE $${i} OR address ILIKE $${i} OR contractor ILIKE $${i})`
    );
  }
  if (params.onlyDownloaded) where.push(`doc_count > 0`);
  if (params.onlyLabeled) {
    args.push([...(await labeledPermitSet())]);
    where.push(`permit_num = ANY($${args.length})`);
  }
  const clause = where.length ? `WHERE ${where.join(" AND ")}` : "";

  const [{ total }] = await q<{ total: number }>(
    `SELECT COUNT(*)::int total FROM estimate.permits ${clause}`,
    args
  );
  const rows = await q<PermitRow>(
    `SELECT permit_num, code, description, address, permit_class, contractor, sqft, doc_count
     FROM estimate.permits ${clause}
     ORDER BY doc_count DESC NULLS LAST, permit_num
     LIMIT ${pageSize} OFFSET ${(page - 1) * pageSize}`,
    args
  );

  // downloaded-doc count per visible permit
  const nums = rows.map((r) => r.permit_num);
  const dlByPermit = new Map<string, number>();
  if (nums.length) {
    const r2 = await r2Set();
    const docs = await q<{ permit_num: string; doc_id: string }>(
      `SELECT permit_num, doc_id::text FROM estimate.documents WHERE permit_num = ANY($1)`,
      [nums]
    );
    for (const d of docs) {
      if (r2.has(d.doc_id))
        dlByPermit.set(d.permit_num, (dlByPermit.get(d.permit_num) ?? 0) + 1);
    }
  }
  for (const r of rows) r.downloaded = dlByPermit.get(r.permit_num) ?? 0;

  return { rows, total, page, pageSize, pages: Math.ceil(total / pageSize) };
}

export async function getPermitClasses(): Promise<string[]> {
  const rows = await q<{ permit_class: string }>(
    `SELECT DISTINCT permit_class FROM estimate.permits
     WHERE COALESCE(TRIM(permit_class),'') <> '' ORDER BY permit_class`
  );
  return rows.map((r) => r.permit_class);
}

export type DocRow = {
  doc_id: string;
  name: string | null;
  downloaded: boolean;
  rendered: boolean;
  labeled: boolean;
  pages: number;
};

export type LabeledPage = {
  pi: number;
  cat: string;
  keep: boolean;
  conf: number;
  title: string | null;
  scale: boolean;
  table: boolean;
  codes: boolean;
  rooms: boolean;
  dims: boolean;
};

export async function getLabeledDoc(docId: string) {
  const [doc] = await q<{ permit_num: string; name: string | null }>(
    `SELECT permit_num, name FROM estimate.documents WHERE doc_id::text = $1 LIMIT 1`,
    [docId]
  );
  const rows = await q<Record<string, unknown>>(
    `SELECT DISTINCT ON (p.id)
        p.page_index pi, pl.category cat, pl.keep keep, pl.confidence conf,
        pl.sheet_title title, pl.scale_visible sc, pl.table_present tb,
        pl.finish_codes_visible fc, pl.room_labels_visible rl, pl.dimensions_visible dm
     FROM estimate.page p
     JOIN estimate.document d ON d.id = p.document_id
     JOIN estimate.page_label pl ON pl.page_id = p.id
     WHERE d.onestop_doc_id::text = $1
     ORDER BY p.id, pl.confidence DESC`,
    [docId]
  );
  const num = (v: unknown) => Number(v) === 1;
  const pages: LabeledPage[] = rows
    .map((r) => ({
      pi: Number(r.pi),
      cat: String(r.cat),
      // derive keep from category (the stored keep flag is inconsistent)
      keep: KEEP_CATS.has(String(r.cat)),
      conf: Number(r.conf),
      title: (r.title as string) ?? null,
      scale: num(r.sc),
      table: num(r.tb),
      codes: num(r.fc),
      rooms: num(r.rl),
      dims: num(r.dm),
    }))
    .sort((a, b) => a.pi - b.pi);
  return {
    docId,
    permit: doc?.permit_num ?? null,
    name: doc?.name ?? null,
    pages,
  };
}

export async function getPageImagePath(
  docId: string,
  pageIndex: number
): Promise<string | null> {
  const [r] = await q<{ image_path: string }>(
    `SELECT p.image_path FROM estimate.page p
     JOIN estimate.document d ON d.id = p.document_id
     WHERE d.onestop_doc_id::text = $1 AND p.page_index = $2 LIMIT 1`,
    [docId, pageIndex]
  );
  return r?.image_path ?? null;
}

export async function getPermit(permitNum: string) {
  const [permit] = await q<Record<string, unknown>>(
    `SELECT * FROM estimate.permits WHERE permit_num = $1`,
    [permitNum]
  );
  if (!permit) return null;
  const docs = await q<{ doc_id: string; name: string | null }>(
    `SELECT doc_id::text, name FROM estimate.documents WHERE permit_num = $1 ORDER BY name NULLS LAST, doc_id`,
    [permitNum]
  );
  const ids = docs.map((d) => d.doc_id);
  const r2 = await r2Set();
  const proc = ids.length
    ? await q<{ did: string; pages: number; labeled: number }>(
        `SELECT d.onestop_doc_id::text did,
                COUNT(DISTINCT pg.id)::int pages,
                COUNT(pl.id)::int labeled
         FROM estimate.document d
         LEFT JOIN estimate.page pg ON pg.document_id = d.id
         LEFT JOIN estimate.page_label pl ON pl.page_id = pg.id
         WHERE d.onestop_doc_id::text = ANY($1)
         GROUP BY d.onestop_doc_id`,
        [ids]
      )
    : [];
  const procMap = new Map(proc.map((r) => [r.did, r]));
  const rows: DocRow[] = docs.map((d) => {
    const p = procMap.get(d.doc_id);
    return {
      doc_id: d.doc_id,
      name: d.name,
      downloaded: r2.has(d.doc_id),
      rendered: (p?.pages ?? 0) > 0,
      labeled: (p?.labeled ?? 0) > 0,
      pages: p?.pages ?? 0,
    };
  });
  return { permit, docs: rows };
}
