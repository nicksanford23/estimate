"use client";

import { useState } from "react";
import ZoomViewer from "@/components/ZoomViewer";

// An item is either a rendered plan page (docId + page → API) or a direct
// static image we generated (src). thumb/full resolve accordingly.
type Item = { page?: number; src?: string; label: string };

export default function GuideImages({
  docId,
  items,
}: {
  docId: number;
  items: Item[];
}) {
  const [open, setOpen] = useState<number | null>(null);
  const key = (it: Item, i: number) => it.src ?? (it.page != null ? `p${it.page}` : `i${i}`);
  const thumb = (it: Item) => it.src ?? `/api/thumb/${docId}/${it.page}`;
  const full = (it: Item) => it.src ?? `/api/pageimg/${docId}/${it.page}`;
  const cur = open !== null ? items[open] : null;
  return (
    <>
      <div className="guide-imgs">
        {items.map((it, i) => (
          <button key={key(it, i)} className="guide-img" onClick={() => setOpen(i)}>
            <img loading="lazy" src={thumb(it)} alt={it.label} />
            <span className="cap">{it.label} · tap to zoom</span>
          </button>
        ))}
      </div>
      {cur && (
        <ZoomViewer src={full(cur)} caption={cur.label} onClose={() => setOpen(null)} />
      )}
    </>
  );
}
