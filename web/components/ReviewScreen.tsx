"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { DemoData, DemoRoom, RoomStatus } from "@/lib/demoTypes";
import { STATUS_LABEL } from "@/lib/demoTypes";
import PlanCanvas from "@/components/PlanCanvas";

type Override = { status: RoomStatus; reviewedByUser: boolean; ts: number };
type Overrides = Record<string, Override>;

const storageKey = (permit: string) => `flooring-review-demo:${permit}`;

const fmtSf = (n: number) => Math.round(n).toLocaleString("en-US");

const FILTERS: { key: "all" | RoomStatus; label: string }[] = [
  { key: "all", label: "All" },
  { key: "accepted", label: "Accepted" },
  { key: "review", label: "Needs review" },
  { key: "open", label: "Open zone" },
  { key: "draw_needed", label: "Draw needed" },
];

export default function ReviewScreen({ permit, data }: { permit: string; data: DemoData }) {
  const page = data.pages[0];
  const baseRooms = page.rooms;

  const [overrides, setOverrides] = useState<Overrides>({});
  const [hydrated, setHydrated] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | RoomStatus>("all");
  const [centerToken, setCenterToken] = useState(0);
  const [centerRoomId, setCenterRoomId] = useState<string | null>(null);

  // load persisted corrections once on mount (client-only -- avoids SSR/client
  // hydration mismatch by starting from the pipeline defaults, then applying
  // localStorage overrides right after mount)
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey(permit));
      if (raw) setOverrides(JSON.parse(raw));
    } catch {
      /* ignore corrupt storage */
    }
    setHydrated(true);
  }, [permit]);

  const persist = useCallback(
    (next: Overrides) => {
      setOverrides(next);
      try {
        window.localStorage.setItem(storageKey(permit), JSON.stringify(next));
      } catch {
        /* storage full/unavailable -- demo still works in-memory */
      }
    },
    [permit]
  );

  const effectiveRooms: (DemoRoom & { reviewedByUser: boolean })[] = useMemo(
    () =>
      baseRooms.map((r) => {
        const ov = overrides[r.id];
        return {
          ...r,
          status: ov?.status ?? r.status,
          reviewedByUser: ov?.reviewedByUser ?? false,
        };
      }),
    [baseRooms, overrides]
  );

  // POLICY: unlabeled shapes (closed geometry with no room-number anchor) are
  // not peer rows to real rooms. They never contribute to Verified/Estimated,
  // never count as "needs review", and appear only as one collapsed group row
  // in the table + de-emphasized grey on the canvas.
  const realRooms = useMemo(() => effectiveRooms.filter((r) => !r.unlabeled), [effectiveRooms]);
  const unlabeledRooms = useMemo(() => effectiveRooms.filter((r) => r.unlabeled), [effectiveRooms]);
  const [unlabeledOpen, setUnlabeledOpen] = useState(false);

  const selectedRoom = effectiveRooms.find((r) => r.id === selectedId) ?? null;

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: realRooms.length };
    for (const r of realRooms) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [realRooms]);

  const verifiedSf = useMemo(
    () => realRooms.filter((r) => r.status === "accepted").reduce((s, r) => s + (r.sf || 0), 0),
    [realRooms]
  );
  const estimatedSf = useMemo(
    () => realRooms.filter((r) => r.status !== "accepted").reduce((s, r) => s + (r.sf || 0), 0),
    [realRooms]
  );
  const nFlagged = realRooms.length - (counts.accepted ?? 0);
  const progressFrac = realRooms.length ? (counts.accepted ?? 0) / realRooms.length : 0;

  const select = useCallback(
    (id: string, center = true) => {
      setSelectedId(id);
      if (center) {
        setCenterRoomId(id);
        setCenterToken((t) => t + 1);
      }
    },
    []
  );

  const flaggedOrder = useMemo(() => realRooms.filter((r) => r.status !== "accepted"), [realRooms]);

  const jumpFlagged = useCallback(
    (dir: 1 | -1) => {
      if (flaggedOrder.length === 0) return;
      const curIdx = flaggedOrder.findIndex((r) => r.id === selectedId);
      const nextIdx =
        curIdx === -1 ? 0 : (curIdx + dir + flaggedOrder.length) % flaggedOrder.length;
      select(flaggedOrder[nextIdx].id);
    },
    [flaggedOrder, selectedId, select]
  );

  const acceptRoom = useCallback(
    (id: string, advance: boolean) => {
      const room = effectiveRooms.find((r) => r.id === id);
      if (!room || room.unlabeled) return; // unanchored shapes need Draw/Fix (v1 verbs), not Accept
      const next = { ...overrides, [id]: { status: "accepted" as RoomStatus, reviewedByUser: true, ts: Date.now() } };
      persist(next);
      if (advance) {
        // move to the next room that still needs attention (excludes the one we just accepted)
        const remaining = realRooms.filter((r) => r.id !== id && r.status !== "accepted");
        if (remaining.length) select(remaining[0].id);
      }
    },
    [overrides, persist, effectiveRooms, realRooms, select]
  );

  const resetDemo = useCallback(() => {
    try {
      window.localStorage.removeItem(storageKey(permit));
    } catch {
      /* ignore */
    }
    setOverrides({});
    setSelectedId(null);
  }, [permit]);

  // ---- keyboard: Enter = accept selected (+advance), arrows = next/prev flagged ----
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const active = document.activeElement;
      const nativeWillHandle =
        active instanceof HTMLButtonElement || active instanceof HTMLAnchorElement;
      if (e.key === "Enter") {
        if (nativeWillHandle) return; // let the focused button's own click fire, avoid double-accept
        if (selectedId) {
          e.preventDefault();
          acceptRoom(selectedId, true);
        }
      } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        jumpFlagged(1);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        jumpFlagged(-1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, acceptRoom, jumpFlagged]);

  const filteredTableRooms =
    filter === "all" ? realRooms : realRooms.filter((r) => r.status === filter);
  const unlabeledSf = unlabeledRooms.reduce((s, r) => s + (r.sf || 0), 0);

  if (!hydrated) {
    // avoid a flash of default-vs-restored totals; render once client state is known
    return (
      <main className="rv-shell">
        <div className="empty" style={{ padding: 60 }}>
          Loading review…
        </div>
      </main>
    );
  }

  return (
    <main className="rv-shell">
      <RvStyle />
      <header className="rv-header">
        <div className="rv-header-top">
          <Link href="/demo" className="back rv-back">
            ← All projects
          </Link>
          <button className="btn ghost rv-reset" onClick={resetDemo}>
            Reset demo
          </button>
        </div>
        <h1 className="rv-title">{data.project.name}</h1>
        <div className="rv-stats">
          <div className="rv-stat rv-stat-verified">
            <div className="l">Verified</div>
            <div className="v">{fmtSf(verifiedSf)} SF</div>
          </div>
          <div className="rv-stat rv-stat-estimated">
            <div className="l">Estimated</div>
            <div className="v">{fmtSf(estimatedSf)} SF</div>
          </div>
          <div className="rv-progress-wrap">
            <div className="rv-progress-label">
              <span>{Math.round(progressFrac * 100)}% reviewed</span>
              <span>{nFlagged} rooms need review</span>
            </div>
            <div className="rv-progress-track">
              <div className="rv-progress-fill" style={{ width: `${progressFrac * 100}%` }} />
            </div>
          </div>
          <button
            className="btn primary rv-checknext-header"
            onClick={() => jumpFlagged(1)}
            disabled={nFlagged === 0}
          >
            Check next →
          </button>
        </div>
      </header>

      <div className="rv-main">
        <div className="rv-canvas-col">
          <PlanCanvas
            image={page.image}
            imageWidth={page.image_width}
            imageHeight={page.image_height}
            rooms={effectiveRooms}
            selectedId={selectedId}
            onSelect={(id) => select(id, false)}
            centerToken={centerToken}
            centerRoomId={centerRoomId}
          />
        </div>

        <aside className="rv-panel">
          {selectedRoom ? (
            <>
              <div
                className={
                  selectedRoom.unlabeled
                    ? "rv-chip rv-chip-unlabeled"
                    : `rv-chip rv-chip-${selectedRoom.status}`
                }
              >
                {selectedRoom.unlabeled ? "Unanchored shape" : STATUS_LABEL[selectedRoom.status]}
                {selectedRoom.reviewedByUser && <span className="rv-checkmark">✓ reviewed by you</span>}
              </div>
              <h2 className="rv-room-name">{selectedRoom.name}</h2>
              <div className="rv-room-sf">
                {selectedRoom.sf != null ? (
                  <>
                    {fmtSf(selectedRoom.sf)} SF
                    {selectedRoom.sf_source === "schedule" && (
                      <span className="rv-sf-source"> · from schedule, not measured</span>
                    )}
                  </>
                ) : (
                  "—"
                )}
              </div>
              <div className="rv-room-material">
                <span className="rv-material-label">Material</span>
                <span className="chip">{selectedRoom.material ?? "—"}</span>
              </div>

              {(selectedRoom.evidence.schedule_row ||
                selectedRoom.evidence.printed_dim ||
                selectedRoom.evidence.why_flagged) && (
                <div className="rv-evidence">
                  {selectedRoom.evidence.schedule_row && (
                    <div className="rv-evidence-line">{selectedRoom.evidence.schedule_row}</div>
                  )}
                  {selectedRoom.evidence.printed_dim && (
                    <div className="rv-evidence-line">{selectedRoom.evidence.printed_dim}</div>
                  )}
                  {selectedRoom.evidence.why_flagged && (
                    <div className="rv-evidence-line rv-evidence-flag">
                      {selectedRoom.evidence.why_flagged}
                    </div>
                  )}
                </div>
              )}

              {selectedRoom.unlabeled && (
                <div className="rv-unlabeled-note">
                  Not counted in any total. Boundary tools (v1) will resolve shapes like this.
                </div>
              )}
              {!selectedRoom.unlabeled && selectedRoom.status === "accepted" && (
                <div className="rv-unlabeled-note">
                  Accepted — locked into the estimate totals.
                </div>
              )}
              <div className="rv-actions">
                {!selectedRoom.unlabeled && (
                  <button className="btn primary rv-accept" onClick={() => acceptRoom(selectedRoom.id, true)}>
                    Accept
                  </button>
                )}
                <button
                  className="btn ghost"
                  onClick={() => jumpFlagged(1)}
                  disabled={nFlagged === 0}
                >
                  Check next
                </button>
              </div>
              <div className="rv-actions rv-actions-disabled">
                <button className="btn disabled" disabled title="Coming in v1">
                  Fix boundary
                </button>
                <button className="btn disabled" disabled title="Coming in v1">
                  Draw room
                </button>
                <button className="btn disabled" disabled title="Coming in v1">
                  Split zone
                </button>
              </div>
            </>
          ) : (
            <div className="rv-panel-empty">
              Select a room on the plan, or a row in the table below, to see its evidence.
            </div>
          )}
        </aside>
      </div>

      <section className="rv-queue">
        <div className="rv-filters">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={`rv-filter-chip ${filter === f.key ? "on" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label} <span className="rv-filter-count">{counts[f.key] ?? 0}</span>
            </button>
          ))}
        </div>
        <div className="tblwrap">
          <table className="rv-table">
            <thead>
              <tr>
                <th>Room</th>
                <th>Status</th>
                <th>Material</th>
                <th className="m">SF</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {filteredTableRooms.map((r) => (
                <tr
                  key={r.id}
                  className={r.id === selectedId ? "rv-row-selected" : ""}
                  onClick={() => select(r.id)}
                >
                  <td>{r.name}</td>
                  <td>
                    <span className={`rv-chip rv-chip-sm rv-chip-${r.status}`}>
                      {STATUS_LABEL[r.status]}
                    </span>
                  </td>
                  <td>{r.material ?? "—"}</td>
                  <td className="m">
                    {r.sf != null ? fmtSf(r.sf) : "—"}
                    {r.sf_source === "schedule" && <span className="rv-sf-source"> (sched.)</span>}
                  </td>
                  <td className="rv-note">
                    {r.evidence.why_flagged || r.evidence.schedule_row || "—"}
                  </td>
                </tr>
              ))}
              {filter === "all" && unlabeledRooms.length > 0 && (
                <>
                  <tr
                    className="rv-row-unlabeled-group"
                    onClick={() => setUnlabeledOpen((o) => !o)}
                  >
                    <td colSpan={5}>
                      <span className="rv-unlabeled-caret">{unlabeledOpen ? "▾" : "▸"}</span>
                      {unlabeledRooms.length} unlabeled shapes, {fmtSf(unlabeledSf)} SF total —
                      geometry closed but no room number anchored; not counted in any total.
                      Click to {unlabeledOpen ? "collapse" : "expand"}.
                    </td>
                  </tr>
                  {unlabeledOpen &&
                    unlabeledRooms.map((r) => (
                      <tr
                        key={r.id}
                        className={`rv-row-unlabeled ${r.id === selectedId ? "rv-row-selected" : ""}`}
                        onClick={() => select(r.id)}
                      >
                        <td>{r.name}</td>
                        <td>
                          <span className="rv-chip rv-chip-sm rv-chip-unlabeled">Unanchored</span>
                        </td>
                        <td>—</td>
                        <td className="m">{r.sf != null ? fmtSf(r.sf) : "—"}</td>
                        <td className="rv-note">{r.evidence.why_flagged ?? "—"}</td>
                      </tr>
                    ))}
                </>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function RvStyle() {
  return (
    <style>{`
:root {
  --rv-green: #1f9d55; --rv-green-bg: #e4f5ea;
  --rv-amber: #b8860b; --rv-amber-bg: #fbf1d9;
  --rv-blue: #2f6fd9; --rv-blue-bg: #e6edfc;
  --rv-red: #d13b3b; --rv-red-bg: #fbe7e7;
}
/* Light mode is the app default everywhere (founder call 2026-07-10) —
   dark-via-OS-preference override removed. */

.rv-shell { max-width: 1400px; margin: 0 auto; padding: 0 18px 60px; }
.rv-header { padding: 18px 0 10px; }
.rv-header-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.rv-reset { margin: 0; }
.rv-title { font-size: clamp(20px, 3vw, 27px); font-weight: 700; letter-spacing: -0.01em; margin: 4px 0 16px; }
.rv-stats { display: flex; align-items: stretch; gap: 12px; flex-wrap: wrap; }
.rv-stat { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 12px 18px; min-width: 130px; }
.rv-stat .l { font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.rv-stat .v { font-family: var(--font-mono); font-size: 22px; font-weight: 700; margin-top: 4px; }
.rv-stat-verified .v { color: var(--rv-green); }
.rv-stat-estimated .v { color: var(--muted); }
.rv-progress-wrap { flex: 1 1 220px; min-width: 200px; align-self: center; }
.rv-progress-label { display: flex; justify-content: space-between; font-size: 12.5px; color: var(--muted); margin-bottom: 6px; font-family: var(--font-mono); }
.rv-progress-track { height: 8px; border-radius: 5px; background: var(--surface-2); border: 1px solid var(--line); overflow: hidden; }
.rv-progress-fill { height: 100%; background: var(--rv-green); transition: width .2s ease; }
.rv-checknext-header { align-self: center; white-space: nowrap; }

.rv-main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; margin-top: 6px; }
.rv-canvas-col { min-width: 0; }
/* the plan IS the product: canvas + evidence panel fill the viewport below
   the header; the review table lives below the fold */
.rv-canvas-shell { position: relative; background: var(--surface-2); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; height: max(480px, calc(100vh - 300px)); }
.rv-canvas-viewport { position: absolute; inset: 0; overflow: auto; display: flex; }
.rv-canvas-stage { position: relative; margin: auto; flex-shrink: 0; }
.rv-canvas-svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.rv-canvas-tools { position: absolute; right: 12px; bottom: 12px; display: flex; gap: 6px; z-index: 5; }
.rv-canvas-tools button { font-family: var(--font-mono); font-size: 15px; min-width: 34px; height: 34px; padding: 0 9px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); cursor: pointer; }
.rv-canvas-tools button:hover { border-color: var(--accent); }

.rv-poly { cursor: pointer; stroke-width: 1.5; fill-opacity: 0.35; vector-effect: non-scaling-stroke; transition: fill-opacity .1s ease; }
.rv-poly-accepted { fill: var(--rv-green); stroke: color-mix(in srgb, var(--rv-green) 70%, black); }
.rv-poly-review { fill: var(--rv-amber); stroke: color-mix(in srgb, var(--rv-amber) 70%, black); }
.rv-poly-open { fill: var(--rv-blue); stroke: color-mix(in srgb, var(--rv-blue) 70%, black); }
.rv-poly-draw_needed { fill: var(--rv-red); stroke: color-mix(in srgb, var(--rv-red) 70%, black); }
.rv-poly-unlabeled { fill: var(--muted); stroke: var(--muted); fill-opacity: 0.10; stroke-dasharray: 5 4; }
.rv-poly-hovered { fill-opacity: 0.55; }
.rv-poly-unlabeled.rv-poly-hovered { fill-opacity: 0.25; }
.rv-poly-selected { stroke-width: 3.5; fill-opacity: 0.6; }
.rv-poly-unlabeled.rv-poly-selected { fill-opacity: 0.3; }

.rv-panel { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 18px 20px; height: max(480px, calc(100vh - 300px)); overflow-y: auto; display: flex; flex-direction: column; }
.rv-panel-empty { color: var(--muted); font-size: 14.5px; margin: auto 0; text-align: center; }
.rv-room-name { font-size: 19px; font-weight: 700; margin: 10px 0 4px; }
.rv-room-sf { font-family: var(--font-mono); font-size: 24px; font-weight: 700; margin-bottom: 10px; }
.rv-sf-source { font-family: var(--font-sans); font-size: 12px; font-weight: 400; color: var(--muted); }
.rv-room-material { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); margin-bottom: 14px; }
.rv-material-label { font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
.rv-evidence { display: flex; flex-direction: column; gap: 8px; background: var(--surface-2); border-radius: 10px; padding: 12px 14px; margin-bottom: 16px; }
.rv-evidence-line { font-size: 13.5px; line-height: 1.45; }
.rv-evidence-flag { color: var(--muted); }
.rv-actions { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.rv-actions-disabled { margin-top: 4px; padding-top: 10px; border-top: 1px solid var(--line); }
.rv-accept { flex: 1; min-width: 100px; }

.rv-chip { display: inline-flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 11.5px; font-weight: 600; padding: 4px 10px; border-radius: 999px; text-transform: uppercase; letter-spacing: .03em; width: fit-content; }
.rv-chip-sm { font-size: 10.5px; padding: 2px 8px; text-transform: none; letter-spacing: 0; font-weight: 500; }
.rv-chip-accepted { color: var(--rv-green); background: var(--rv-green-bg); }
.rv-chip-review { color: var(--rv-amber); background: var(--rv-amber-bg); }
.rv-chip-open { color: var(--rv-blue); background: var(--rv-blue-bg); }
.rv-chip-draw_needed { color: var(--rv-red); background: var(--rv-red-bg); }
.rv-chip-unlabeled { color: var(--muted); background: var(--surface-2); border: 1px dashed var(--line); }
.rv-checkmark { font-family: var(--font-sans); text-transform: none; letter-spacing: 0; font-weight: 500; color: var(--muted); font-size: 11px; }
.rv-unlabeled-note { font-size: 12.5px; color: var(--muted); margin-bottom: 12px; }
.rv-row-unlabeled-group td { color: var(--muted); font-size: 12.5px; background: var(--surface-2); }
.rv-unlabeled-caret { display: inline-block; width: 16px; color: var(--muted); }
.rv-row-unlabeled td { color: var(--muted); }

.rv-queue { margin-top: 22px; }
.rv-queue .tblwrap { overflow-x: auto; }
.rv-filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.rv-filter-chip { font-family: var(--font-mono); font-size: 12.5px; padding: 7px 12px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--muted); cursor: pointer; }
.rv-filter-chip:hover { border-color: var(--accent); }
.rv-filter-chip.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.rv-filter-count { opacity: .75; margin-left: 4px; }
.rv-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.rv-table th { text-align: left; font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); padding: 8px 12px; border-bottom: 1px solid var(--line); }
.rv-table th.m, .rv-table td.m { text-align: right; }
.rv-table td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
.rv-table tr { cursor: pointer; }
.rv-table tr:hover td { background: var(--surface-2); }
.rv-table tr.rv-row-selected td { background: color-mix(in srgb, var(--accent) 10%, transparent); }
.rv-note { color: var(--muted); font-size: 12.5px; max-width: 340px; }

@media (max-width: 768px) {
  .rv-main { grid-template-columns: 1fr; }
  .rv-canvas-shell, .rv-panel { height: 46vh; }
  .rv-panel { height: auto; max-height: none; }
  .rv-actions-disabled { display: none; }
  .rv-actions { position: sticky; bottom: 0; background: var(--surface); padding-top: 8px; }
  .rv-accept, .rv-actions .btn { min-height: 48px; font-size: 15px; }
  .rv-checknext-header { width: 100%; min-height: 44px; }
  .rv-stats { gap: 8px; }
  .rv-stat { flex: 1 1 45%; min-width: 0; padding: 10px 12px; }
}
`}</style>
  );
}
