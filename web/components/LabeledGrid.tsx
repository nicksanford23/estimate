"use client";

import { useState } from "react";
import { CAT_LABEL } from "@/lib/labels";
import type { LabeledPage } from "@/lib/queries";
import ZoomViewer from "@/components/ZoomViewer";

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

  const nkeep = pages.filter((p) => p.keep).length;
  const shown = keepOnly ? pages.filter((p) => p.keep) : pages;
  const current = open !== null ? pages.find((p) => p.pi === open) : null;

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

      <p className="hint">Green = flooring page. Tap any page to open it full-size and zoom in.</p>

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
              onClick={() => setOpen(p.pi)}
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
        <ZoomViewer
          src={`/api/pageimg/${docId}/${current.pi}`}
          caption={`p${String(current.pi).padStart(2, "0")} · ${CAT_LABEL[current.cat] ?? current.cat}${
            current.title ? ` · ${current.title}` : ""
          }`}
          onClose={() => setOpen(null)}
        />
      )}
    </>
  );
}
