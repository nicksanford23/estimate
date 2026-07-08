import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import { getPageImagePath } from "@/lib/queries";

const DATA_ROOT = process.env.DATA_ROOT ?? "/workspaces/estimate";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ docId: string; page: string }> }
) {
  const { docId, page } = await params;
  if (!/^\d+$/.test(docId) || !/^\d+$/.test(page)) {
    return new NextResponse("bad request", { status: 400 });
  }
  const ip = await getPageImagePath(docId, parseInt(page, 10));
  if (!ip) return new NextResponse("not found", { status: 404 });
  const full = path.isAbsolute(ip) ? ip : path.join(DATA_ROOT, ip);
  if (!fs.existsSync(full)) return new NextResponse("no image", { status: 404 });

  const buf = await sharp(full).resize({ width: 320 }).jpeg({ quality: 72 }).toBuffer();
  return new NextResponse(new Uint8Array(buf), {
    headers: { "Content-Type": "image/jpeg", "Cache-Control": "max-age=3600" },
  });
}
