import { notFound } from "next/navigation";
import { getBuildingDetail } from "@/lib/v2Db";
import V2ReviewBoard from "@/components/V2ReviewBoard";

export const dynamic = "force-dynamic";

export default async function V2BuildingPage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const detail = await getBuildingDetail(permit);
  if (!detail) return notFound();

  return <V2ReviewBoard permit={detail.permit} building={detail.building} docs={detail.docs} />;
}
