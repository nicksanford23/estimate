import Link from "next/link";
import { listPilotBuildings, type BuildingListRow } from "@/lib/v2Db";
import { floorAreaSummary, type FloorAreaCounts } from "@/lib/floorAreas";
import { displayTitle, shortDescription } from "@/lib/projectDisplay";

export const dynamic = "force-dynamic";

// V2 landing: ONE card per project (V2_PRODUCT_REBUILD_PLAN_V1.md §5). No
// separate cards for page labeling, schedules, geometry, or annotation
// packets — those were parallel research sections that made the same project
// appear twice with two identities. Address/name is the dominant text; permit
// number is demoted to a corner. Progress shown is honest and actionable only:
// machine work and human approval counts are kept distinct, and no "locked"
// count is derived from provisional V1 rows.

const PILOT: Record<string, { tag: string; note: string }> = {
  "26-10321-RNVN": { tag: "A", note: "geometry-centric" },
  "24-06748-RNVS": { tag: "B", note: "schedule-centric" },
};

type ProjectCardModel = BuildingListRow & { floor: FloorAreaCounts | null };

function currentStep(b: ProjectCardModel): { label: string; detail: string } {
  const f = b.floor;
  if (f && f.total > 0) {
    return {
      label: "Floor-area review",
      // Machine and human counts are shown SEPARATELY and honestly. "approved"
      // is human-approved V2 geometry — zero until real review happens here.
      detail: `${f.withProposal} proposed · ${f.provisional} provisional · ${f.unresolved} unresolved · ${f.approved} approved`,
    };
  }
  return { label: "Plan set", detail: `${b.page_count} pages on file` };
}

function ProjectCard({ b }: { b: ProjectCardModel }) {
  const pilot = PILOT[b.permit_num];
  const step = currentStep(b);
  const title = displayTitle({
    permit_num: b.permit_num,
    building_name: b.building_name,
    address_raw: b.address_raw,
    city_description: b.city_description,
  });
  const sub = shortDescription(b.city_description);
  return (
    <Link href={`/v2/b/${b.permit_num}`} className="proj-card" title={b.permit_num}>
      {pilot && <span className="proj-pilot">Pilot {pilot.tag} · {pilot.note}</span>}
      <span className="proj-title">{title}</span>
      {sub && sub !== title && <span className="proj-sub">{sub}</span>}

      <div className="proj-step">
        <span className="proj-step-eyebrow">Current step</span>
        <span className="proj-step-label">{step.label}</span>
        <span className="proj-step-detail">{step.detail}</span>
      </div>

      <div className="proj-foot">
        <span className="proj-continue">Open project →</span>
        <span className="proj-permit">{b.permit_num}</span>
      </div>
    </Link>
  );
}

export default async function V2ProjectsPage() {
  const buildings = await listPilotBuildings();
  const models: ProjectCardModel[] = buildings.map((b) => ({
    ...b,
    floor: floorAreaSummary(b.permit_num),
  }));

  // Recently active first: projects that have reached Floor Areas lead, then
  // by page count. (No timestamp column yet — this is the honest proxy.)
  const rank = (m: ProjectCardModel) => (m.floor && m.floor.total > 0 ? 1 : 0);
  const pilot = models
    .filter((m) => PILOT[m.permit_num])
    .sort((a, z) => PILOT[a.permit_num].tag.localeCompare(PILOT[z.permit_num].tag));
  const others = models
    .filter((m) => !PILOT[m.permit_num])
    .sort((a, z) => rank(z) - rank(a) || z.page_count - a.page_count);

  return (
    <div className="container">
      <div className="page-head">
        <span className="eyebrow">Commercial flooring estimator</span>
        <h1>Projects</h1>
        <p>
          Each project moves through one sequence: confirm the plan set, confirm the room roster, review
          floor areas, then estimate. Start with the two active pilot projects.
        </p>
      </div>

      <div className="proj-grid">
        {pilot.map((b) => <ProjectCard key={b.building_id} b={b} />)}
      </div>

      {others.length > 0 && (
        <details className="proj-more">
          <summary>Other candidate projects ({others.length}) — not part of the active pilot</summary>
          <div className="proj-grid" style={{ marginTop: 14 }}>
            {others.map((b) => <ProjectCard key={b.building_id} b={b} />)}
          </div>
        </details>
      )}

      {buildings.length === 0 && <p style={{ color: "var(--muted)" }}>No projects loaded yet.</p>}
    </div>
  );
}
