// Original (no-overlay) page images + doc metadata for the Ops permit
// detail page. Resolution order for a page image:
//   1. the pipeline's existing render (Neon estimate.page.image_path)
//   2. our render cache (data/render_cache/<docId>_p<page>.png)
//   3. render on demand with PyMuPDF from a local PDF copy
//      (data/pdfs_r2/<docId>.pdf, else fetched once from R2 and cached
//      under data/render_cache/pdf/).
// Everything lands in data/ (gitignored); nothing is written to web/public.
import fs from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { q } from "./db";
import { getPdfBytes } from "./r2";
import { DATA_ROOT } from "./opsData";

const execFileP = promisify(execFile);

const CACHE_DIR = path.join(DATA_ROOT, "data/render_cache");
const PDF_CACHE_DIR = path.join(CACHE_DIR, "pdf");
const LOCAL_PDF_DIR = path.join(DATA_ROOT, "data/pdfs_r2");
const PAGETEXT_DIR = path.join(DATA_ROOT, "data/pagetext");

function ensureDirs() {
  fs.mkdirSync(PDF_CACHE_DIR, { recursive: true });
}

// ------------------------------------------------------------- pdf get ---
async function ensureLocalPdf(docId: string): Promise<string | null> {
  const candidates = [
    path.join(LOCAL_PDF_DIR, `${docId}.pdf`),
    path.join(PDF_CACHE_DIR, `${docId}.pdf`),
  ];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  ensureDirs();
  const dest = path.join(PDF_CACHE_DIR, `${docId}.pdf`);
  try {
    const bytes = await getPdfBytes(docId);
    // trust but verify: don't cache junk
    if (bytes.length < 5 || String.fromCharCode(...bytes.slice(0, 4)) !== "%PDF") return null;
    fs.writeFileSync(dest, bytes);
    return dest;
  } catch {
    return null;
  }
}

// --------------------------------------------------------- page render ---
// Simple semaphore so a 40-thumb strip can't stampede the box with
// concurrent PyMuPDF subprocesses.
let active = 0;
const waiters: Array<() => void> = [];
const MAX_CONCURRENT_RENDERS = 2;
async function withRenderSlot<T>(fn: () => Promise<T>): Promise<T> {
  if (active >= MAX_CONCURRENT_RENDERS) {
    await new Promise<void>((res) => waiters.push(res));
  }
  active++;
  try {
    return await fn();
  } finally {
    active--;
    waiters.shift()?.();
  }
}

async function renderPageToCache(docId: string, page: number): Promise<string | null> {
  ensureDirs();
  const out = path.join(CACHE_DIR, `${docId}_p${page}.png`);
  if (fs.existsSync(out)) return out;
  const pdf = await ensureLocalPdf(docId);
  if (!pdf) return null;
  const script = `
import sys, fitz
pdf, page, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
doc = fitz.open(pdf)
if page < 0 or page >= len(doc):
    sys.exit(3)
pix = doc[page].get_pixmap(dpi=140)
pix.save(out)
`;
  try {
    await withRenderSlot(() =>
      execFileP("python3", ["-c", script, pdf, String(page), out], { timeout: 60_000 })
    );
    return fs.existsSync(out) ? out : null;
  } catch {
    return null;
  }
}

async function neonImagePath(docId: string, page: number): Promise<string | null> {
  try {
    const [r] = await q<{ image_path: string }>(
      `SELECT p.image_path FROM estimate.page p
       JOIN estimate.document d ON d.id = p.document_id
       WHERE d.onestop_doc_id::text = $1 AND p.page_index = $2 LIMIT 1`,
      [docId, page]
    );
    if (!r?.image_path) return null;
    const full = path.isAbsolute(r.image_path) ? r.image_path : path.join(DATA_ROOT, r.image_path);
    return fs.existsSync(full) ? full : null;
  } catch {
    return null;
  }
}

/** Absolute path of the ORIGINAL page image (no overlay), or null. */
export async function getOriginalPagePath(docId: string, page: number): Promise<string | null> {
  if (!/^\d+$/.test(docId) || page < 0) return null;
  return (
    (await neonImagePath(docId, page)) ??
    // cache hit without spawning python
    (fs.existsSync(path.join(CACHE_DIR, `${docId}_p${page}.png`))
      ? path.join(CACHE_DIR, `${docId}_p${page}.png`)
      : await renderPageToCache(docId, page))
  );
}

// ----------------------------------------------------------- doc meta ----
const TITLE_WORD = /(PLAN|SCHEDULE|ELEVATION|SECTION|DETAILS?|NOTES|INDEX|COVER|LEGEND|SPECIFICATIONS|RISER)\b/i;
const TITLE_PREFER = /(FLOOR|FINISH|DEMO|CEILING|ROOF|SITE|FRAMING|FOUNDATION|ELECTRICAL|PLUMBING|MECHANICAL|HVAC|LIFE\s+SAFETY|ENLARGED|PARTIAL)[\s\S]{0,40}(PLAN|SCHEDULE)/i;

// Cheap title-block guess from the page's extracted text: short,
// title-shaped lines only (same spirit as scan_closeability_full.title_flag
// — "SEE FLOOR PLAN" cross-references excluded). Null when no pagetext.
function titleFromText(text: string): string | null {
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length >= 4 && l.length < 60 && !/\bSEE\b/i.test(l));
  const preferred = lines.find((l) => TITLE_PREFER.test(l));
  if (preferred) return preferred;
  return lines.find((l) => TITLE_WORD.test(l)) ?? null;
}

export type DocMeta = {
  docId: string;
  pageCount: number;
  titles: (string | null)[]; // index = page
  name: string | null;
};

export async function getDocMeta(docId: string): Promise<DocMeta | null> {
  if (!/^\d+$/.test(docId)) return null;

  let name: string | null = null;
  try {
    const [d] = await q<{ name: string | null }>(
      `SELECT name FROM estimate.documents WHERE doc_id::text = $1 LIMIT 1`,
      [docId]
    );
    name = d?.name ?? null;
  } catch {
    /* name is cosmetic */
  }

  // page count: pagetext dir -> Neon -> PyMuPDF
  let pageCount = 0;
  const ptDir = path.join(PAGETEXT_DIR, docId);
  if (fs.existsSync(ptDir)) {
    pageCount = fs.readdirSync(ptDir).filter((f) => /^page_\d{4}\.txt$/.test(f)).length;
  }
  if (!pageCount) {
    try {
      const [r] = await q<{ n: number }>(
        `SELECT COUNT(pg.id)::int n FROM estimate.document d
         JOIN estimate.page pg ON pg.document_id = d.id
         WHERE d.onestop_doc_id::text = $1`,
        [docId]
      );
      pageCount = r?.n ?? 0;
    } catch {
      /* fall through */
    }
  }
  if (!pageCount) {
    const pdf = await ensureLocalPdf(docId);
    if (pdf) {
      try {
        const { stdout } = await execFileP(
          "python3",
          ["-c", "import sys, fitz; print(len(fitz.open(sys.argv[1])))", pdf],
          { timeout: 30_000 }
        );
        pageCount = parseInt(stdout.trim(), 10) || 0;
      } catch {
        /* leave 0 */
      }
    }
  }
  if (!pageCount) return null;

  const titles: (string | null)[] = [];
  for (let i = 0; i < pageCount; i++) {
    const f = path.join(ptDir, `page_${String(i).padStart(4, "0")}.txt`);
    if (fs.existsSync(f)) {
      try {
        titles.push(titleFromText(fs.readFileSync(f, "utf8")));
      } catch {
        titles.push(null);
      }
    } else {
      titles.push(null);
    }
  }
  return { docId, pageCount, titles, name };
}
