// Streams pipeline artifacts (PDFs, overlay images, reports) for the temp
// ML workbench. Strict whitelist per kind; no path traversal possible.
import { NextRequest } from "next/server";
import fs from "fs";
import path from "path";
import { SMOKE, PDF_DIR, PROJECT_DOCS } from "@/lib/lab";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams;
  const permit = q.get("permit") ?? "";
  const kind = q.get("kind") ?? "";
  const name = q.get("name") ?? "";
  if (!/^[A-Za-z0-9-]+$/.test(permit)) return new Response("bad permit", { status: 400 });

  let file: string | null = null;
  let type = "application/octet-stream";
  if (kind === "kept") {
    file = path.join(SMOKE, permit, `${permit}_kept_pages.pdf`);
    type = "application/pdf";
  } else if (kind === "doc") {
    if (!/^[0-9]+$/.test(name) || !(PROJECT_DOCS[permit] ?? []).includes(name))
      return new Response("unknown doc", { status: 400 });
    file = path.join(PDF_DIR, `${name}.pdf`);
    type = "application/pdf";
  } else if (kind === "keptimg") {
    if (!/^[0-9]{2}$/.test(name)) return new Response("bad name", { status: 400 });
    file = path.join(SMOKE, permit, "kept_pages", `page_${name}.png`);
    type = "image/png";
  } else if (kind === "overlay") {
    if (!/^[A-Za-z0-9]+$/.test(name)) return new Response("bad name", { status: 400 });
    file = path.join(SMOKE, permit, "claude_vision", `overlay_${name}.png`);
    type = "image/png";
  } else if (kind === "report") {
    file = path.join(SMOKE, permit, "PIPELINE_REPORT.md");
    type = "text/plain; charset=utf-8";
  } else {
    return new Response("bad kind", { status: 400 });
  }
  if (!file || !fs.existsSync(file)) return new Response("not found", { status: 404 });
  const data = fs.readFileSync(file);
  return new Response(new Uint8Array(data), {
    headers: { "Content-Type": type, "Content-Disposition": `inline; filename="${path.basename(file)}"` },
  });
}
