import { NextResponse } from "next/server";
import { presignPdf } from "@/lib/r2";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ docId: string }> }
) {
  const { docId } = await params;
  if (!/^\d+$/.test(docId)) {
    return new NextResponse("bad document id", { status: 400 });
  }
  const url = await presignPdf(docId);
  return NextResponse.redirect(url);
}
