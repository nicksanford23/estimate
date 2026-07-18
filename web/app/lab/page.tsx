// TEMP ML workbench index — rebuilt 2026-07-17 to mirror the LOCKED process
// (docs/pilot/FULL_PROCESS_LOCKED.md). One card per project: address, blurb,
// small permit, a pipeline status strip (one chip per stage, "-" when a stage's
// artifact is absent — never a fake green), and two counts: identities
// discovered vs surfaces resolved.
//
// FOUNDER CAVEAT: functional slice, no invented polish — pending founder visual
// sign-off. Projects shown by ADDRESS, never permit number.
import Link from "next/link";
import { listProjectSummaries, type StageChip } from "@/lib/lab";

export const dynamic = "force-dynamic";

function StageChipView({ c }: { c: StageChip }) {
  const done = c.state === "done";
  return (
    <span
      className="chip"
      title={`${c.key} ${c.label} — ${done ? "artifact present" : "not run / unknown"}`}
      style={{
        borderColor: done ? "color-mix(in srgb, var(--accent) 45%, var(--line))" : "var(--line)",
        color: done ? "var(--accent-ink)" : "var(--muted)",
        opacity: done ? 1 : 0.55,
      }}
    >
      {c.key} {done ? (c.detail ? `${c.label} ${c.detail}` : c.label) : "-"}
    </span>
  );
}

export default function LabIndex() {
  const projects = listProjectSummaries();
  return (
    <div className="container">
      <div className="page-head">
        <h1>ML Workbench (temp)</h1>
        <p>
          The LOCKED pipeline, project by project. Each strip shows a stage&apos;s status derived from artifacts on disk;
          &quot;-&quot; means that stage has not run. Functional slice — pending founder visual sign-off.
        </p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 14, marginTop: 16 }}>
        {projects.map((p) => (
          <Link key={p.permit} href={`/lab/${p.permit}`} className="permit-card">
            <strong>{p.name}</strong>
            <div style={{ fontSize: 13, opacity: 0.75 }}>{p.blurb}</div>
            <div style={{ fontSize: 11, opacity: 0.5, fontFamily: "var(--font-mono)" }}>{p.permit}</div>
            <div style={{ marginTop: 8, display: "flex", gap: 5, flexWrap: "wrap" }}>
              {p.stages.map((c) => (
                <StageChipView key={c.key} c={c} />
              ))}
            </div>
            <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
              <span className="chip">
                {p.identitiesDiscovered ?? "-"} identities
              </span>
              <span className="chip">
                {p.surfacesResolved ?? "-"} surfaces
              </span>
              {!p.surfacesConsolidated && p.surfacesResolved != null && (
                <span className="chip" title="no surfaces.json yet — count is identities, not consolidated physical surfaces">
                  unconsolidated
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>
      {projects.length === 0 && <p>No pipeline projects found under data/sam_smoke/.</p>}
    </div>
  );
}
