// TEMP ML workbench — single project. Rebuilt 2026-07-17 to mirror the LOCKED
// process (docs/pilot/FULL_PROCESS_LOCKED.md). Three parts:
//   (a) the 4-button row (Full plan set PDF / Trimmed plans images /
//       Pipeline report / Room editor);
//   (b) REVIEW QUEUE — the star: measured surfaces awaiting an S8 decision;
//   (c) SURFACES grouped by measured verdict (gate output; pre-measurement
//       fallback for projects the gate has not reached yet).
//
// FOUNDER CAVEAT: functional slice, no invented polish — pending founder visual
// sign-off. Projects shown by ADDRESS, never permit number.
import Link from "next/link";
import { notFound } from "next/navigation";
import { loadProjectDetail, loadReviewQueue, loadSurfaceGroups } from "@/lib/lab";
import LabReviewQueue from "@/components/LabReviewQueue";

export const dynamic = "force-dynamic";

export default async function LabProject({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const detail = loadProjectDetail(permit);
  if (!detail) return notFound();
  const queue = loadReviewQueue(permit);
  const surfaces = loadSurfaceGroups(permit);
  const f = (kind: string, name = "") =>
    `/api/lab/file?permit=${permit}&kind=${kind}${name ? `&name=${name}` : ""}`;

  return (
    <div className="container">
      <div className="page-head">
        <h1>{detail.name}</h1>
        <p>
          <Link href="/lab">← workbench</Link> · {detail.blurb}
        </p>
      </div>

      {/* (a) the four buttons — images for humans, PDFs one-click downloads */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
        {detail.activeDoc && (
          <a className="btn" href={f("doc", detail.activeDoc)} target="_blank">
            Full plan set (PDF)
          </a>
        )}
        {detail.hasKeptImages && (
          <Link className="btn" href={`/lab/${permit}/pages`}>
            Trimmed plans (images)
          </Link>
        )}
        {detail.hasReport && (
          <a className="btn" href={f("report")} target="_blank">
            Pipeline report
          </a>
        )}
        {detail.hasEditor && (
          <Link className="btn" href={`/v2/annotate/${permit}`}>
            Room editor
          </Link>
        )}
      </div>

      {/* (b) REVIEW QUEUE — S5.5 measured surfaces -> S8 human decision */}
      <section>
        <h2 style={{ marginTop: 26 }}>Review queue</h2>
        <p style={{ fontSize: 13, opacity: 0.75 }}>
          Measured surfaces awaiting your decision. Each is a confirmed-reference call — confirm + accept, reject the
          reference, flag for judgment, or skip with a note.
        </p>
        {queue.present ? (
          <LabReviewQueue permit={permit} items={queue.items} />
        ) : (
          <p style={{ opacity: 0.7 }}>Measuring gate not yet run (no edge_gate_full/QUEUE.json for this project).</p>
        )}
      </section>

      {/* (c) SURFACES grouped by measured verdict */}
      <section>
        <h2 style={{ marginTop: 30 }}>Surfaces by verdict</h2>
        <p style={{ fontSize: 13, opacity: 0.75 }}>
          {surfaces.source === "gate"
            ? "Grouped by the measured verdict from the edge gate."
            : surfaces.source === "fallback"
              ? "Pre-measurement view — the edge gate has not run here; grouped by draft inspection / proposal signal."
              : "No surface artifacts yet."}
        </p>
        {surfaces.groups.map((g) => (
          <div key={g.verdict}>
            <h3 style={{ marginTop: 18 }}>
              {g.title} ({g.cards.length})
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 14, marginTop: 8 }}>
              {g.cards.map((c) => {
                const proof = c.proofImages[0] ? f("proof", c.proofImages[0]) : c.overlayCode ? f("overlay", c.overlayCode) : null;
                return (
                  <div key={c.id} className="permit-card" style={{ cursor: "default" }}>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                      <strong>{c.identities.join(" · ") || c.id}</strong>
                      {c.spaceName && <span style={{ fontSize: 12, opacity: 0.7 }}>{c.spaceName}</span>}
                      {c.worstDeviationIn != null && <span className="chip">worst {c.worstDeviationIn.toFixed(1)} in</span>}
                      {c.decision && <span className="chip code">{c.decision.decision}</span>}
                    </div>
                    {c.reason && <p style={{ fontSize: 12, opacity: 0.75, margin: "6px 0 0" }}>{c.reason}</p>}
                    {proof ? (
                      <a href={proof} target="_blank" rel="noreferrer">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={proof}
                          alt={`surface ${c.id}`}
                          loading="lazy"
                          style={{ width: "100%", marginTop: 8, borderRadius: 8, border: "1px solid var(--line)" }}
                        />
                      </a>
                    ) : (
                      <p style={{ marginTop: 8, fontSize: 12, opacity: 0.6 }}>no proof image yet</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
        {surfaces.groups.length === 0 && <p style={{ opacity: 0.7 }}>Nothing to show yet.</p>}
      </section>
    </div>
  );
}
