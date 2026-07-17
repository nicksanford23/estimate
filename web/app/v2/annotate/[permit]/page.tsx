import { notFound } from "next/navigation";
import { isValidPermit, loadBoardData } from "@/lib/annotate";
import AnnotateBoard from "@/components/AnnotateBoard";

export const dynamic = "force-dynamic";

// Geometry annotation editor — FUNCTIONAL PILOT SLICE (no approved mockup;
// see design-loop caveat in the component header). Reads the immutable
// V1 annotation packet + sam_smoke viewport bundle, writes append-only
// provisional review outcomes. These rows are proposals for V2 re-review,
// never training/evaluation truth. Route: /v2/annotate/<permit>.
export default async function AnnotatePage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  if (!isValidPermit(permit)) return notFound();
  const data = loadBoardData(permit);
  if (!data) return notFound();
  return <AnnotateBoard data={data} />;
}
