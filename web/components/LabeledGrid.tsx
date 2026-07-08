"use client";

import { useState } from "react";
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
  const nkeep = pages.filter((p) => p.keep).length;
  const shown = keepOnly ? pages.filter((p) => p.keep) : pages;

  return (
    <>
      <div className="detail-head">
        <div className="eyebrow">Labels · {permit ?? ""}</div>
        <h1 style={{ fontSize: 18 }}>{name || `Document ${docId}`}</h1>
        <div style={{ display: "flex", gap: 14, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
          <label className="toggle">
            <input
              type="checkbox"
              checked={keepOnly}
              onChange={(e) => setKeepOnly(e.target.checked)}
            />
            keep only
          </label>
          <span className="mono" style={{ color: "var(--muted)", fontSize: 13 }}>
            {pages.length} pages · {nkeep} keep
          </span>
        </div>
      </div>

      <p className="hint">
        Green = flooring keep. Click any page to open it in the full PDF.
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
            <a
              key={p.pi}
              className={`lcell ${p.keep ? "keep" : "drop"}`}
              href={`/api/pdf/${docId}#page=${p.pi + 1}`}
              target="_blank"
              rel="noopener"
            >
              <img
                loading="lazy"
                src={`/api/thumb/${docId}/${p.pi}`}
                alt={`page ${p.pi}`}
              />
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
            </a>
          );
        })}
      </div>
      <div style={{ height: 50 }} />
    </>
  );
}
