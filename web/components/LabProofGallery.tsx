"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

export type LabProof = {
  src: string;
  label: string;
};

export default function LabProofGallery({
  primary,
  details = [],
  compact = false,
}: {
  primary: LabProof[];
  details?: LabProof[];
  compact?: boolean;
}) {
  const proofs = useMemo(() => [...primary, ...details], [primary, details]);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [zoom, setZoom] = useState<"fit" | 1 | 1.5 | 2>("fit");

  const close = useCallback(() => setOpenIndex(null), []);
  const step = useCallback(
    (delta: -1 | 1) => {
      setOpenIndex((current) => {
        if (current == null) return current;
        return Math.max(0, Math.min(proofs.length - 1, current + delta));
      });
      setZoom("fit");
    },
    [proofs.length],
  );

  useEffect(() => {
    if (openIndex == null) return;
    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") close();
      else if (event.key === "ArrowLeft") step(-1);
      else if (event.key === "ArrowRight") step(1);
    }
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = priorOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [openIndex, close, step]);

  const active = openIndex == null ? null : proofs[openIndex];

  return (
    <div className={`lab-proof-gallery${compact ? " compact" : ""}`}>
      <div className="lab-proof-primary">
        {primary.map((proof, index) => (
          <button
            key={proof.src}
            type="button"
            className="lab-proof-open"
            onClick={() => {
              setOpenIndex(index);
              setZoom("fit");
            }}
            aria-label={`Open full-screen proof: ${proof.label}`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={proof.src} alt={proof.label} loading="lazy" />
            <span className="lab-proof-hint">Click to inspect full screen</span>
          </button>
        ))}
      </div>

      {details.length > 0 && (
        <details className="lab-proof-details">
          <summary>Edge details ({details.length})</summary>
          <div className="lab-proof-detail-list">
            {details.map((proof, index) => (
              <button
                key={proof.src}
                type="button"
                onClick={() => {
                  setOpenIndex(primary.length + index);
                  setZoom("fit");
                }}
              >
                {proof.label}
              </button>
            ))}
          </div>
        </details>
      )}

      {active && openIndex != null && (
        <div className="lightbox lab-proof-lightbox" onClick={close} role="dialog" aria-modal="true" aria-label={active.label}>
          <div className="lightbox-bar" onClick={(event) => event.stopPropagation()}>
            <span className="cap">
              {active.label} · {openIndex + 1} of {proofs.length}
            </span>
            <div className="tools">
              <button type="button" onClick={() => step(-1)} disabled={openIndex === 0} aria-label="Previous proof">←</button>
              <button type="button" onClick={() => step(1)} disabled={openIndex === proofs.length - 1} aria-label="Next proof">→</button>
              <button type="button" className={zoom === "fit" ? "active" : ""} onClick={() => setZoom("fit")}>Fit</button>
              <button type="button" className={zoom === 1 ? "active" : ""} onClick={() => setZoom(1)}>100%</button>
              <button type="button" className={zoom === 1.5 ? "active" : ""} onClick={() => setZoom(1.5)}>150%</button>
              <button type="button" className={zoom === 2 ? "active" : ""} onClick={() => setZoom(2)}>200%</button>
              <a href={active.src} target="_blank" rel="noreferrer">Original ↗</a>
              <button type="button" onClick={close} aria-label="Close proof viewer">✕</button>
            </div>
          </div>
          <div className={`lightbox-stage lab-proof-stage ${zoom === "fit" ? "fit" : "zoomed"}`} onClick={(event) => event.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={active.src}
              alt={active.label}
              style={zoom === "fit" ? undefined : { width: `${zoom * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
