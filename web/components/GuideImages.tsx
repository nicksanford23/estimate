"use client";

import { useState } from "react";
import ZoomViewer from "@/components/ZoomViewer";

export default function GuideImages({
  docId,
  items,
}: {
  docId: number;
  items: { page: number; label: string }[];
}) {
  const [open, setOpen] = useState<number | null>(null);
  const cur = open !== null ? items.find((i) => i.page === open) : null;
  return (
    <>
      <div className="guide-imgs">
        {items.map((it) => (
          <button key={it.page} className="guide-img" onClick={() => setOpen(it.page)}>
            <img loading="lazy" src={`/api/thumb/${docId}/${it.page}`} alt={it.label} />
            <span className="cap">{it.label} · tap to zoom</span>
          </button>
        ))}
      </div>
      {cur && (
        <ZoomViewer
          src={`/api/pageimg/${docId}/${cur.page}`}
          caption={cur.label}
          onClose={() => setOpen(null)}
        />
      )}
    </>
  );
}
