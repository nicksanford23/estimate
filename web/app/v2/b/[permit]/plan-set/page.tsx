import { notFound } from "next/navigation";
import { getBuildingDetail, getProjectIdentity } from "@/lib/v2Db";
import V2ReviewBoard from "@/components/V2ReviewBoard";

export const dynamic = "force-dynamic";

// Plan Set (V2_PRODUCT_REBUILD_PLAN_V1.md §6.2). Combines the useful parts of
// the old Pages and Documents tabs. This slice ships the existing page-review
// board (sheet inventory + per-page source review) under the Plan Set tab plus
// a link to the full document list; the fuller document/active-plan-set
// consolidation is a later phase.
export default async function PlanSetPage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const [detail, identity] = await Promise.all([
    getBuildingDetail(permit),
    getProjectIdentity(permit),
  ]);
  if (!detail) return notFound();

  return <V2ReviewBoard permit={detail.permit} building={detail.building} docs={detail.docs} identity={identity} />;
}
