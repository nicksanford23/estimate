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
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 16 }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid var(--line)" }}>
            <th style={{ padding: "8px 6px" }}>Building</th>
            <th style={{ padding: "8px 6px" }}>Permit</th>
            <th style={{ padding: "8px 6px" }}>Docs</th>
            <th style={{ padding: "8px 6px" }}>Pages</th>
          </tr>
        </thead>
        <tbody>
          {buildings.map((b) => (
            <tr key={b.building_id} style={{ borderBottom: "1px solid var(--line)" }}>
              <td style={{ padding: "8px 6px" }}>
                <Link href={`/v2/b/${b.permit_num}`}>{b.building_name}</Link>
              </td>
              <td style={{ padding: "8px 6px", fontFamily: "var(--font-mono)" }}>{b.permit_num}</td>
              <td style={{ padding: "8px 6px" }}>{b.doc_count}</td>
              <td style={{ padding: "8px 6px" }}>{b.page_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {buildings.length === 0 && <p style={{ color: "var(--muted)" }}>No pilot buildings backfilled yet — run scripts/v2_backfill.py.</p>}
    </div>
  );
}
