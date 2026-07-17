import { NextResponse } from "next/server";
import fs from "node:fs";
import { isValidPermit, viewportImagePath } from "@/lib/annotate";

// Streams a level's viewport PNG for the geometry annotation editor. Source is
// the sam_smoke bundle (data/sam_smoke/<permit>/bundle/viewport_p<page>.png)
// with a local-render fallback — resolution + path-safety live in lib/annotate.
// Pages 5-8 only (the four confirmed proposed-plan viewports for this pilot).
export async function GET(req: Request) {
  const url = new URL(req.url);
  const permit = url.searchParams.get("permit") ?? "";
  const pageStr = url.searchParams.get("page") ?? "";
  if (!isValidPermit(permit)) return new NextResponse("bad permit", { status: 400 });
  if (!/^[5-8]$/.test(pageStr)) return new NextResponse("bad page", { status: 400 });

  const full = viewportImagePath(permit, Number(pageStr));
  if (!full || !fs.existsSync(full)) return new NextResponse("no image", { status: 404 });
  const buf = fs.readFileSync(full);
  return new NextResponse(new Uint8Array(buf), {
    headers: { "Content-Type": "image/png", "Cache-Control": "no-store" },
  });
}
