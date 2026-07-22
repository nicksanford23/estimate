import Link from "next/link";
import { notFound } from "next/navigation";
import { getProjectIdentity, getRoomsFinishes } from "@/lib/v2Db";
import { floorAreaSummary } from "@/lib/floorAreas";
import ProjectHeader from "@/components/ProjectHeader";

export const dynamic = "force-dynamic";

// Project Overview (V2_PRODUCT_REBUILD_PLAN_V1.md §6.1). Shows the real
// pipeline stages with honest status — no fabricated completion, machine and
// human counts kept separate. This replaces the old Pages board as the
// project landing tab; the page-review board now lives under Plan Set.

type StageState = "done" | "active" | "waiting" | "blocked";

function StageRow({
  n,
  name,
  detail,
  state,
  href,
}: {
  n: number;
  name: string;
  detail: string;
  state: StageState;
  href?: string;
}) {
  const inner = (
    <>
      <span className="ov-stage-n">{n}</span>
      <span className="ov-stage-name">{name}</span>
      <span className="ov-stage-detail">{detail}</span>
      <span className={`ov-stage-dot ov-stage-${state}`} aria-hidden />
    </>
  );
  return href ? (
    <Link href={href} className="ov-stage ov-stage-link">
      {inner}
    </Link>
  ) : (
    <div className="ov-stage">{inner}</div>
  );
}

export default async function ProjectOverviewPage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const identity = await getProjectIdentity(permit);
  if (!identity) return notFound();

  const [rooms, floor] = await Promise.all([
    getRoomsFinishes(permit).catch(() => null),
    Promise.resolve(floorAreaSummary(permit)),
  ]);

  const roomTotal = rooms?.rows.length ?? 0;
  const roomConfirmed = rooms?.rows.filter((r) => r.confirmed).length ?? 0;

  // Determine the current step / next action honestly.
  let nextAction = "Confirm the active plan set";
  let nextHref = `/v2/b/${permit}/plan-set`;
  if (roomTotal > 0) {
    nextAction = "Review the room roster";
    nextHref = `/v2/b/${permit}/rooms`;
  }
  if (floor && floor.total > 0) {
    nextAction = "Review floor areas";
    nextHref = `/v2/b/${permit}/floor-areas`;
  }

  return (
    <div className="container">
      <ProjectHeader identity={identity} active="overview" permit={permit} />

      <div className="ov-next">
        <span className="ov-next-eyebrow">Next action</span>
        <span className="ov-next-label">{nextAction}</span>
        <Link href={nextHref} className="btn primary ov-next-btn">Continue →</Link>
      </div>

      <div className="ov-stages">
        <StageRow
          n={1}
          name="Plan set"
          detail={`${identity.doc_count} documents · ${identity.page_count} pages on file`}
          state="active"
          href={`/v2/b/${permit}/plan-set`}
        />
        <StageRow
          n={2}
          name="Room roster"
          detail={roomTotal > 0 ? `${roomConfirmed}/${roomTotal} rows confirmed` : "No schedule extracted yet"}
          state={roomTotal > 0 ? (roomConfirmed === roomTotal ? "done" : "active") : "waiting"}
          href={`/v2/b/${permit}/rooms`}
        />
        <StageRow
          n={3}
          name="Floor areas"
          detail={
            floor && floor.total > 0
              ? `${floor.withProposal} proposed · ${floor.provisional} provisional · ${floor.unresolved} unresolved · ${floor.approved} approved`
              : "No proposals yet"
          }
          state={floor && floor.total > 0 ? "active" : "waiting"}
          href={`/v2/b/${permit}/floor-areas`}
        />
        <StageRow n={4} name="Policy" detail="Waiting for flooring decisions" state="waiting" />
        <StageRow n={5} name="Estimate" detail="Not ready" state="waiting" />
      </div>

      <p className="ov-note">
        Machine proposals and human approvals are counted separately. No floor area is approved until a person
        approves the geometry itself — matching the printed schedule area is a later diagnostic, never approval.
      </p>
    </div>
  );
}
