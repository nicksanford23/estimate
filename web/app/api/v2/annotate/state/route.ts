import { NextResponse } from "next/server";
import { isValidPermit, readLatestOutcomes } from "@/lib/annotate";

// Latest human outcome per task_id (append-only JSONL resolved, last row wins).
// Lets the editor re-read saved state without a full page reload.
export async function GET(req: Request) {
  const url = new URL(req.url);
  const permit = url.searchParams.get("permit") ?? "";
  if (!isValidPermit(permit)) return NextResponse.json({ error: "bad permit" }, { status: 400 });
  return NextResponse.json({ latest: readLatestOutcomes(permit) });
}
