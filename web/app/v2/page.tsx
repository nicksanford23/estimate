import Link from "next/link";
import { listPilotBuildings } from "@/lib/v2Db";

export const dynamic = "force-dynamic";

// Display: project first (address + what it is), permit number demoted to
// hover/detail. City sqft/value shown only when the record actually has it.
function shortDescription(d: string | null): string {
  if (!d) return "";
  // City descriptions ramble ("...as per plans, HDLC C/A #..."), keep the lead clause.
  const cut = d.split(/ as per | per plans|, HDLC|, BZA/i)[0];
  return cut.length > 90 ? cut.slice(0, 87) + "…" : cut;
}

export default async function V2IndexPage() {
  const buildings = await listPilotBuildings();

  return (
    <div className="container">
      <div className="page-head">
        <h1>Buildings</h1>
        <p>Confirm page labels — machine suggestions are dashed, your decisions turn solid.</p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14, marginTop: 18 }}>
        {buildings.map((b) => (
          <Link key={b.building_id} href={`/v2/b/${b.permit_num}`} className="permit-card" title={b.permit_num}>
            <span className="pnum">{b.address_raw || b.building_name}</span>
            <span className="addr">{shortDescription(b.city_description)}</span>
            <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
              {b.city_sqft != null && b.city_sqft > 0 && (
                <span className="chip">{Math.round(b.city_sqft).toLocaleString()} SF (city record)</span>
              )}
              <span className="chip">{b.page_count} pages</span>
            </div>
          </Link>
        ))}
      </div>
      {buildings.length === 0 && <p style={{ color: "var(--muted)" }}>No buildings loaded yet.</p>}
    </div>
  );
}
