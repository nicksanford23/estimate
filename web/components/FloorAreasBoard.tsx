"use client";

// Floor Areas workspace (V2_PRODUCT_REBUILD_PLAN_V1.md §6.4, §7). Replaces the
// old Outline Rooms editor and Geometry Review. Three columns: an area queue, a
// dominant plan canvas, and a review panel. This slice ships the honest review
// SHELL on real proposal data — it does not run agentic critique/repair or edit
// geometry, so those actions are visible-but-reserved, never fake-working
// (§17: reserve real states, don't hard-code fake reviews).

import { useMemo, useState } from "react";
import FloorAreasCanvas, { type Overlay, type ViewMode } from "@/components/FloorAreasCanvas";
import type { FloorAreaRoom, FloorAreasData, FloorAreaStatus } from "@/lib/floorAreas";

const STATUS_META: Record<FloorAreaStatus, { glyph: string; label: string; cls: string }> = {
  proposal: { glyph: "●", label: "Proposed", cls: "fa-st-proposal" },
  provisional: { glyph: "◐", label: "Provisional", cls: "fa-st-provisional" },
  unresolved: { glyph: "▲", label: "Unresolved", cls: "fa-st-unresolved" },
  no_proposal: { glyph: "—", label: "No proposal", cls: "fa-st-none" },
};

function fmtSf(sf: number | null | undefined): string {
  return sf == null ? "—" : `${sf.toFixed(1)} SF`;
}

export default function FloorAreasBoard({ data }: { data: FloorAreasData }) {
  const { permit, rooms, counts } = data;
  const [selectedId, setSelectedId] = useState<string | null>(rooms.find((r) => r.proposal)?.taskId ?? rooms[0]?.taskId ?? null);
  const [overlay, setOverlay] = useState<Overlay>("proposal");
  const [viewMode, setViewMode] = useState<ViewMode>("room");
  const [selectedEdge, setSelectedEdge] = useState<number | null>(null);
  const [fitToken, setFitToken] = useState(0);

  const room = useMemo(() => rooms.find((r) => r.taskId === selectedId) ?? null, [rooms, selectedId]);

  const levels = useMemo(() => {
    const by: Record<string, FloorAreaRoom[]> = {};
    for (const r of rooms) (by[r.level] ??= []).push(r);
    return Object.keys(by).sort().map((level) => ({ level, sheet: by[level][0]?.sheetNumber, items: by[level] }));
  }, [rooms]);

  function openRoom(r: FloorAreaRoom) {
    setSelectedId(r.taskId);
    setSelectedEdge(null);
    // If the room has no proposal but has a human outline, default to that.
    setOverlay(r.proposal ? "proposal" : r.human?.polygonPx ? "human" : "proposal");
    setViewMode("room");
  }

  function selectEdge(i: number | null) {
    setSelectedEdge(i);
    if (i != null) setViewMode("room");
  }

  const activePoly = room ? (overlay === "proposal" ? room.proposal?.polygonPx : room.human?.polygonPx) ?? null : null;
  const edgeCount = activePoly ? activePoly.length : 0;

  return (
    <div className="fa-board">
      {/* ---------------- queue ---------------- */}
      <aside className="fa-queue">
        <div className="fa-queue-head">
          <span className="fa-queue-title">Area queue</span>
          <span className="fa-queue-count">{counts.total} rooms</span>
        </div>
        <p className="fa-queue-legend">
          {counts.withProposal} proposed · {counts.provisional} provisional · {counts.unresolved} unresolved ·{" "}
          <b>{counts.approved} approved</b>
        </p>
        <div className="fa-queue-scroll">
          {levels.map(({ level, sheet, items }) => (
            <div key={level} className="fa-queue-group">
              <div className="fa-queue-grouphead">{level}{sheet ? ` · ${sheet}` : ""}</div>
              {items.map((r) => {
                const meta = STATUS_META[r.status];
                return (
                  <button
                    key={r.taskId}
                    className={`fa-queue-row${r.taskId === selectedId ? " fa-queue-row-on" : ""}`}
                    onClick={() => openRoom(r)}
                  >
                    <span className="fa-code">{r.code}</span>
                    <span className="fa-name">{r.name}</span>
                    <span className={`fa-glyph ${meta.cls}`} title={meta.label}>{meta.glyph}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </aside>

      {/* ---------------- canvas ---------------- */}
      <section className="fa-center">
        {room ? (
          <>
            <div className="fa-viewbar">
              <div className="fa-seg">
                <button className={viewMode === "room" ? "on" : ""} onClick={() => { setViewMode("room"); setFitToken((t) => t + 1); }}>Room</button>
                <button className={viewMode === "floor" ? "on" : ""} onClick={() => { setViewMode("floor"); setSelectedEdge(null); }}>Full floor</button>
              </div>
              <div className="fa-seg">
                <button
                  className={overlay === "proposal" ? "on" : ""}
                  disabled={!room.proposal}
                  onClick={() => setOverlay("proposal")}
                  title={room.proposal ? "Original machine proposal" : "No machine proposal for this room"}
                >
                  <span className="fa-swatch fa-sw-proposal" /> Proposal
                </button>
                <button
                  className={overlay === "human" ? "on" : ""}
                  disabled={!room.human?.polygonPx}
                  onClick={() => setOverlay("human")}
                  title={room.human?.polygonPx ? "Provisional human outline" : "No provisional human outline"}
                >
                  <span className="fa-swatch fa-sw-human" /> Provisional
                </button>
                <button className="fa-approved-off" disabled title="No geometry is human-approved in this dataset yet">
                  <span className="fa-swatch fa-sw-approved" /> Approved
                </button>
              </div>
            </div>
            <FloorAreasCanvas
              permit={permit}
              room={room}
              overlay={overlay}
              viewMode={viewMode}
              selectedEdge={selectedEdge}
              onSelectEdge={selectEdge}
              fitToken={fitToken}
            />
          </>
        ) : (
          <div className="fa-empty">Select a room from the queue.</div>
        )}
      </section>

      {/* ---------------- review ---------------- */}
      <aside className="fa-review">
        {room ? (
          <>
            <div className="fa-rv-head">
              <span className="fa-rv-code">{room.code} · {room.name}</span>
              <span className="fa-rv-meta">{room.level} · sheet {room.sheetNumber}</span>
            </div>

            <span className={`fa-badge ${STATUS_META[room.status].cls}`}>{STATUS_META[room.status].label}</span>

            {/* provenance — always honest about machine/provisional status */}
            {overlay === "proposal" && room.proposal && (
              <div className="fa-prov">
                <div className="fa-rv-eyebrow">Machine proposal — provisional, not approved</div>
                <div className="fa-prov-src">{room.proposal.source}</div>
                <div className="fa-prov-line">
                  {fmtSf(room.proposal.measuredSf)} measured <span className="fa-muted">(display only — not an approval)</span>
                </div>
                {room.proposal.confidence != null && (
                  <div className="fa-prov-line fa-muted">proposer self-rated confidence {room.proposal.confidence.toFixed(2)}</div>
                )}
              </div>
            )}
            {overlay === "human" && room.human && (
              <div className="fa-prov">
                <div className="fa-rv-eyebrow">Provisional human outline — not approved V2 truth</div>
                <div className="fa-prov-src">{room.human.outcome}{room.human.boundaryTypes.length ? ` · ${room.human.boundaryTypes.join(", ")}` : ""}</div>
                <div className="fa-prov-line">
                  {fmtSf(room.human.measuredSf)} measured <span className="fa-muted">(display only)</span>
                </div>
                <div className="fa-prov-line fa-muted">saved {new Date(room.human.savedAt).toLocaleDateString()} by {room.human.reviewer}</div>
                {room.human.notes && <div className="fa-prov-line">{room.human.notes}</div>}
              </div>
            )}

            {/* edge-by-edge inspection navigation */}
            {edgeCount > 0 && (
              <div className="fa-edges">
                <div className="fa-rv-eyebrow">Inspect edges ({edgeCount})</div>
                <div className="fa-edge-chips">
                  {Array.from({ length: edgeCount }, (_, i) => (
                    <button
                      key={i}
                      className={`fa-edge-chip${selectedEdge === i ? " on" : ""}`}
                      onClick={() => selectEdge(selectedEdge === i ? null : i)}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
                <p className="fa-hint">Click an edge here or on the plan to zoom to its close-up.</p>
              </div>
            )}

            {/* the proposer's own boundary reasoning — NOT an independent inspection */}
            {overlay === "proposal" && room.proposal && room.proposal.boundaryNotes.length > 0 && (
              <div className="fa-notes">
                <div className="fa-rv-eyebrow">Proposal boundary notes</div>
                <p className="fa-hint">The proposer&rsquo;s stated reasoning. Independent edge inspection is a later slice — this is not a verified critique.</p>
                <ul className="fa-notelist">
                  {room.proposal.boundaryNotes.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              </div>
            )}

            {/* schedule reference — diagnostic only, kept out of the way (§13) */}
            {room.scheduleAreaSf != null && (
              <details className="fa-sched">
                <summary>Schedule reference (diagnostic)</summary>
                <div className="fa-sched-body">
                  Printed schedule area: <b>{room.scheduleAreaSf} SF</b>. This did not select, reshape, or approve any
                  outline — it is a later cross-check only.
                </div>
              </details>
            )}

            {/* reserved human actions — visible verb set, nothing fake-works */}
            <div className="fa-actions">
              <div className="fa-rv-eyebrow">Review actions</div>
              <button className="btn primary fa-act" disabled title="Human V2 approval arrives with the agentic review slice">Approve shape</button>
              <button className="btn fa-act" disabled title="Agentic repair arrives in the next slice">Repair with AI</button>
              <button className="btn fa-act" disabled title="The V2 editor arrives in the next slice">Edit manually</button>
              <button className="btn fa-act" disabled title="Arrives in the next slice">Cannot determine</button>
              <p className="fa-hint">Agentic critique / repair and manual editing arrive in the next slice. Nothing here can mark provisional data as approved V2 truth.</p>
            </div>
          </>
        ) : (
          <div className="fa-empty">No room selected.</div>
        )}
      </aside>
    </div>
  );
}
