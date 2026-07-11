import { notFound } from "next/navigation";
import { getGeometryReview } from "@/lib/v2Db";
import GeometryReviewBoard from "@/components/GeometryReviewBoard";

export const dynamic = "force-dynamic";

export default async function V2GeometryPage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const data = await getGeometryReview(permit);
  if (!data) return notFound();
  return <GeometryReviewBoard data={data} />;
}
