"use client";

import { useEffect, useRef, useState } from "react";
import type { DemoRoom, RoomStatus } from "@/lib/demoTypes";

type Props = {
  image: string;
  imageWidth: number;
  imageHeight: number;
  rooms: DemoRoom[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** bump this number to ask the canvas to pan/zoom onto centerRoomId */
  centerToken: number;
  centerRoomId: string | null;
};

const MIN_ZOOM_FACTOR = 0.4; // relative to fit-to-viewport width
const MAX_ZOOM_FACTOR = 8;

function bbox(polygon: [number, number][]) {
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  for (const [x, y] of polygon) {
    if (x < minx) minx = x;
    if (x > maxx) maxx = x;
    if (y < miny) miny = y;
    if (y > maxy) maxy = y;
  }
  return { minx, miny, maxx, maxy, w: maxx - minx, h: maxy - miny };
}

export default function PlanCanvas({
  image,
  imageWidth,
  imageHeight,
  rooms,
  selectedId,
  onSelect,
  centerToken,
  centerRoomId,
}: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const fitWidthRef = useRef(imageWidth);
  const [widthPx, setWidthPx] = useState<number | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinchDist = useRef(0);
  const pan = useRef<{ x: number; y: number; l: number; t: number } | null>(null);

  const computeFit = () => {
    const vp = viewportRef.current;
    if (!vp) return;
    const vw = vp.clientWidth || 1;
    const vh = vp.clientHeight || 1;
    const fitW = Math.min(vw / imageWidth, vh / imageHeight) * imageWidth;
    fitWidthRef.current = fitW;
    setWidthPx(fitW);
  };

  useEffect(() => {
    computeFit();
    const onResize = () => computeFit();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageWidth, imageHeight]);

  const applyZoom = (rawWidthPx: number, anchorX?: number, anchorY?: number) => {
    const vp = viewportRef.current;
    if (!vp || widthPx == null) return;
    const min = fitWidthRef.current * MIN_ZOOM_FACTOR;
    const max = imageWidth * MAX_ZOOM_FACTOR;
    const newWidth = Math.min(max, Math.max(min, rawWidthPx));
    const rect = vp.getBoundingClientRect();
    const px = (anchorX ?? rect.left + rect.width / 2) - rect.left;
    const py = (anchorY ?? rect.top + rect.height / 2) - rect.top;
    const fracX = (vp.scrollLeft + px) / (vp.scrollWidth || 1);
    const fracY = (vp.scrollTop + py) / (vp.scrollHeight || 1);
    setWidthPx(newWidth);
    requestAnimationFrame(() => {
      vp.scrollLeft = fracX * vp.scrollWidth - px;
      vp.scrollTop = fracY * vp.scrollHeight - py;
    });
  };

  const resetView = () => computeFit();

  // ---- centering on a room (from table row click / Check Next) ----
  useEffect(() => {
    if (centerToken === 0) return;
    const vp = viewportRef.current;
    const room = rooms.find((r) => r.id === centerRoomId);
    if (!vp || !room || !room.polygon || room.polygon.length < 3) return;
    const b = bbox(room.polygon);
    const vw = vp.clientWidth || 1;
    const vh = vp.clientHeight || 1;
    const desiredScale = Math.min(vw / (b.w * 2.2), vh / (b.h * 2.2));
    const targetWidthPx = Math.min(
      imageWidth * MAX_ZOOM_FACTOR,
      Math.max(fitWidthRef.current, desiredScale * imageWidth)
    );
    setWidthPx(targetWidthPx);
    const scale = targetWidthPx / imageWidth;
    const cx = (b.minx + b.maxx) / 2;
    const cy = (b.miny + b.maxy) / 2;
    requestAnimationFrame(() => {
      vp.scrollLeft = cx * scale - vw / 2;
      vp.scrollTop = cy * scale - vh / 2;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [centerToken]);

  // ---- pointer handlers: drag pan (from background) + pinch zoom ----
  const isPolygonTarget = (t: EventTarget | null) =>
    t instanceof Element && !!t.closest("polygon");

  const onPointerDown = (e: React.PointerEvent) => {
    const vp = viewportRef.current;
    if (!vp) return;
    try {
      vp.setPointerCapture(e.pointerId);
    } catch {
      /* no-op */
    }
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 1 && !isPolygonTarget(e.target)) {
      pan.current = { x: e.clientX, y: e.clientY, l: vp.scrollLeft, t: vp.scrollTop };
    } else if (pointers.current.size === 2) {
      pan.current = null;
      const p = [...pointers.current.values()];
      pinchDist.current = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
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
      if (pinchDist.current > 0 && widthPx != null) {
        applyZoom(widthPx * (d / pinchDist.current), mx, my);
      }
      pinchDist.current = d;
    } else if (pan.current) {
      const vp = viewportRef.current!;
      vp.scrollLeft = pan.current.l - (e.clientX - pan.current.x);
      vp.scrollTop = pan.current.t - (e.clientY - pan.current.y);
    }
  };
  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinchDist.current = 0;
    if (pointers.current.size === 1) {
      const [pt] = [...pointers.current.values()];
      const vp = viewportRef.current!;
      pan.current = { x: pt.x, y: pt.y, l: vp.scrollLeft, t: vp.scrollTop };
    } else if (pointers.current.size === 0) {
      pan.current = null;
    }
  };
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (widthPx == null) return;
    applyZoom(widthPx * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX, e.clientY);
  };

  const heightPx = widthPx != null ? widthPx * (imageHeight / imageWidth) : undefined;

  return (
    <div className="rv-canvas-shell">
      <div
        className="rv-canvas-viewport"
        ref={viewportRef}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        style={{ touchAction: "none" }}
      >
        <div
          className="rv-canvas-stage"
          style={{ width: widthPx ?? "100%", height: heightPx }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={image}
            alt="Floor plan"
            draggable={false}
            onLoad={computeFit}
            style={{ width: "100%", height: "100%", display: "block" }}
          />
          <svg
            viewBox={`0 0 ${imageWidth} ${imageHeight}`}
            preserveAspectRatio="none"
            className="rv-canvas-svg"
          >
            {/* paint unlabeled shapes first so real rooms always sit on top for hover/click */}
            {[...rooms].sort((a, b) => Number(b.unlabeled ?? false) - Number(a.unlabeled ?? false)).map((r) => {
              if (!r.polygon || r.polygon.length < 3) return null;
              const pts = r.polygon.map((p) => p.join(",")).join(" ");
              const cls = [
                "rv-poly",
                r.unlabeled ? "rv-poly-unlabeled" : `rv-poly-${r.status}`,
                r.id === selectedId ? "rv-poly-selected" : "",
                r.id === hoveredId ? "rv-poly-hovered" : "",
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <polygon
                  key={r.id}
                  points={pts}
                  className={cls}
                  onClick={() => onSelect(r.id)}
                  onMouseEnter={() => setHoveredId(r.id)}
                  onMouseLeave={() => setHoveredId((h) => (h === r.id ? null : h))}
                />
              );
            })}
          </svg>
        </div>
      </div>
      <div className="rv-canvas-tools">
        <button onClick={() => widthPx != null && applyZoom(widthPx / 1.4)} aria-label="Zoom out">
          −
        </button>
        <button onClick={resetView} aria-label="Fit to view">
          fit
        </button>
        <button onClick={() => widthPx != null && applyZoom(widthPx * 1.4)} aria-label="Zoom in">
          +
        </button>
      </div>
    </div>
  );
}

export type { RoomStatus };
