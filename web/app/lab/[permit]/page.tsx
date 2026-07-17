// TEMP ML workbench, single project: source PDFs, kept-pages PDF, overlay
// gallery with per-room status, report link, editor link. Interim surface.
import Link from "next/link";
import { notFound } from "next/navigation";
import { loadProject, projectName } from "@/lib/lab";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export default async function LabProject({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const p = loadProject(permit);
  if (!p) return notFound();
  const hasEditor = fs.existsSync(
    path.join(process.cwd(), "..", "data", "geometry_annotations", `${permit}.geometry_annotation_packet_v1.json`),
  );
  const keptDir = path.join(process.cwd(), "..", "data", "sam_smoke", permit, "kept_pages");
  const keptPages = fs.existsSync(keptDir)
    ? fs.readdirSync(keptDir).filter((x) => /^page_[0-9]{2}\.png$/.test(x)).map((x) => x.slice(5, 7)).sort()
    : [];
  const f = (kind: string, name = "") =>
    `/api/lab/file?permit=${permit}&kind=${kind}${name ? `&name=${name}` : ""}`;
  return (
    <div className="container">
      <div className="page-head">
        <h1>{projectName(permit)}</h1>
        <p><Link href="/lab">← workbench</Link></p>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
        {p.docs.length > 0 && (
          <a className="btn" href={f("doc", p.docs[0])} target="_blank">Full plan set (PDF)</a>
        )}
        {keptPages.length > 0 && (
          <Link className="btn" href={`/lab/${permit}/pages`}>Trimmed plans (images)</Link>
        )}
        {p.report && <a className="btn" href={f("report")} target="_blank">Pipeline report</a>}
        {hasEditor && <Link className="btn" href={`/v2/annotate/${permit}`}>Room editor</Link>}
      </div>
      <h2 style={{ marginTop: 20 }}>Room overlays — machine proposals, not truth</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 14, marginTop: 10 }}>
        {p.rooms.map((r) => (
          <div key={r.code} className="permit-card" style={{ cursor: "default" }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <strong>{r.code}</strong>
              {r.outcome && <span className="chip">{r.outcome}</span>}
              {r.confidence !== null && <span className="chip">conf {r.confidence.toFixed(2)}</span>}
              {r.decision && <span className="chip">{r.decision}</span>}
            </div>
            {r.overlay ? (
              <a href={f("overlay", r.code)} target="_blank">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={f("overlay", r.code)} alt={`room ${r.code} overlay`}
                     style={{ width: "100%", marginTop: 8, borderRadius: 8, border: "1px solid var(--line)" }} />
              </a>
            ) : (
              <p style={{ marginTop: 8 }}>no overlay rendered</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
