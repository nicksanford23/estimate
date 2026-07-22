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
import { loadProjectDetail, loadReviewQueue, loadSurfaceGroups, listFloorMaps } from "@/lib/lab";
import LabReviewQueue from "@/components/LabReviewQueue";
import LabProofGallery from "@/components/LabProofGallery";

export const dynamic = "force-dynamic";

export default async function LabProject({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const detail = loadProjectDetail(permit);
  if (!detail) return notFound();
  const queue = loadReviewQueue(permit);
  const surfaces = loadSurfaceGroups(permit);
  const floorMaps = listFloorMaps(permit);
  const allCards = surfaces.groups?.flatMap((g) => g.cards) ?? [];
  const needsYou = queue.items.filter((i) => !i.decision).length;
  const f = (kind: string, name = "") =>
    `/api/lab/file?permit=${permit}&kind=${kind}${name ? `&name=${name}` : ""}`;

  return (
    <div className="container lab-project">
      <div className="page-head">
        <h1>{detail.name}</h1>
        <p>
          <Link href="/lab">← workbench</Link> · {detail.blurb}
        </p>
      </div>

      {/* (a) the four buttons — images for humans, PDFs one-click downloads */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
        {permit === "24-06748-RNVS" && (
          <Link className="btn primary" href={`/lab/${permit}/learn/107`}>
            Start here: understand Room 107
          </Link>
        )}
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
      {floorMaps.length > 0 && (
        <section>
          <h2 style={{ marginTop: 20 }}>Floor maps — every room, colored by status</h2>
          <p style={{ fontSize: 13, opacity: 0.75 }}>
            blue = done · green = measured good · orange = small nudge · red = needs fix · gray = your call.
            Needs you: <strong>{needsYou}</strong>
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12 }}>
            {floorMaps.map((m) => (
              <a key={m} href={f("proof", m)} target="_blank">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={f("proof", m)} alt={m} loading="lazy"
                     style={{ width: "100%", maxHeight: "80vh", objectFit: "contain", borderRadius: 8, border: "1px solid var(--line)" }} />
              </a>
            ))}
          </div>
        </section>
      )}

      {allCards.length > 0 && (
        <section>
          <h2 style={{ marginTop: 20 }}>All rooms (stable order — nothing ever moves)</h2>
          <table style={{ width: "100%", fontSize: 14, borderCollapse: "collapse" }}>
            <tbody>
              {[...allCards].sort((a, b) => (a.identities[0] ?? "").localeCompare(b.identities[0] ?? "", undefined, { numeric: true })).map((c) => (
                <tr key={c.id} style={{ borderBottom: "1px solid var(--line)" }}>
                  <td style={{ padding: "6px 8px" }}><a href={`#room-${c.identities[0] ?? c.id}`}><strong>{c.identities.join("/")}</strong></a></td>
                  <td style={{ padding: "6px 8px", opacity: 0.8 }}>{c.spaceName ?? ""}</td>
                  <td style={{ padding: "6px 8px" }}><span className="chip">{c.decision ? c.decision.decision : c.verdict.replaceAll("_", " ")}</span></td>
                  <td style={{ padding: "6px 8px", opacity: 0.8 }}>{c.worstDeviationIn != null ? `worst ${c.worstDeviationIn.toFixed(1)}"` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}


      {/* (b) REVIEW QUEUE — S5.5 measured surfaces -> S8 human decision */}
      <section>
        <h2 style={{ marginTop: 26 }}>Review queue</h2>
        <p className="lab-section-intro">
          Work from the whole-room image. Green edges passed measurement, orange edges need a small adjustment, and red
          edges need to be redrawn. Open the edge details only when you need a closer look.
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
        <p className="lab-section-intro">
          {surfaces.source === "gate"
            ? "Grouped by the measured verdict from the edge gate."
            : surfaces.source === "fallback"
              ? "Pre-measurement view — the edge gate has not run here; grouped by draft inspection / proposal signal."
              : "No surface artifacts yet."}
        </p>
        <div className="lab-verdict-groups">
          {surfaces.groups.map((g) => (
            <details key={g.verdict} className="lab-verdict-group">
              <summary>
                <span>{g.title}</span>
                <span className="chip">{g.cards.length} surface{g.cards.length === 1 ? "" : "s"}</span>
              </summary>
              <div className="lab-surface-grid">
              {g.cards.map((c) => {
                const primary = c.proofImages.map((name) => ({ src: f("proof", name), label: `Room ${c.identities.join(" · ")} review` }));
                if (primary.length === 0 && c.overlayCode) primary.push({ src: f("overlay", c.overlayCode), label: `Room ${c.overlayCode} draft overlay` });
                const details = c.edgeZooms.map((name) => ({
                  src: f("proof", name),
                  label: name.match(/_(e\d+|room)\.png$/)?.[1]?.replace(/^e/, "Edge ") ?? name,
                }));
                return (
                  <article key={c.id} className="lab-surface-card">
                    <div className="lab-surface-card-head">
                      <strong>{c.identities.join(" · ") || c.id}</strong>
                      {c.spaceName && <span>{c.spaceName}</span>}
                      {c.worstDeviationIn != null && <span className="chip">worst {c.worstDeviationIn.toFixed(1)} in</span>}
                      {c.decision && <span className="chip code">{c.decision.decision}</span>}
                    </div>
                    {c.reason && <p>{c.reason}</p>}
                    {primary.length > 0 ? (
                      <LabProofGallery primary={primary} details={details} compact />
                    ) : (
                      <p style={{ marginTop: 8, fontSize: 12, opacity: 0.6 }}>no proof image yet</p>
                    )}
                  </article>
                );
              })}
              </div>
            </details>
          ))}
        </div>
        {surfaces.groups.length === 0 && <p style={{ opacity: 0.7 }}>Nothing to show yet.</p>}
      </section>
    </div>
  );
}
