import { NextResponse } from "next/server";
import fs from "node:fs";
import { resolveOverlayPath } from "@/lib/opsData";

// Streams overlay/render images from data/ (gitignored) for the Ops
// dashboard. Restricted to a fixed allow-list of pipeline output dirs —
// see resolveOverlayPath() in lib/opsData.ts.
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ segs: string[] }> }
) {
  const { segs } = await params;
  const rel = segs.map(decodeURIComponent).join("/");
  const full = resolveOverlayPath(rel);
  if (!full) return new NextResponse("not found", { status: 404 });
  const buf = fs.readFileSync(full);
  const ct = /\.png$/i.test(full) ? "image/png" : "image/jpeg";
  return new NextResponse(new Uint8Array(buf), {
    headers: { "Content-Type": ct, "Cache-Control": "max-age=3600" },
  });
}
