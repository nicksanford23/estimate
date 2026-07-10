import { NextResponse } from "next/server";
import fs from "node:fs";
import sharp from "sharp";
import { getOriginalPagePath } from "@/lib/opsPages";

// Original (no-overlay) page image for the Ops detail page. Falls back to
// render-on-demand (cached in data/render_cache/). `?w=280` returns a
// resized JPEG thumb; no param streams the full PNG.
export async function GET(
  req: Request,
  { params }: { params: Promise<{ docId: string; page: string }> }
) {
  const { docId, page } = await params;
  if (!/^\d+$/.test(docId) || !/^\d+$/.test(page)) {
    return new NextResponse("bad request", { status: 400 });
  }
  const full = await getOriginalPagePath(docId, parseInt(page, 10));
  if (!full) return new NextResponse("no original render available", { status: 404 });

  const w = new URL(req.url).searchParams.get("w");
  if (w && /^\d+$/.test(w)) {
    const width = Math.min(1200, Math.max(64, parseInt(w, 10)));
    const buf = await sharp(full).resize({ width }).jpeg({ quality: 72 }).toBuffer();
    return new NextResponse(new Uint8Array(buf), {
      headers: { "Content-Type": "image/jpeg", "Cache-Control": "max-age=3600" },
    });
  }
  const buf = fs.readFileSync(full);
  return new NextResponse(new Uint8Array(buf), {
    headers: { "Content-Type": "image/png", "Cache-Control": "max-age=3600" },
  });
}
