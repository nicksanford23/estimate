import Link from "next/link";
import { listPilotBuildings } from "@/lib/v2Db";

export const dynamic = "force-dynamic";

export default async function V2IndexPage() {
  const buildings = await listPilotBuildings();

  return (
    <div className="container">
      <div className="page-head">
        <div className="eyebrow">V2 schema · slice S1</div>
        <h1>Pilot Buildings</h1>
        <p>Thin Page Review — identity spine (permit/building/document/page) + binding decisions.</p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 14, marginTop: 18 }}>
        {buildings.map((b) => (
          <Link key={b.building_id} href={`/v2/b/${b.permit_num}`} className="permit-card">
            <span className="pnum">{b.building_name}</span>
            <span className="addr" style={{ fontFamily: "var(--font-mono)" }}>{b.permit_num}</span>
            <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
              <span className="chip">{b.doc_count} doc{b.doc_count === 1 ? "" : "s"}</span>
              <span className="chip">{b.page_count} pages</span>
            </div>
          </Link>
        ))}
      </div>
      {buildings.length === 0 && <p style={{ color: "var(--muted)" }}>No pilot buildings backfilled yet — run scripts/v2_backfill.py.</p>}
    </div>
  );
}
