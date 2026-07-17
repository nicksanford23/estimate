// TEMP ML workbench index — founder-requested interim surface (2026-07-17).
// One card per pipeline project. Deliberately unstyled beyond site defaults;
// replaced by the real product surface once the outline process stabilizes.
import Link from "next/link";
import { listProjects, PROJECT_NAMES } from "@/lib/lab";

export const dynamic = "force-dynamic";

export default function LabIndex() {
  const projects = listProjects();
  return (
    <div className="container">
      <div className="page-head">
        <h1>ML Workbench (temp)</h1>
        <p>The room-outline pipeline, project by project. Plans, overlays, statuses — no polish, no ceremony.</p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14, marginTop: 16 }}>
        {projects.map((p) => {
          const decided = p.rooms.filter((r) => r.decision === "lock").length;
          return (
            <Link key={p.permit} href={`/lab/${p.permit}`} className="permit-card">
              <strong>{PROJECT_NAMES[p.permit]?.name ?? p.permit}</strong>
              <div style={{ fontSize: 13, opacity: 0.75 }}>{PROJECT_NAMES[p.permit]?.blurb ?? ""}</div>
              <div style={{ fontSize: 11, opacity: 0.5 }}>{p.permit}</div>
              <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span className="chip">{p.rooms.length} rooms proposed</span>
                <span className="chip">{decided} locked</span>
                {p.keptPdf && <span className="chip">kept-pages PDF</span>}
                {p.report && <span className="chip">report</span>}
              </div>
            </Link>
          );
        })}
      </div>
      {projects.length === 0 && <p>No pipeline projects found under data/sam_smoke/.</p>}
    </div>
  );
}
