"use client";
import { useCallback, useEffect, useState } from "react";

// Thumbnail strip of every page in a document, with a tap-to-open inline
// lightbox for the full-size render. Thumbs lazy-load (docs run 40+ pages);
// the full-size image is only requested when a thumb is opened.
export default function DocStrip({
  docId,
  pageCount,
  titles,
  name,
}: {
  docId: string;
  pageCount: number;
  titles: (string | null)[];
  name: string | null;
}) {
  const [open, setOpen] = useState<number | null>(null);

  const close = useCallback(() => setOpen(null), []);
  const step = useCallback(
    (d: 1 | -1) => setOpen((o) => (o == null ? o : Math.max(0, Math.min(pageCount - 1, o + d)))),
    [pageCount]
  );

  useEffect(() => {
    if (open == null) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") step(1);
      else if (e.key === "ArrowLeft") step(-1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close, step]);

  return (
    <div className="docstrip">
      <div className="docstrip-head">
        <span className="nm" title={name ?? undefined}>
          {name ?? `Document ${docId}`} <span className="pc">· {pageCount} pages</span>
        </span>
        <a href={`/api/pdf/${docId}`} target="_blank" rel="noreferrer" className="btn ghost">
          Open raw PDF ↗
        </a>
      </div>
      <div className="docstrip-scroll">
        {Array.from({ length: pageCount }, (_, i) => (
          <button key={i} className="docstrip-thumb" onClick={() => setOpen(i)} title={titles[i] ?? `Page ${i + 1}`}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/opspage/${docId}/${i}?w=280`} alt={`Page ${i + 1}`} loading="lazy" />
            <span className="cap">
              <b>p{i + 1}</b>
              {titles[i] ? ` ${titles[i]}` : ""}
            </span>
          </button>
        ))}
      </div>

      {open != null && (
        <div className="lightbox" onClick={close} role="dialog" aria-modal="true">
          <div className="lightbox-bar" onClick={(e) => e.stopPropagation()}>
            <span className="cap">
              {name ?? `Document ${docId}`} — page {open + 1} / {pageCount}
              {titles[open] ? ` · ${titles[open]}` : ""}
            </span>
            <div className="tools">
              <button onClick={() => step(-1)} disabled={open <= 0}>
                ←
              </button>
              <button onClick={() => step(1)} disabled={open >= pageCount - 1}>
                →
              </button>
              <button onClick={close}>✕</button>
            </div>
          </div>
          <div className="lightbox-stage" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/opspage/${docId}/${open}`} alt={`Page ${open + 1} full size`} />
          </div>
        </div>
      )}
    </div>
  );
}
