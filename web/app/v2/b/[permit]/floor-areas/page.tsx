import Link from "next/link";
import { notFound } from "next/navigation";
import { getProjectIdentity } from "@/lib/v2Db";
import { loadFloorAreas } from "@/lib/floorAreas";
import ProjectHeader from "@/components/ProjectHeader";
import FloorAreasBoard from "@/components/FloorAreasBoard";

export const dynamic = "force-dynamic";

// Floor Areas (V2_PRODUCT_REBUILD_PLAN_V1.md §6.4). The single geometry-review
// destination — replaces Outline Rooms and Geometry Review. Loads the existing
// machine proposals + provisional human outlines for real; shows an honest
// review shell (no agentic critique/repair or editing yet).
export default async function FloorAreasPage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const identity = await getProjectIdentity(permit);
  if (!identity) return notFound();

  const data = loadFloorAreas(permit);

  return (
    <div className="container">
      <ProjectHeader identity={identity} active="floor" permit={permit} />
      {data ? (
        <FloorAreasBoard data={data} />
      ) : (
        <div className="fa-unavailable">
          <p>No floor-area proposals exist for this project yet.</p>
          <p className="fa-hint">
            Floor Areas opens once a plan set has been segmented into room proposals. Confirm the{" "}
            <Link href={`/v2/b/${permit}/plan-set`}>plan set</Link> and{" "}
            <Link href={`/v2/b/${permit}/rooms`}>room roster</Link> first.
          </p>
        </div>
      )}
    </div>
  );
}
