"use client";

import { useState } from "react";
import { TAXONOMY_V2 } from "@/lib/v2Taxonomy";
import type { V2PageRow } from "@/lib/v2Db";

// Thin Page Review card: PDF p.N, sheet title (grey, machine observation),
// category chip (dashed = machine-only, solid green = binding human decision
// exists — SCHEMA_V2.md §14 trust states), 16-slug taxonomy picker + Confirm.
export default function V2PageCard({ page }: { page: V2PageRow }) {
  const [selected, setSelected] = useState<string>(page.binding_category ?? page.claimed_category ?? "");
  const [binding, setBinding] = useState<string | null>(page.binding_category);
  const [decisionId, setDecisionId] = useState<number | null>(page.binding_decision_id);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function confirm() {
    if (!selected) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/v2/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_id: page.page_id, category: selected }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "decide failed");
      setBinding(selected);
      setDecisionId(data.decision_id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "error");
    } finally {
      setBusy(false);
    }
  }

  // opspage is keyed by the onestop doc id and renders on demand from R2, so
  // every backfilled doc gets a thumbnail (legacy /api/thumb knew one doc).
  const thumbSrc = `/api/opspage/${page.onestop_doc_id}/${page.pdf_page_index}?w=280`;
  const chipConfirmed = Boolean(binding);
  const chipLabel = binding ?? page.claimed_category ?? "unlabeled";

  return (
    <div style={{ display: "flex", gap: 12, padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
      {thumbSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={thumbSrc} alt={`p.${page.pdf_page_index}`} width={90} style={{ borderRadius: 4, border: "1px solid var(--line)", height: "fit-content" }} />
      ) : (
        <div style={{ width: 90, height: 60, background: "var(--surface-2)", borderRadius: 4 }} />
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>PDF p.{page.pdf_page_index}</span>
          <span
            className="chip"
            style={
              chipConfirmed
                ? { borderStyle: "solid", borderColor: "var(--good)", color: "var(--good)" }
                : { borderStyle: "dashed" }
            }
            title={decisionId ? `human_decision #${decisionId}` : page.claimed_source ?? undefined}
          >
            {chipLabel}
          </span>
        </div>
        {page.sheet_title && <div style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 2 }}>{page.sheet_title}</div>}
        <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {TAXONOMY_V2.map((cat) => (
            <button
              key={cat}
              type="button"
              className="btn"
              style={selected === cat ? { background: "var(--accent)", color: "#fff", borderColor: "var(--accent)" } : undefined}
              onClick={() => setSelected(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
        <div style={{ marginTop: 6 }}>
          <button type="button" className="btn primary" disabled={!selected || busy} onClick={confirm}>
            {busy ? "Confirming…" : "Confirm"}
          </button>
          {err && <span style={{ color: "var(--bad)", marginLeft: 8, fontSize: 12 }}>{err}</span>}
        </div>
      </div>
    </div>
  );
}
