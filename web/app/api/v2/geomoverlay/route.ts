import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

// Serves the legacy takeoff overlay JPGs (data/takeoff/<permit>/overlay_*.jpg)
// referenced from v2.geometry_run.manifest_json.overlay_path. These runs
// predate the v2 schema (imported with manifest_json.legacy=true) and have
// no vector polygon coordinates — only this pre-rendered raster with
// overlays already baked in — so this is the canvas image for Geometry
// Review until a fresh run produces real geom_json coordinates. `file` is
// constrained to basenames under data/takeoff/ to avoid path traversal.
const ROOT = path.join(process.cwd(), ".."); // repo root; manifest paths are "data/takeoff/..."

export async function GET(req: Request) {
  const url = new URL(req.url);
  const rel = url.searchParams.get("path");
  if (!rel || rel.includes("..") || path.isAbsolute(rel) || !rel.startsWith("data/takeoff/")) {
    return new NextResponse("bad request", { status: 400 });
  }
  const full = path.join(ROOT, rel);
  if (!full.startsWith(path.join(ROOT, "data/takeoff")) || !fs.existsSync(full)) {
    return new NextResponse("not found", { status: 404 });
  }
  const buf = fs.readFileSync(full);
  return new NextResponse(new Uint8Array(buf), {
    headers: { "Content-Type": "image/jpeg", "Cache-Control": "max-age=3600" },
  });
}
