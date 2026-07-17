import { notFound } from "next/navigation";
import { isValidPermit, loadBoardData } from "@/lib/annotate";
import AnnotateBoard from "@/components/AnnotateBoard";

export const dynamic = "force-dynamic";

// Geometry annotation editor — FUNCTIONAL PILOT SLICE (no approved mockup;
// see design-loop caveat in the component header). Reads the immutable
// annotation packet + sam_smoke viewport bundle, writes append-only human
// outcomes. Route: /v2/annotate/<permit>.
export default async function AnnotatePage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  if (!isValidPermit(permit)) return notFound();
  const data = loadBoardData(permit);
  if (!data) return notFound();
  return <AnnotateBoard data={data} />;
}
