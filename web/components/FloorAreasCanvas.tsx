"use client";

// Floor Areas plan canvas (V2_PRODUCT_REBUILD_PLAN_V1.md §7.2, §7.3). A
// read-only, high-resolution viewer that dominates the workspace: mouse-wheel /
// trackpad / pinch zoom, click-drag pan, fit-to-room, fit-full-floor, and
// click-an-edge to open its close-up. Editing/repair land in a later slice, so
// nothing here mutates geometry — it reserves the states, it does not fake them.
//
// Overlay colors follow §11.1: magenta = original machine proposal, blue =
// provisional human outline. Green (human-approved) does not appear because no
// geometry is approved in this dataset yet.

import { useCallback, useEffect, useRef, useState } from "react";
import type { FloorAreaRoom } from "@/lib/floorAreas";

type Pt = [number, number];
export type Overlay = "proposal" | "human";
export type ViewMode = "room" | "floor";

const COLOR = {
  proposal: "#c026a9", // magenta — original machine proposal
  human: "#1f6fb2", // blue — provisional human outline
  edgeSel: "#00c2d1", // cyan — the edge currently being inspected (not a verdict)
  anchor: "#e08a00", // orange — room-label location hint
};

function activePolygon(room: FloorAreaRoom, overlay: Overlay): Pt[] | null {
  if (overlay === "proposal") return room.proposal?.polygonPx ?? null;
  return room.human?.polygonPx ?? null;
}

export default function FloorAreasCanvas({
  permit,
  room,
  overlay,
  viewMode,
  selectedEdge,
  onSelectEdge,
  fitToken,
}: {
  permit: string;
  room: FloorAreaRoom;
  overlay: Overlay;
  viewMode: ViewMode;
  selectedEdge: number | null;
  onSelectEdge: (i: number | null) => void;
  fitToken: number;
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [zoom, setZoom] = useState(0.2);
  const drag = useRef<{ sx: number; sy: number; l: number; t: number; moved: boolean } | null>(null);
  const pendingScroll = useRef<{ ix: number; iy: number; cx: number; cy: number } | null>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinchDist = useRef(0);

  const { imgW, imgH } = room;
  const poly = activePolygon(room, overlay);
  const imageUrl = `/api/v2/annotate/image?permit=${encodeURIComponent(permit)}&page=${room.pageIndex}`;
  const displayW = imgW * zoom;
  const displayH = imgH * zoom;

  // ---- fit helpers ----
  const fitBox = useCallback(
    (x0: number, y0: number, x1: number, y1: number, pad: number) => {
      const el = scrollRef.current;
      if (!el) return;
      x0 = Math.max(0, x0 - pad);
      y0 = Math.max(0, y0 - pad);
      x1 = Math.min(imgW, x1 + pad);
      y1 = Math.min(imgH, y1 + pad);
      const z = Math.min(4, Math.max(0.05, Math.min(el.clientWidth / (x1 - x0), el.clientHeight / (y1 - y0))));
      setZoom(z);
      requestAnimationFrame(() => {
        el.scrollLeft = ((x0 + x1) / 2) * z - el.clientWidth / 2;
        el.scrollTop = ((y0 + y1) / 2) * z - el.clientHeight / 2;
      });
    },
    [imgW, imgH]
  );

  const fitToTarget = useCallback(() => {
    // full floor
    if (viewMode === "floor") return fitBox(0, 0, imgW, imgH, 0);
    // a single edge close-up
    if (selectedEdge != null && poly && poly.length >= 2) {
      const a = poly[selectedEdge % poly.length];
      const b = poly[(selectedEdge + 1) % poly.length];
      const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
      return fitBox(
        Math.min(a[0], b[0]),
        Math.min(a[1], b[1]),
        Math.max(a[0], b[0]),
        Math.max(a[1], b[1]),
        Math.max(60, len * 0.6)
      );
    }
    // whole room polygon
    if (poly && poly.length >= 3) {
      const xs = poly.map((p) => p[0]);
      const ys = poly.map((p) => p[1]);
      return fitBox(Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys), 90);
    }
    // no polygon — center the label anchor neighborhood
    if (room.anchorPx) {
      const [ax, ay] = room.anchorPx;
      return fitBox(ax - 240, ay - 240, ax + 240, ay + 240, 0);
    }
    return fitBox(0, 0, imgW, imgH, 0);
  }, [viewMode, selectedEdge, poly, room.anchorPx, imgW, imgH, fitBox]);

  // Refit on room / view / edge selection / explicit fit — but NOT on overlay
  // toggle, so switching proposal<->human preserves the current zoom/pan (§7.2).
  useEffect(() => {
    fitToTarget();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [room.taskId, viewMode, selectedEdge, fitToken]);

  // ---- wheel zoom at cursor (non-passive) ----
  const screenToImg = useCallback((clientX: number, clientY: number): Pt | null => {
    const svg = svgRef.current;
    if (!svg) return null;
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
    return [p.x, p.y];
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const img = screenToImg(e.clientX, e.clientY);
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      setZoom((z) => {
        if (img) pendingScroll.current = { ix: img[0], iy: img[1], cx: e.clientX, cy: e.clientY };
        return Math.min(4, Math.max(0.05, z * factor));
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [screenToImg]);

  useEffect(() => {
    const el = scrollRef.current;
    const ps = pendingScroll.current;
    if (!el || !ps) return;
    pendingScroll.current = null;
    const rect = el.getBoundingClientRect();
    el.scrollLeft = ps.ix * zoom - (ps.cx - rect.left);
    el.scrollTop = ps.iy * zoom - (ps.cy - rect.top);
  }, [zoom]);

  // ---- drag pan + pinch ----
  const onPointerDown = (e: React.PointerEvent) => {
    const el = scrollRef.current;
    if (!el) return;
    try {
      el.setPointerCapture(e.pointerId);
    } catch {
      /* no-op */
    }
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2) {
      const p = [...pointers.current.values()];
      pinchDist.current = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
      drag.current = null;
    } else {
      drag.current = { sx: e.clientX, sy: e.clientY, l: el.scrollLeft, t: el.scrollTop, moved: false };
    }
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size >= 2) {
      const p = [...pointers.current.values()];
      const d = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
      const mx = (p[0].x + p[1].x) / 2;
      const my = (p[0].y + p[1].y) / 2;
      if (pinchDist.current > 0) {
        const img = screenToImg(mx, my);
        setZoom((z) => {
          if (img) pendingScroll.current = { ix: img[0], iy: img[1], cx: mx, cy: my };
          return Math.min(4, Math.max(0.05, z * (d / pinchDist.current)));
        });
      }
      pinchDist.current = d;
      return;
    }
    const d = drag.current;
    const el = scrollRef.current;
    if (!d || !el) return;
    if (Math.abs(e.clientX - d.sx) > 3 || Math.abs(e.clientY - d.sy) > 3) d.moved = true;
    if (d.moved) {
      el.scrollLeft = d.l - (e.clientX - d.sx);
      el.scrollTop = d.t - (e.clientY - d.sy);
    }
  };
  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinchDist.current = 0;
    drag.current = null;
  };

  const color = COLOR[overlay];
  const sw = 2 / zoom;
  const vtxR = 4 / zoom;

  return (
    <div className="fa-canvas">
      <div className="fa-canvas-tools">
        <button className="btn" onClick={() => setZoom((z) => Math.min(4, z * 1.25))} aria-label="Zoom in">＋</button>
        <button className="btn" onClick={() => setZoom((z) => Math.max(0.05, z / 1.25))} aria-label="Zoom out">－</button>
        <button className="btn" onClick={() => { onSelectEdge(null); fitToTarget(); }} title="Fit this room">Fit room</button>
        <span className="chip fa-zoomchip">{Math.round(zoom * 100)}%</span>
      </div>
      <div
        ref={scrollRef}
        className="fa-canvas-viewport"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        style={{ touchAction: "none" }}
      >
        <div style={{ position: "relative", width: displayW, height: displayH }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={`${room.level} · sheet ${room.sheetNumber}`}
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
            style={{ position: "absolute", inset: 0 }}
          >
            {room.anchorPx && (
              <g pointerEvents="none" stroke={COLOR.anchor} strokeWidth={sw}>
                <circle cx={room.anchorPx[0]} cy={room.anchorPx[1]} r={vtxR * 1.6} fill="none" />
                <line x1={room.anchorPx[0] - vtxR * 2.4} y1={room.anchorPx[1]} x2={room.anchorPx[0] + vtxR * 2.4} y2={room.anchorPx[1]} />
                <line x1={room.anchorPx[0]} y1={room.anchorPx[1] - vtxR * 2.4} x2={room.anchorPx[0]} y2={room.anchorPx[1] + vtxR * 2.4} />
              </g>
            )}

            {poly && poly.length >= 3 && (
              <>
                <polygon
                  points={poly.map((p) => `${p[0]},${p[1]}`).join(" ")}
                  fill={color}
                  fillOpacity={0.14}
                  stroke={color}
                  strokeWidth={sw}
                  pointerEvents="none"
                />
                {/* one clickable hit-line per edge (fat transparent stroke) */}
                {poly.map((p, i) => {
                  const n = poly[(i + 1) % poly.length];
                  const isSel = selectedEdge === i;
                  return (
                    <g key={`e${i}`}>
                      {isSel && (
                        <line
                          x1={p[0]} y1={p[1]} x2={n[0]} y2={n[1]}
                          stroke={COLOR.edgeSel} strokeWidth={sw * 2.2} strokeLinecap="round" pointerEvents="none"
                        />
                      )}
                      <line
                        x1={p[0]} y1={p[1]} x2={n[0]} y2={n[1]}
                        stroke="transparent" strokeWidth={Math.max(sw * 4, 10 / zoom)}
                        style={{ cursor: "pointer" }}
                        onClick={() => onSelectEdge(isSel ? null : i)}
                      />
                    </g>
                  );
                })}
                {poly.map((p, i) => (
                  <circle key={`v${i}`} cx={p[0]} cy={p[1]} r={vtxR} fill="#fff" stroke={color} strokeWidth={sw} pointerEvents="none" />
                ))}
              </>
            )}
          </svg>
        </div>
      </div>
    </div>
  );
}
