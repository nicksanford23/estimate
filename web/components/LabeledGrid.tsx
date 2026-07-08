"use client";

import { useEffect, useRef, useState } from "react";
import { CAT_LABEL } from "@/lib/labels";
import type { LabeledPage } from "@/lib/queries";

export default function LabeledGrid({
  docId,
  permit,
  name,
  pages,
}: {
  docId: string;
  permit: string | null;
  name: string | null;
  pages: LabeledPage[];
}) {
  const [keepOnly, setKeepOnly] = useState(false);
  const [open, setOpen] = useState<number | null>(null); // page_index being viewed
  const [zoom, setZoom] = useState(1);
  const stageRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; l: number; t: number } | null>(null);

  const nkeep = pages.filter((p) => p.keep).length;
  const shown = keepOnly ? pages.filter((p) => p.keep) : pages;
  const current = open !== null ? pages.find((p) => p.pi === open) : null;

  const openImg = (pi: number) => {
    setZoom(1);
    setOpen(pi);
    document.body.style.overflow = "hidden";
  };
  const close = () => {
    setOpen(null);
    document.body.style.overflow = "";
  };
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    setZoom((z) => Math.min(8, Math.max(1, z * (e.deltaY < 0 ? 1.15 : 1 / 1.15))));
  };
  const onDown = (e: React.PointerEvent) => {
    const s = stageRef.current;
    if (!s) return;
    drag.current = { x: e.clientX, y: e.clientY, l: s.scrollLeft, t: s.scrollTop };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    const s = stageRef.current;
    if (!s || !drag.current) return;
    s.scrollLeft = drag.current.l - (e.clientX - drag.current.x);
    s.scrollTop = drag.current.t - (e.clientY - drag.current.y);
  };
  const onUp = () => {
    drag.current = null;
  };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  return (
    <>
      <div className="detail-head">
        <div className="eyebrow">Labels · {permit ?? ""}</div>
        <h1 style={{ fontSize: 18 }}>{name || `Document ${docId}`}</h1>
        <div style={{ display: "flex", gap: 14, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
          <button
            type="button"
            className={`ftog ${keepOnly ? "on" : ""}`}
            onClick={() => setKeepOnly((v) => !v)}
          >
            <span className="bx">{keepOnly ? "☑" : "☐"}</span> flooring pages only
          </button>
          <span className="mono" style={{ color: "var(--muted)", fontSize: 13 }}>
            {pages.length} pages · {nkeep} flooring
          </span>
        </div>
      </div>

      <p className="hint">
        Green = flooring page. Tap any page to open it full-size and zoom in.
      </p>

      <div className="lab-grid">
        {shown.map((p) => {
          const flags = [
            ["scale", p.scale],
            ["table", p.table],
            ["codes", p.codes],
            ["rooms", p.rooms],
            ["dims", p.dims],
          ].filter(([, v]) => v) as [string, boolean][];
          return (
            <button
              type="button"
              key={p.pi}
              className={`lcell ${p.keep ? "keep" : "drop"}`}
              onClick={() => openImg(p.pi)}
            >
              <img loading="lazy" src={`/api/thumb/${docId}/${p.pi}`} alt={`page ${p.pi}`} />
              <div className="lcap">
                <div className="lrow">
                  <span className="pn">p{String(p.pi).padStart(2, "0")}</span>
                  <span className="cat">{CAT_LABEL[p.cat] ?? p.cat}</span>
                  <span className="cf">{p.conf.toFixed(2)}</span>
                </div>
                {p.title && <div className="ttl">{p.title}</div>}
                {flags.length > 0 && (
                  <div className="lflags">
                    {flags.map(([n]) => (
                      <span key={n} className="lfl">
                        {n}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>
      <div style={{ height: 50 }} />

      {current && (
        <div className="wt-lb">
          <div className="wt-lb-bar">
            <span className="wt-lb-cap">
              p{String(current.pi).padStart(2, "0")} · {CAT_LABEL[current.cat] ?? current.cat}
              {current.title ? ` · ${current.title}` : ""}
            </span>
            <div className="wt-lb-tools">
              <button onClick={() => setZoom((z) => Math.max(1, z / 1.4))}>−</button>
              <button onClick={() => setZoom(1)}>fit</button>
              <button onClick={() => setZoom((z) => Math.min(8, z * 1.4))}>+</button>
              <button onClick={close}>✕ close</button>
            </div>
          </div>
          <div
            className="wt-lb-stage"
            ref={stageRef}
            onWheel={onWheel}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            style={{ cursor: zoom > 1 ? "grab" : "zoom-in" }}
          >
            <img
              src={`/api/pageimg/${docId}/${current.pi}`}
              alt={`page ${current.pi}`}
              draggable={false}
              style={{ width: `${zoom * 100}%`, maxWidth: "none", display: "block", margin: "0 auto" }}
            />
          </div>
          <div className="wt-lb-hint">scroll or ± to zoom · drag to pan · ✕ or Esc to close</div>
        </div>
      )}
    </>
  );
}
