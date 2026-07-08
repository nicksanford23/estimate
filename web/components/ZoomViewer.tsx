"use client";

import { useEffect, useRef } from "react";

/**
 * Fullscreen image viewer with pinch-to-zoom (two fingers), drag/one-finger
 * pan, mouse-wheel zoom, and +/− buttons. Zoom is width-based (the browser
 * re-samples from the full-res source) so it stays crisp when zoomed in.
 */
export default function ZoomViewer({
  src,
  caption,
  onClose,
}: {
  src: string;
  caption: string;
  onClose: () => void;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const zoom = useRef(1);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef(0);
  const pan = useRef<{ x: number; y: number; l: number; t: number } | null>(null);

  const apply = (nz: number, ax?: number, ay?: number) => {
    const st = stageRef.current;
    const img = imgRef.current;
    if (!st || !img) return;
    nz = Math.min(8, Math.max(1, nz));
    const rect = st.getBoundingClientRect();
    const px = (ax ?? rect.left + rect.width / 2) - rect.left;
    const py = (ay ?? rect.top + rect.height / 2) - rect.top;
    const fracX = (st.scrollLeft + px) / (st.scrollWidth || 1);
    const fracY = (st.scrollTop + py) / (st.scrollHeight || 1);
    img.style.width = `${nz * 100}%`;
    // reading scrollWidth after the style change forces a reflow (sync)
    st.scrollLeft = fracX * st.scrollWidth - px;
    st.scrollTop = fracY * st.scrollHeight - py;
    zoom.current = nz;
    img.style.cursor = nz > 1 ? "grab" : "zoom-in";
  };

  const reset = () => {
    const img = imgRef.current;
    const st = stageRef.current;
    if (img) img.style.width = "100%";
    if (st) {
      st.scrollLeft = 0;
      st.scrollTop = 0;
    }
    zoom.current = 1;
  };

  useEffect(() => {
    reset();
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [src]); // eslint-disable-line react-hooks/exhaustive-deps

  const onDown = (e: React.PointerEvent) => {
    try {
      stageRef.current?.setPointerCapture(e.pointerId);
    } catch {
      /* no-op */
    }
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 1) {
      const st = stageRef.current!;
      pan.current = { x: e.clientX, y: e.clientY, l: st.scrollLeft, t: st.scrollTop };
    } else if (pointers.current.size === 2) {
      pan.current = null;
      const p = [...pointers.current.values()];
      pinch.current = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
    }
  };
  const onMove = (e: React.PointerEvent) => {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size >= 2) {
      const p = [...pointers.current.values()];
      const d = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
      const mx = (p[0].x + p[1].x) / 2;
      const my = (p[0].y + p[1].y) / 2;
      if (pinch.current > 0) apply(zoom.current * (d / pinch.current), mx, my);
      pinch.current = d;
    } else if (pan.current) {
      const st = stageRef.current!;
      st.scrollLeft = pan.current.l - (e.clientX - pan.current.x);
      st.scrollTop = pan.current.t - (e.clientY - pan.current.y);
    }
  };
  const onUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinch.current = 0;
    if (pointers.current.size === 1) {
      const [pt] = [...pointers.current.values()];
      const st = stageRef.current!;
      pan.current = { x: pt.x, y: pt.y, l: st.scrollLeft, t: st.scrollTop };
    } else if (pointers.current.size === 0) {
      pan.current = null;
    }
  };
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    apply(zoom.current * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX, e.clientY);
  };

  return (
    <div className="wt-lb">
      <div className="wt-lb-bar">
        <span className="wt-lb-cap">{caption}</span>
        <div className="wt-lb-tools">
          <button onClick={() => apply(zoom.current / 1.4)}>−</button>
          <button onClick={reset}>fit</button>
          <button onClick={() => apply(zoom.current * 1.4)}>+</button>
          <button onClick={onClose}>✕ close</button>
        </div>
      </div>
      <div
        className="wt-lb-stage"
        ref={stageRef}
        onWheel={onWheel}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        style={{ touchAction: "none" }}
      >
        <img
          ref={imgRef}
          src={src}
          alt={caption}
          draggable={false}
          style={{ width: "100%", maxWidth: "none", display: "block", margin: "0 auto" }}
        />
      </div>
      <div className="wt-lb-hint">pinch or scroll or ± to zoom · drag to pan · ✕ or Esc to close</div>
    </div>
  );
}
