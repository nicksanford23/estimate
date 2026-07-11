import { NextResponse } from "next/server";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { DATA_ROOT } from "@/lib/opsData";

const execFileP = promisify(execFile);

// On-demand single-doc download for the Ops Documents tab's "Download"
// button. Shells out to scripts/fetch_one_doc.py, which reuses
// scripts/download_batch.py's proven fetch/%PDF-validate/R2-upload
// machinery and appends to the standing download log CSV — so this path
// is logged exactly like the batch downloader, never a parallel one-off.
export async function POST(req: Request) {
  let body: { doc_id?: string; permit?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const { doc_id, permit } = body;
  if (typeof doc_id !== "string" || !/^\d+$/.test(doc_id)) {
    return NextResponse.json({ error: "doc_id must be a numeric string" }, { status: 400 });
  }
  if (typeof permit !== "string" || !permit) {
    return NextResponse.json({ error: "permit is required" }, { status: 400 });
  }

  const scriptsDir = path.join(DATA_ROOT, "scripts");
  try {
    const { stdout } = await execFileP(
      "python3",
      ["fetch_one_doc.py", doc_id, permit],
      { cwd: scriptsDir, timeout: 180_000 }
    );
    const lastLine = stdout.trim().split("\n").pop() ?? "{}";
    const res = JSON.parse(lastLine) as {
      doc_id: string;
      permit: string;
      status: string;
      bytes: number;
      note: string;
    };
    const ok = res.status === "ok" || res.status === "already_in_r2";
    return NextResponse.json(res, { status: ok ? 200 : 502 });
  } catch (err) {
    return NextResponse.json(
      { error: "fetch_one_doc.py failed", detail: String(err) },
      { status: 500 }
    );
  }
}
