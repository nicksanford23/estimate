import Link from "next/link";
import { getPermit, CODE_LABEL } from "@/lib/queries";
import { GUIDES } from "@/lib/guides";
import GuideImages from "@/components/GuideImages";

export const dynamic = "force-dynamic";

const fmt = (n: number) => n.toLocaleString("en-US");

const GUIDE_CSS = `
.guide-imgs{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.guide-img{display:block;width:100%;padding:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff;cursor:zoom-in}
.guide-img img{width:100%;display:block;aspect-ratio:3/2;object-fit:cover;object-position:top}
.guide-img .cap{display:block;font-family:var(--font-mono);font-size:11px;color:var(--muted);padding:8px 10px;background:var(--surface);text-align:left}
.buckets{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
.bucket{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.bucket .btop{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.bucket .btype{font-weight:700;font-size:15px}
.bucket .bunit{font-family:var(--font-mono);font-size:11px;color:var(--accent-ink);border:1px solid var(--line);border-radius:6px;padding:2px 7px}
.bucket .bcodes{font-family:var(--font-mono);font-size:12px;color:var(--muted);margin-top:4px}
.bucket .brooms{font-size:13px;margin-top:8px}
.bucket .bproduct{font-size:12px;color:var(--muted);margin-top:6px}
.fitrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:14px}
.fitcell{display:flex;align-items:center;gap:8px;font-size:14px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
.verdict-box{border-radius:12px;padding:16px 18px}
.verdict-box.partial{background:var(--warn-bg);border:1px solid color-mix(in srgb,var(--warn) 40%,var(--line))}
.verdict-box.good{background:var(--good-bg);border:1px solid color-mix(in srgb,var(--good) 40%,var(--line))}
.verdict-box.not_suitable{background:var(--bad-bg);border:1px solid color-mix(in srgb,var(--bad) 40%,var(--line))}
.verdict-box p{margin:8px 0 0;font-size:14px}
.guide-steps{margin:0;padding-left:22px;display:flex;flex-direction:column;gap:10px}
.guide-steps li{font-size:15px;line-height:1.5}
.guide table td.ok{color:var(--good);font-family:var(--font-mono);font-size:12.5px}
.guide table td.bad{color:var(--bad);font-family:var(--font-mono);font-size:12.5px}
.guide table td.pend{color:var(--muted);font-family:var(--font-mono);font-size:12.5px}
.guide table tr.key td{background:var(--bad-bg)}
`;

export default async function GuidePage({
  params,
}: {
  params: Promise<{ permitNum: string }>;
}) {
  const { permitNum } = await params;
  const permit = decodeURIComponent(permitNum);
  const g = GUIDES[permit];
  const data = await getPermit(permit);
  const p = (data?.permit ?? {}) as Record<string, unknown>;
  const str = (k: string) => (p[k] == null || p[k] === "" ? null : String(p[k]));

  if (!g) {
    return (
      <main className="container">
        <Link href={`/permits/${encodeURIComponent(permit)}`} className="back">
          ← {permit}
        </Link>
        <div className="empty" style={{ paddingTop: 60 }}>
          No takeoff guide generated for this project yet.
        </div>
      </main>
    );
  }

  const carpet = g.materials.find((m) => m.type === "Carpet");
  const areaTypes = g.materials.filter((m) => m.unit !== "LF").map((m) => m.type);
  const linearTypes = g.materials.filter((m) => m.unit === "LF").map((m) => m.type);

  return (
    <main className="container guide">
      <style>{GUIDE_CSS}</style>
      <Link href={`/permits/${encodeURIComponent(permit)}`} className="back">
        ← {permit}
      </Link>

      {/* 1. Overview */}
      <div className="page-head">
        <div className="eyebrow">Takeoff Guide · {CODE_LABEL[str("code") ?? ""] ?? "Project"}</div>
        <h1>{permit}</h1>
        <p>{str("description") || "—"}</p>
      </div>
      <div className="meta-grid">
        {[
          ["Recorded sq ft", str("sqft")],
          ["Address", [str("address"), str("city")].filter(Boolean).join(", ") || null],
          ["Plan set", `${g.planSet.docName} · ${g.planSet.totalPages} pages`],
          ["Scale", g.scale],
        ]
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <div key={k as string}>
              <div className="k">{k}</div>
              <div className="v">{v}</div>
            </div>
          ))}
      </div>

      {/* 2. Plan set */}
      <div className="section-title">The flooring pages</div>
      <p className="sec-intro">
        Of {g.planSet.totalPages} pages, <b>{g.planSet.flooringPages}</b> matter for flooring
        (floor plans, the finish plan, demo plan), plus <b>{g.planSet.specPages}</b> architectural
        spec pages that carry the Division-09 flooring specifications. Everything else — MEP,
        structural, elevations, civil — is skipped.
      </p>
      <GuideImages
        docId={g.docId}
        items={[
          { page: g.finishPlanPage, label: "Finish plan & schedule (what goes where)" },
          { page: g.floorPlanPage, label: "Floor plan (the geometry we measure)" },
        ]}
      />

      {/* 3. What & where — materials */}
      <div className="section-title">What flooring &amp; where (from the finish schedule)</div>
      <p className="sec-intro">
        The finish schedule assigns every room a material. These are the buckets an estimator needs a
        quantity for:
      </p>
      <div className="buckets">
        {g.materials.map((m) => (
          <div className="bucket" key={m.type}>
            <div className="btop">
              <span className="btype">{m.type}</span>
              <span className="bunit">{m.unit}</span>
            </div>
            <div className="bcodes">{m.codes.join(" · ")}</div>
            <div className="brooms">{m.rooms}</div>
            <div className="bproduct">{m.product}</div>
          </div>
        ))}
      </div>

      {/* 4. Measurability */}
      <div className="section-title">Can we measure it automatically?</div>
      <div className="fitrow">
        {[
          ["Vector (not scanned)", g.fit.vector],
          ["Readable scale", g.fit.scale],
          ["Printed dimensions", g.fit.dimensions],
          ["Walls close into rooms", g.fit.geometryCloses],
        ].map(([label, ok]) => (
          <div className={`fitcell ${ok ? "ok" : "bad"}`} key={label as string}>
            <span className="fmark">{ok ? "✅" : "❌"}</span>
            {label}
          </div>
        ))}
      </div>
      <div className={`verdict-box ${g.fit.verdict}`}>
        <b>
          {g.fit.verdict === "partial"
            ? "🟡 Partial — great inputs, one blocker"
            : g.fit.verdict === "good"
            ? "🟢 Good fit"
            : "🔴 Not suitable"}
        </b>
        <p>{g.fit.note}</p>
      </div>

      {/* 5. How an estimator takes it off */}
      <div className="section-title">How an estimator would take this off</div>
      <ol className="guide-steps">
        <li>
          <b>Read the finish schedule first.</b> Learn what goes where → the buckets above
          ({areaTypes.join(", ")}, plus base &amp; transitions).
        </li>
        <li>
          <b>Set the scale</b> ({g.scale}). Every measurement scales from this.
        </li>
        <li>
          <b>Trace every room&rsquo;s area</b> — the bulk of the work. In takeoff software they click
          around each room&rsquo;s perimeter; the tool computes the area. Color-coded by material.
        </li>
        <li>
          <b>Sum by material.</b> All carpet rooms → total{carpet ? " (converted to square yards, SY = SF ÷ 9)" : ""};
          tile → SF; resilient → SF.
        </li>
        <li>
          <b>Measure the linear items</b> ({linearTypes.join(", ")}) — in linear feet around walls and at
          doorways.
        </li>
        <li>
          <b>Add waste</b> (+5–10% for cuts &amp; pattern match).
        </li>
        <li>
          <b>Add prep &amp; accessories</b> — floor prep, adhesive, thresholds (defined in the specs).
        </li>
        <li>
          <b>Price it</b> — quantity × material + labor + prep + margin → the bid.
        </li>
      </ol>

      {/* 6. Where our automation stands */}
      <div className="section-title">Where our automation stands</div>
      <div className="tblwrap">
        <table>
          <thead>
            <tr>
              <th>Estimator step</th>
              <th>Our pipeline</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Get plans</td><td>Download from R2</td><td className="ok">✅ done</td></tr>
            <tr><td>Read finish schedule</td><td>Labeling finds it; AI reads it → buckets above</td><td className="ok">✅ (this guide)</td></tr>
            <tr><td>Set scale</td><td>Parses {g.scale}</td><td className="ok">✅</td></tr>
            <tr className="key"><td><b>Trace every room</b></td><td>Geometry auto-traces polygons</td><td className="bad">❌ blobs — the hard part</td></tr>
            <tr><td>Sum by material</td><td>polygons × finish map</td><td className="pend">⛔ needs rooms</td></tr>
            <tr><td>Base / transitions</td><td>perimeter from geometry</td><td className="pend">⛔ not built</td></tr>
            <tr><td>Waste / prep / price</td><td>—</td><td className="pend">⛔ not built</td></tr>
          </tbody>
        </table>
      </div>
      <p className="sec-intro" style={{ marginTop: 16 }}>
        The one binding step is <b>tracing every room</b> — exactly what our geometry automates and where
        it blobs today. The realistic product is <b>assisted takeoff</b>: the tool suggests room
        boundaries, a human confirms the few it gets wrong. And the <b>materials half</b> (finish schedule →
        buckets) is the tractable, mostly-unbuilt win shown above.
      </p>
      <div style={{ height: 60 }} />
    </main>
  );
}
