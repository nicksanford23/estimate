import Link from "next/link";
import { getPermit, CODE_LABEL } from "@/lib/queries";
import { GUIDES } from "@/lib/guides";
import GuideImages from "@/components/GuideImages";

export const dynamic = "force-dynamic";

const fmt = (n: number) => n.toLocaleString("en-US");

const GUIDE_CSS = `
.guide-imgs{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.guide-img{display:block;width:100%;padding:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff;cursor:zoom-in}
.guide-img img{width:100%;display:block;aspect-ratio:3/2;object-fit:contain;object-position:center;background:#fff}
.guide-img .cap{display:block;font-family:var(--font-mono);font-size:11px;color:var(--muted);padding:8px 10px;background:var(--surface);text-align:left}
.buckets{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
.bucket{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.bucket .btop{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.bucket .btype{font-weight:700;font-size:15px}
.bucket .bunit{font-family:var(--font-mono);font-size:11px;color:var(--accent-ink);border:1px solid var(--line);border-radius:6px;padding:2px 7px}
.bucket .bqty{font-family:var(--font-mono);font-size:16px;font-weight:700;margin-top:10px}
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
.guide table td.warn{color:var(--warn);font-family:var(--font-mono);font-size:12.5px}
.guide table td.pend{color:var(--muted);font-family:var(--font-mono);font-size:12.5px}
.guide table tr.key td{background:var(--warn-bg)}
.state-pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;font-family:var(--font-mono);font-size:11px;white-space:nowrap}
.state-pill.auto_quantity{background:var(--good-bg);color:var(--good)}
.state-pill.geometry_review,.state-pill.open_zone_split,.state-pill.vision_correct_or_redraw{background:var(--warn-bg);color:var(--warn)}
.mdot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:7px;vertical-align:middle}
.mdot.carpet{background:#2563a8}
.mdot.ceramic-tile,.mdot.tile{background:#a06a2c}
.mdot.resilient{background:#2f7d57}
.mdot.lvt{background:#d97706}
.mdot.sealed-concrete,.mdot.concrete{background:#6b7280}
.finding-list{margin:0;padding-left:22px;display:flex;flex-direction:column;gap:9px}
.finding-list li{font-size:14.5px;line-height:1.5}
.adjust-box{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--accent-ink);border-radius:10px;padding:12px 16px;margin-top:14px}
`;

const ACTION_LABELS = {
  auto_quantity: "auto quantity",
  geometry_review: "geometry review",
  open_zone_split: "open-zone split",
  vision_correct_or_redraw: "vision/redraw",
};

const STATUS_MARK: Record<string, string> = {
  ok: "✅",
  warn: "⚠",
  pend: "⛔",
  bad: "❌",
};

// Fallback automation table (the original bank guide narrative) for guides that
// don't carry their own per-permit automation rows.
const BANK_AUTOMATION = [
  { step: "Get plans", pipeline: "Download from R2", status: "ok", note: "done" },
  { step: "Read finish schedule", pipeline: "Labeling finds it; AI reads it → buckets above", status: "ok", note: "(this guide)" },
  { step: "Set scale", pipeline: "Parses the sheet scale", status: "ok", note: "" },
  { step: "Trace enclosed rooms", pipeline: "Layer geometry + printed-dimension cross-check", status: "ok", note: "10 auto / 2 review" },
  { step: "Split open finish zones", pipeline: "Finish-boundary / zoning model plus reviewer fallback", status: "warn", note: "5 room labels" },
  { step: "Correct fragments", pipeline: "Vision/redraw catches storefront and door semantics", status: "warn", note: "101 only" },
  { step: "Sum by material", pipeline: "product states × finish map", status: "ok", note: "completed here" },
  { step: "Base / transitions", pipeline: "perimeter and material-change pass", status: "warn", note: "estimated, review" },
  { step: "Waste / prep / price", pipeline: "—", status: "pend", note: "not built" },
];

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
  const areaTypes = g.materials.filter((m) => m.unit === "SF" || m.unit === "SY").map((m) => m.type);
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
          ["Completed takeoff", g.takeoff ? `${fmt(g.takeoff.netFloorSf)} SF net` : null],
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

      {/* 2b. Our takeoff overlays (custom images we generated) */}
      {g.overlays && g.overlays.length > 0 && (
        <>
          <div className="section-title">What our takeoff pass produced</div>
          <p className="sec-intro">
            The images below are generated by our pipeline on this permit — geometry polygons,
            room anchoring, and the assembled takeoff (or, where it fails, the failure itself).
          </p>
          <GuideImages docId={g.docId} items={g.overlays} />
        </>
      )}

      {/* 3. What & where — materials */}
      <div className="section-title">What flooring &amp; where (from the finish schedule)</div>
      <p className="sec-intro">
        The finish schedule assigns every room a material. These are the buckets an estimator needs a
        quantity for. On this bank pass, the material quantities are assembled from the finish map,
        geometry, open-zone splits, and review corrections:
      </p>
      <div className="buckets">
        {g.materials.map((m) => (
          <div className="bucket" key={m.type}>
            <div className="btop">
              <span className="btype">{m.type}</span>
              <span className="bunit">{m.unit}</span>
            </div>
            {m.quantity && <div className="bqty">{m.quantity}</div>}
            <div className="bcodes">{m.codes.join(" · ")}</div>
            <div className="brooms">{m.rooms}</div>
            <div className="bproduct">{m.product}</div>
          </div>
        ))}
      </div>

      {/* 3b. Rooms — the takeoff skeleton */}
      <div className="section-title">Rooms — product-state review ({g.rooms.length})</div>
      <p className="sec-intro">
        The useful field is not just room SF. It is the action the product should take: auto-quantity
        clean enclosed rooms, split open finish zones, or send uncertain geometry to review.
      </p>
      <div className="tblwrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Room</th>
              <th>Floor material</th>
              <th>Product action</th>
              <th className="m">Quantity status</th>
            </tr>
          </thead>
          <tbody>
            {g.rooms.map((r) => (
              <tr key={r.num}>
                <td className="m">{r.num}</td>
                <td>{r.name}</td>
                <td>
                  <span className={`mdot ${r.material.replace(/\s/g, "-").toLowerCase()}`} />
                  {r.material} ({r.code})
                </td>
                <td>
                  {r.action ? (
                    <span className={`state-pill ${r.action}`}>{ACTION_LABELS[r.action]}</span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="m" style={{ color: "var(--muted)" }}>{r.sfNote ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 4. Measurability */}
      <div className="section-title">Can we measure it automatically?</div>
      <div className="fitrow">
        {[
          ["Vector (not scanned)", g.fit.vector],
          ["Readable scale", g.fit.scale],
          ["Printed dimensions", g.fit.dimensions],
          ["All finish zones close automatically", g.fit.geometryCloses],
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
            ? "🟡 Partial — assisted takeoff, review flagged"
            : g.fit.verdict === "good"
            ? "🟢 Good fit"
            : "🔴 Not suitable"}
        </b>
        <p>{g.fit.note}</p>
        {g.takeoff && <p>{g.takeoff.note}</p>}
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
          <b>Trace enclosed rooms and split open areas.</b> Clean rooms become polygons directly.
          Open public areas need finish boundaries or a reviewer-confirmed split.
        </li>
        <li>
          <b>Sum by material.</b> All carpet rooms → total{carpet ? " (converted to square yards, SY = SF ÷ 9)" : ""};
          tile → SF; resilient → SF.
        </li>
        <li>
          <b>Measure base and transitions</b> — {linearTypes.join(", ")} in linear feet around walls,
          plus transition counts at material changes.
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

      {/* 5b. What we found (per-permit findings) */}
      {g.findings && g.findings.length > 0 && (
        <>
          <div className="section-title">What we found on this permit</div>
          <ul className="finding-list">
            {g.findings.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </>
      )}

      {/* 5c. How we'd adjust the approach */}
      {g.adjustments && g.adjustments.length > 0 && (
        <>
          <div className="section-title">How this changes the approach</div>
          <div className="adjust-box">
            <ul className="finding-list">
              {g.adjustments.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>
        </>
      )}

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
            {(g.automation ?? BANK_AUTOMATION).map((r) => (
              <tr key={r.step}>
                <td>{r.step}</td>
                <td>{r.pipeline}</td>
                <td className={r.status}>
                  {STATUS_MARK[r.status]} {r.note}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sec-intro" style={{ marginTop: 16 }}>
        This is the product shape to carry forward: confident quantities where geometry and dimensions
        agree, explicit review queues where they do not, and open-plan finish splits treated as their
        own problem instead of as a generic room-geometry failure.
      </p>

      <div className="section-title">How this links to the rest of the system</div>
      <ol className="guide-steps">
        <li><b>Permit triage</b> decides which docs and pages to keep for flooring.</li>
        <li><b>Finish extraction</b> turns the finish schedule into room → material buckets.</li>
        <li><b>Geometry probes</b> create candidate room polygons and validation totals.</li>
        <li><b>Product-state review</b> classifies each room as auto, open-zone split, review, or redraw.</li>
        <li><b>Takeoff assembly</b> rolls accepted quantities into material totals, base, and transitions.</li>
        {!g.findings && (
          <li><b>Training notes</b> come from the review rows: 101 storefront fragment, 109 door/opening edge, 114 service-core corridor, and the two open-zone split groups.</li>
        )}
      </ol>
      <div style={{ height: 60 }} />
    </main>
  );
}
