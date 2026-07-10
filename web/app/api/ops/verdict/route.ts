import { NextResponse } from "next/server";
import { appendVerdict } from "@/lib/opsVerdict";

// The ONE permitted mutation: append one row to eyeball_verdicts.csv
// (slice=nick), never rewriting or deleting existing rows.
export async function POST(req: Request) {
  let body: {
    permit?: string;
    doc_id?: string;
    page?: string;
    verdict?: "CONFIRMED" | "FALSE_PASS" | "UNCLEAR";
    reason?: string;
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }
  const { permit, doc_id = "", page = "", verdict, reason = "" } = body;
  if (!permit || !verdict) {
    return NextResponse.json({ error: "permit and verdict are required" }, { status: 400 });
  }
  try {
    appendVerdict({ permit, doc_id, page, verdict, reason });
  } catch (e) {
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 400 });
  }
  return NextResponse.json({ ok: true });
}
