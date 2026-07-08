import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { PDFDocument } from "pdf-lib";
import { q } from "@/lib/db";
import { getPdfBytes } from "@/lib/r2";

export const dynamic = "force-dynamic";

const DATA_ROOT = process.env.DATA_ROOT ?? "/workspaces/estimate";
const KEEP = new Set(["floor_plan", "finish_plan", "finish_schedule", "demo_plan"]);
// Division-09 flooring specification sections
const FLOOR_RE =
  /(RESILIENT FLOORING|SECTION\s*096\d\d|SECTION\s*0930\d|(CERAMIC|PORCELAIN)\s+TILE\s+FLOORING)/i;

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ docId: string }> }
) {
  const { docId } = await params;
  if (!/^\d+$/.test(docId)) return new NextResponse("bad id", { status: 400 });

  const rows = await q<{ pi: number; cat: string }>(
    `SELECT DISTINCT ON (p.id) p.page_index pi, pl.category cat
     FROM estimate.page p
     JOIN estimate.document d ON d.id = p.document_id
     JOIN estimate.page_label pl ON pl.page_id = p.id
     WHERE d.onestop_doc_id = $1
     ORDER BY p.id, pl.confidence DESC`,
    [Number(docId)]
  );

  const kept = new Set<number>();
  for (const r of rows) if (KEEP.has(r.cat)) kept.add(r.pi);
  // flooring-spec pages: specs_notes whose text has a Division-09 flooring section
  for (const r of rows) {
    if (r.cat !== "specs_notes") continue;
    const tp = path.join(
      DATA_ROOT,
      `data/pagetext/${docId}/page_${String(r.pi).padStart(4, "0")}.txt`
    );
    if (fs.existsSync(tp) && FLOOR_RE.test(fs.readFileSync(tp, "utf8"))) kept.add(r.pi);
  }

  const idx = [...kept].sort((a, b) => a - b);
  if (idx.length === 0) {
    return new NextResponse("No flooring pages found for this document.", { status: 404 });
  }

  const srcBytes = await getPdfBytes(docId);
  const src = await PDFDocument.load(srcBytes, { ignoreEncryption: true });
  const n = src.getPageCount();
  const valid = idx.filter((i) => i >= 0 && i < n);
  const out = await PDFDocument.create();
  const copied = await out.copyPages(src, valid);
  copied.forEach((pg) => out.addPage(pg));
  const outBytes = await out.save();

  return new NextResponse(new Uint8Array(outBytes), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="flooring-pages-${docId}.pdf"`,
      "Cache-Control": "no-store",
    },
  });
}
