"use client";
import { useState } from "react";

// Before/after pair: the ORIGINAL page image next to the pipeline's overlay
// render. Side-by-side on desktop; stacked (original first) on mobile — the
// DOM order gives both. If the original can't be produced (PDF missing from
// R2, render failed) we say so instead of showing a broken image.
export default function OrigOverlayPair({
  docId,
  page,
  overlaySrc,
  overlayFile,
}: {
  docId: string | null;
  page: string | null;
  overlaySrc: string;
  overlayFile: string;
}) {
  const [origFailed, setOrigFailed] = useState(false);
  const hasOrigTarget = docId != null && page != null && docId !== "" && page !== "";
  const origSrc = hasOrigTarget ? `/api/opspage/${docId}/${page}` : null;

  return (
    <div className="pair">
      <figure className="pair-cell">
        {origSrc && !origFailed ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={origSrc} alt={`Original — doc ${docId} page ${page}`} loading="lazy" onError={() => setOrigFailed(true)} />
        ) : (
          <div className="pair-missing">
            {hasOrigTarget ? "No original render available for this page." : "Source page unknown for this render."}
          </div>
        )}
        <figcaption>Original{hasOrigTarget ? ` · doc ${docId} p${page}` : ""}</figcaption>
      </figure>
      <figure className="pair-cell">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={overlaySrc} alt={overlayFile} loading="lazy" />
        <figcaption>What the system found · {overlayFile}</figcaption>
      </figure>
    </div>
  );
}
