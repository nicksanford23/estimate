"use client";

// Geometry annotation editor — FUNCTIONAL PILOT SLICE.
//
// DESIGN-LOOP CAVEAT: there is NO approved mockup for this screen (design-loop
// SKILL: approved images are the spec for real screens). This is a lean,
// hand-rolled SVG polygon editor for the 36-room geometry pilot, styled to
// match the existing /v2 pages (globals.css tokens/classes) but NOT a
// signed-off product surface. Nick must visually review before it counts.
//
// What it does: pick a task -> outline a provisional flooring region on the
// level viewport (vertices in PIXEL space) -> pick a V1 outcome + coarse
// boundary types -> save. Save converts pixels to PDF/contract coords
// server-side and appends one row to the V1 human outcomes JSONL (packet stays
// immutable). V1 rows are proposals for V2 re-review, not qualified truth.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  NO_POLYGON_OUTCOMES,
  POLYGON_OUTCOMES,
  polygonAreaSf,
  type BoardData,
  type BoundaryType,
  type Outcome,
  type OutcomeRow,
  type Pt,
  type TaskView,
} from "@/lib/annotateTypes";

type Props = { data: BoardData };

const OUTCOME_LABEL: Record<Outcome, string> = {
  enclosed_polygon: "Enclosed polygon",
  open_zone: "Open zone",
  finish_zone: "Finish zone",
  not_in_scope: "Not in scope",
  unresolved: "Unresolved",
};

interface EditState {
  points: Pt[];
  closed: boolean;
  outcome: Outcome | "";
  boundaryTypes: BoundaryType[];
  openZoneMembers: string[];
  notes: string;
  proposalSource: string;
  selectedVertex: number | null;
}

function initEdit(task: TaskView): EditState {
  const latest = task.latest;
  if (latest) {
    return {
      points: task.latest_polygon_px ? task.latest_polygon_px.map((p) => [p[0], p[1]]) : [],
      closed: !!(task.latest_polygon_px && task.latest_polygon_px.length >= 3),
      outcome: latest.outcome,
      boundaryTypes: [...latest.boundary_types],
      openZoneMembers: [...latest.open_zone_members],
      notes: latest.notes ?? "",
      proposalSource: latest.proposal_source || "drawn_from_scratch",
      selectedVertex: null,
    };
  }
  return {
    points: [],
    closed: false,
    outcome: "",
    boundaryTypes: [],
    openZoneMembers: [],
    notes: "",
    proposalSource: "drawn_from_scratch",
    selectedVertex: null,
  };
}

export default function AnnotateBoard({ data }: Props) {
  const [tasks, setTasks] = useState<TaskView[]>(data.tasks);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = useMemo(() => tasks.find((t) => t.task_id === selectedId) ?? null, [tasks, selectedId]);

  const levels = useMemo(() => {
    const by: Record<string, TaskView[]> = {};
    for (const t of tasks) (by[t.level] ??= []).push(t);
    for (const k of Object.keys(by)) by[k].sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true }));
    return Object.keys(by)
      .sort()
      .map((level) => ({ level, items: by[level] }));
  }, [tasks]);

  const savedCount = tasks.filter((t) => t.latest).length;

  return (
    <div className="container" style={{ paddingBottom: 60 }}>
      <div className="page-head">
        <span className="eyebrow">Geometry annotation · V1 provisional review</span>
        <h1>Room outlines — {data.permit}</h1>
        <p>
          Review or correct a proposed outline, then record a provisional V1 outcome. Rows are append-only and the
          packet is never mutated. Image source: {data.imageSourceNote}.
        </p>
        <p style={{ fontSize: 13, color: "var(--warn)", marginTop: 4 }}>
          This editor does not capture the complete Geometry V2 contract. Saving here does not create training or
          evaluation truth; every row must be re-reviewed in the V2 editor after it is implemented.
        </p>
        <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
          No approved mockup exists yet — this remains a functional pilot pending founder visual sign-off.
        </p>
      </div>

      {!selected ? (
        <TaskList levels={levels} savedCount={savedCount} total={tasks.length} onOpen={setSelectedId} />
      ) : (
        <Editor
          key={selected.task_id}
          data={data}
          task={selected}
          onBack={() => setSelectedId(null)}
          onSaved={(row, polygonPx) => {
            setTasks((prev) =>
              prev.map((t) =>
                t.task_id === row.task_id ? { ...t, latest: row, latest_polygon_px: polygonPx } : t
              )
            );
          }}
        />
      )}
    </div>
  );
}

// ---------- task list ----------

function statusChip(task: TaskView) {
  if (!task.latest) return <span className="chip">pending</span>;
  const o = task.latest.outcome;
  const bg =
    o === "not_in_scope" || o === "unresolved" ? "var(--surface-2)" : "var(--good-bg)";
  const color =
    o === "not_in_scope" || o === "unresolved" ? "var(--muted)" : "var(--good)";
  return (
    <span className="chip" style={{ background: bg, color, borderColor: "transparent" }}>
      {OUTCOME_LABEL[o]}
    </span>
  );
}

function TaskList({
  levels,
  savedCount,
  total,
  onOpen,
}: {
  levels: { level: string; items: TaskView[] }[];
  savedCount: number;
  total: number;
  onOpen: (id: string) => void;
}) {
  return (
    <div>
      <div className="v2progress" style={{ marginTop: 0 }}>
        {savedCount} / {total} rooms have a saved provisional V1 outcome
        <div className="v2progress-bar" style={{ maxWidth: 320 }}>
          <div className="v2progress-fill" style={{ width: `${(savedCount / total) * 100}%` }} />
        </div>
      </div>

      {levels.map(({ level, items }) => (
        <div key={level}>
          <div className="section-title">
            {level} · {items[0]?.sheet_number} · {items.length} rooms
          </div>
          <div className="permit-grid">
            {items.map((t) => (
              <button
                key={t.task_id}
                className="permit-card"
                style={{ cursor: "pointer", textAlign: "left" }}
                onClick={() => onOpen(t.task_id)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <span className="pnum">
                    {t.code} · {t.name}
                  </span>
                  {statusChip(t)}
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                  {t.schedule_area_sf_reference != null && (
                    <span className="chip" title="diagnostic reference only — never a target to match">
                      {t.schedule_area_sf_reference} SF (schedule ref)
                    </span>
                  )}
                  {t.floor_material_reference && <span className="chip">{t.floor_material_reference}</span>}
                  {t.proposal && <span className="chip" style={{ color: "var(--accent-ink)" }}>proposal avail.</span>}
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- editor ----------

const MOVE_THRESHOLD = 3;

function Editor({
  data,
  task,
  onBack,
  onSaved,
}: {
  data: BoardData;
  task: TaskView;
  onBack: () => void;
  onSaved: (row: OutcomeRow, polygonPx: Pt[] | null) => void;
}) {
  const [imgW, imgH] = task.transform.pixel_size;
  const [edit, setEdit] = useState<EditState>(() => initEdit(task));
  const [zoom, setZoom] = useState<number>(() => Math.min(0.32, 700 / imgH));
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const svgRef = useRef<SVGSVGElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const drag = useRef<{
    kind: "vertex" | "bg";
    idx: number;
    sx: number;
    sy: number;
    scrollL: number;
    scrollT: number;
    moved: boolean;
  } | null>(null);
  const pendingScroll = useRef<{ ix: number; iy: number; cx: number; cy: number } | null>(null);

  const displayW = imgW * zoom;
  const displayH = imgH * zoom;
  const imageUrl = `/api/v2/annotate/image?permit=${encodeURIComponent(data.permit)}&page=${task.page_index}`;

  const areaSf = edit.closed && edit.points.length >= 3 ? polygonAreaSf(edit.points) : null;
  const memberOptions = (data.levelCodes[task.level] ?? []).filter((c) => c.code !== task.code);

  const screenToImg = useCallback((clientX: number, clientY: number): Pt | null => {
    const svg = svgRef.current;
    if (!svg) return null;
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
    return [p.x, p.y];
  }, []);

  // Non-passive wheel zoom (React onWheel is passive; can't preventDefault).
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const img = screenToImg(e.clientX, e.clientY);
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      setZoom((z) => {
        const nz = Math.min(5, Math.max(0.08, z * factor));
        if (img) pendingScroll.current = { ix: img[0], iy: img[1], cx: e.clientX, cy: e.clientY };
        return nz;
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [screenToImg]);

  // Keep the cursor's image point stable across a wheel-zoom.
  useEffect(() => {
    const el = scrollRef.current;
    const ps = pendingScroll.current;
    if (!el || !ps) return;
    pendingScroll.current = null;
    const rect = el.getBoundingClientRect();
    el.scrollLeft = ps.ix * zoom - (ps.cx - rect.left);
    el.scrollTop = ps.iy * zoom - (ps.cy - rect.top);
  }, [zoom]);

  const clampPt = useCallback(
    (p: Pt): Pt => [Math.max(0, Math.min(imgW, p[0])), Math.max(0, Math.min(imgH, p[1]))],
    [imgW, imgH]
  );

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    const target = e.target as SVGElement;
    const vtx = target.getAttribute("data-vtx");
    const mid = target.getAttribute("data-mid");
    (e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId);

    if (mid != null) {
      // Insert a vertex at this edge midpoint, then drag it (edge-pull UX).
      const i = Number(mid);
      const img = screenToImg(e.clientX, e.clientY);
      if (img) {
        setEdit((s) => {
          const pts = [...s.points];
          pts.splice(i + 1, 0, clampPt(img));
          return { ...s, points: pts, selectedVertex: i + 1 };
        });
        drag.current = { kind: "vertex", idx: i + 1, sx: e.clientX, sy: e.clientY, scrollL: 0, scrollT: 0, moved: false };
      }
      return;
    }
    if (vtx != null) {
      drag.current = { kind: "vertex", idx: Number(vtx), sx: e.clientX, sy: e.clientY, scrollL: 0, scrollT: 0, moved: false };
      return;
    }
    const el = scrollRef.current;
    drag.current = {
      kind: "bg",
      idx: -1,
      sx: e.clientX,
      sy: e.clientY,
      scrollL: el?.scrollLeft ?? 0,
      scrollT: el?.scrollTop ?? 0,
      moved: false,
    };
  };

  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.sx;
    const dy = e.clientY - d.sy;
    if (Math.abs(dx) > MOVE_THRESHOLD || Math.abs(dy) > MOVE_THRESHOLD) d.moved = true;
    if (d.kind === "vertex" && d.moved) {
      const img = screenToImg(e.clientX, e.clientY);
      if (img)
        setEdit((s) => {
          const pts = [...s.points];
          pts[d.idx] = clampPt(img);
          return { ...s, points: pts };
        });
    } else if (d.kind === "bg" && d.moved) {
      const el = scrollRef.current;
      if (el) {
        el.scrollLeft = d.scrollL - dx;
        el.scrollTop = d.scrollT - dy;
      }
    }
  };

  const onPointerUp = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (d.moved) return; // was a drag (vertex move or pan)
    if (d.kind === "vertex") {
      // click a vertex: close on first vertex, else select it.
      setEdit((s) => {
        if (d.idx === 0 && !s.closed && s.points.length >= 3) return { ...s, closed: true, selectedVertex: null };
        return { ...s, selectedVertex: d.idx };
      });
    } else {
      // background click: place a vertex while the ring is open.
      const img = screenToImg(e.clientX, e.clientY);
      if (img)
        setEdit((s) => {
          if (s.closed) return { ...s, selectedVertex: null };
          return { ...s, points: [...s.points, clampPt(img)], selectedVertex: s.points.length };
        });
    }
  };

  const toggleBoundary = (b: BoundaryType) =>
    setEdit((s) => ({
      ...s,
      boundaryTypes: s.boundaryTypes.includes(b) ? s.boundaryTypes.filter((x) => x !== b) : [...s.boundaryTypes, b],
    }));
  const toggleMember = (code: string) =>
    setEdit((s) => ({
      ...s,
      openZoneMembers: s.openZoneMembers.includes(code)
        ? s.openZoneMembers.filter((x) => x !== code)
        : [...s.openZoneMembers, code],
    }));

  const loadProposal = () => {
    if (!task.proposal) return;
    setEdit((s) => ({
      ...s,
      points: task.proposal!.polygon_px.map((p) => clampPt([p[0], p[1]])),
      closed: true,
      proposalSource: task.proposal!.source,
      selectedVertex: null,
    }));
  };

  const deleteSelected = () =>
    setEdit((s) => {
      if (s.selectedVertex == null) return s;
      const pts = s.points.filter((_, i) => i !== s.selectedVertex);
      return { ...s, points: pts, selectedVertex: null, closed: s.closed && pts.length >= 3 };
    });
  const clearPolygon = () =>
    setEdit((s) => ({ ...s, points: [], closed: false, selectedVertex: null, proposalSource: "drawn_from_scratch" }));

  // client-side validity mirror of the server rules (server re-validates).
  const validity = useMemo(() => {
    if (!edit.outcome) return { ok: false, why: "Pick an outcome." };
    if (POLYGON_OUTCOMES.has(edit.outcome)) {
      if (!edit.closed || edit.points.length < 3) return { ok: false, why: "Close a polygon (≥3 vertices) for this outcome." };
      if (edit.boundaryTypes.length < 1) return { ok: false, why: "Pick at least one boundary type." };
    }
    if (NO_POLYGON_OUTCOMES.has(edit.outcome) && edit.points.length > 0)
      return { ok: false, why: `${OUTCOME_LABEL[edit.outcome]} must not carry a polygon — clear it.` };
    return { ok: true, why: "" };
  }, [edit]);

  const save = async () => {
    setSaving(true);
    setMsg(null);
    const usePolygon = edit.outcome !== "" && POLYGON_OUTCOMES.has(edit.outcome) && edit.closed;
    const polygonPx = usePolygon ? edit.points : null;
    try {
      const res = await fetch("/api/v2/annotate/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          permit: data.permit,
          task_id: task.task_id,
          outcome: edit.outcome,
          boundary_types: edit.boundaryTypes,
          polygon_px: polygonPx,
          open_zone_members: edit.openZoneMembers,
          notes: edit.notes,
          proposal_source: usePolygon ? edit.proposalSource : "drawn_from_scratch",
        }),
      });
      const json = (await res.json()) as { ok?: boolean; row?: OutcomeRow; error?: string };
      if (!res.ok || !json.ok || !json.row) {
        setMsg(`Save failed: ${json.error ?? res.statusText}`);
      } else {
        onSaved(json.row, polygonPx);
        setMsg("Saved as provisional V1 review. V2 re-review is still required.");
      }
    } catch (err) {
      setMsg(`Save error: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const r = 6 / zoom;
  const rMid = 4 / zoom;
  const sw = 1.6 / zoom;
  const showMids = edit.points.length >= 2;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <button className="btn" onClick={onBack}>
          ← All rooms
        </button>
        <strong style={{ fontFamily: "var(--font-mono)" }}>
          {task.code} · {task.name}
        </strong>
        <span className="chip">
          {task.level} · {task.sheet_number}
        </span>
        {statusChip(task)}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16, alignItems: "start" }}>
        {/* canvas */}
        <div>
          <div className="grv-togglepills" style={{ marginBottom: 8, flexWrap: "wrap" }}>
            <button className="btn" onClick={() => setZoom((z) => Math.min(5, z * 1.25))}>
              Zoom +
            </button>
            <button className="btn" onClick={() => setZoom((z) => Math.max(0.08, z / 1.25))}>
              Zoom −
            </button>
            <button
              className="btn"
              onClick={() => {
                const el = scrollRef.current;
                if (el) setZoom(Math.min(el.clientWidth / imgW, el.clientHeight / imgH));
              }}
            >
              Fit
            </button>
            <span className="chip" style={{ alignSelf: "center" }}>
              {Math.round(zoom * 100)}%
            </span>
            {task.proposal && (
              <button className="btn" onClick={loadProposal} title={`Start from ${task.proposal.source}`}>
                Load machine proposal
              </button>
            )}
          </div>
          <div
            ref={scrollRef}
            style={{
              border: "1px solid var(--line)",
              borderRadius: 12,
              background: "#14181d",
              overflow: "auto",
              height: "72vh",
              position: "relative",
              touchAction: "none",
            }}
          >
            <div style={{ position: "relative", width: displayW, height: displayH }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt={`${task.level} viewport`}
                width={displayW}
                height={displayH}
                draggable={false}
                style={{ display: "block", position: "absolute", inset: 0, userSelect: "none" }}
              />
              <svg
                ref={svgRef}
                width={displayW}
                height={displayH}
                viewBox={`0 0 ${imgW} ${imgH}`}
                style={{ position: "absolute", inset: 0, cursor: edit.closed ? "grab" : "crosshair", touchAction: "none" }}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
              >
                {/* room-label anchor marker (hint, not a verdict) */}
                {task.anchor_px && (
                  <g pointerEvents="none" stroke="#ffb703" strokeWidth={sw}>
                    <circle cx={task.anchor_px[0]} cy={task.anchor_px[1]} r={r * 1.4} fill="none" />
                    <line x1={task.anchor_px[0] - r * 2} y1={task.anchor_px[1]} x2={task.anchor_px[0] + r * 2} y2={task.anchor_px[1]} />
                    <line x1={task.anchor_px[0]} y1={task.anchor_px[1] - r * 2} x2={task.anchor_px[0]} y2={task.anchor_px[1] + r * 2} />
                  </g>
                )}

                {edit.points.length >= 2 &&
                  (edit.closed ? (
                    <polygon
                      points={edit.points.map((p) => `${p[0]},${p[1]}`).join(" ")}
                      fill="rgba(31,78,121,0.22)"
                      stroke="#1f4e79"
                      strokeWidth={sw}
                      pointerEvents="none"
                    />
                  ) : (
                    <polyline
                      points={edit.points.map((p) => `${p[0]},${p[1]}`).join(" ")}
                      fill="none"
                      stroke="#1f4e79"
                      strokeWidth={sw}
                      strokeDasharray={`${sw * 3} ${sw * 2}`}
                      pointerEvents="none"
                    />
                  ))}

                {/* edge midpoints (insert handles) */}
                {showMids &&
                  edit.points.map((p, i) => {
                    const next = edit.points[(i + 1) % edit.points.length];
                    if (!edit.closed && i === edit.points.length - 1) return null;
                    const mx = (p[0] + next[0]) / 2;
                    const my = (p[1] + next[1]) / 2;
                    return (
                      <circle
                        key={`m${i}`}
                        data-mid={i}
                        cx={mx}
                        cy={my}
                        r={rMid}
                        fill="#fff"
                        stroke="#1f4e79"
                        strokeWidth={sw}
                        opacity={0.7}
                        style={{ cursor: "copy" }}
                      />
                    );
                  })}

                {/* vertices */}
                {edit.points.map((p, i) => (
                  <circle
                    key={`v${i}`}
                    data-vtx={i}
                    cx={p[0]}
                    cy={p[1]}
                    r={r}
                    fill={i === edit.selectedVertex ? "#c23b3b" : i === 0 && !edit.closed ? "#2e7d57" : "#1f4e79"}
                    stroke="#fff"
                    strokeWidth={sw}
                    style={{ cursor: "pointer" }}
                  />
                ))}
              </svg>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            {!edit.closed && edit.points.length >= 3 && (
              <button className="btn" onClick={() => setEdit((s) => ({ ...s, closed: true }))}>
                Close polygon
              </button>
            )}
            <button className="btn" onClick={deleteSelected} disabled={edit.selectedVertex == null}>
              Delete vertex
            </button>
            <button className="btn" onClick={clearPolygon} disabled={edit.points.length === 0}>
              Clear
            </button>
            <span className="chip" style={{ alignSelf: "center" }}>
              {edit.points.length} vertices {edit.closed ? "· closed" : "· open"}
            </span>
            <span className="chip" style={{ alignSelf: "center", color: "var(--accent-ink)" }}>
              area: {areaSf != null ? `${areaSf.toFixed(1)} SF` : "—"} (computed, display only)
            </span>
          </div>
          <p className="hint" style={{ marginTop: 8 }}>
            Click to drop vertices; click the first (green) vertex or “Close polygon” to close. Drag a vertex to adjust,
            drag an edge midpoint to insert, drag the image to pan, wheel to zoom. Orange crosshair = room label.
          </p>
        </div>

        {/* controls */}
        <div className="rf-left" style={{ position: "sticky", top: 18 }}>
          <div className="rf-eyebrow">Reference (never a target)</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
            {task.schedule_area_sf_reference != null && (
              <span className="chip">{task.schedule_area_sf_reference} SF (schedule ref)</span>
            )}
            {task.floor_material_reference && <span className="chip">{task.floor_material_reference}</span>}
          </div>

          <div className="rf-eyebrow">Outcome</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
            {task.allowed_outcomes.map((o) => (
              <label key={o} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, cursor: "pointer" }}>
                <input
                  type="radio"
                  name="outcome"
                  checked={edit.outcome === o}
                  onChange={() => setEdit((s) => ({ ...s, outcome: o }))}
                />
                {OUTCOME_LABEL[o]}
              </label>
            ))}
          </div>

          <div className="rf-eyebrow">Boundary types</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
            {task.allowed_boundary_types.map((b) => (
              <button
                key={b}
                className="label-btn"
                onClick={() => toggleBoundary(b)}
                style={
                  edit.boundaryTypes.includes(b)
                    ? { background: "var(--accent)", color: "#fff", borderColor: "var(--accent)" }
                    : undefined
                }
              >
                {b}
              </button>
            ))}
          </div>

          {edit.outcome === "open_zone" && memberOptions.length > 0 && (
            <>
              <div className="rf-eyebrow">Open-zone members (same level)</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
                {memberOptions.map((c) => (
                  <button
                    key={c.code}
                    className="label-btn"
                    title={c.name}
                    onClick={() => toggleMember(c.code)}
                    style={
                      edit.openZoneMembers.includes(c.code)
                        ? { background: "var(--good)", color: "#fff", borderColor: "var(--good)" }
                        : undefined
                    }
                  >
                    {c.code}
                  </button>
                ))}
              </div>
            </>
          )}

          <div className="rf-eyebrow">Notes</div>
          <textarea
            value={edit.notes}
            onChange={(e) => setEdit((s) => ({ ...s, notes: e.target.value }))}
            placeholder="Why this boundary / why unresolved / anything a reviewer needs."
            style={{
              width: "100%",
              minHeight: 64,
              resize: "vertical",
              borderRadius: 9,
              border: "1px solid var(--line)",
              background: "var(--surface-2)",
              color: "var(--ink)",
              fontFamily: "var(--font-sans)",
              fontSize: 13.5,
              padding: "9px 12px",
              marginBottom: 12,
            }}
          />

          {edit.proposalSource !== "drawn_from_scratch" && (
            <p className="v2micro" style={{ marginTop: 0 }}>
              Started from proposal: {edit.proposalSource}
            </p>
          )}

          {!validity.ok && <p style={{ fontSize: 12.5, color: "var(--warn)", margin: "0 0 8px" }}>{validity.why}</p>}
          {msg && (
            <p style={{ fontSize: 12.5, color: msg.startsWith("Saved") ? "var(--good)" : "var(--bad)", margin: "0 0 8px" }}>
              {msg}
            </p>
          )}

          <button className="btn primary" style={{ width: "100%" }} onClick={save} disabled={!validity.ok || saving}>
            {saving ? "Saving…" : task.latest ? "Save new provisional review (supersedes)" : "Save provisional review"}
          </button>
          {task.latest && (
            <p className="v2micro">
              Last saved {new Date(task.latest.saved_at).toLocaleString()} by {task.latest.reviewer}. Saving appends a
              new row; history is preserved.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
