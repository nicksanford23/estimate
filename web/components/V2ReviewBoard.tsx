"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import { TAXONOMY_V2 } from "@/lib/v2Taxonomy";
import type { V2PageRow } from "@/lib/v2Db";
import V2Tabs from "@/components/V2Tabs";

// Page Review board — matches design_specs/page_review_APPROVED.png:
// collapsible per-doc sections of page-card grids + a fixed right side
// panel for the selected page (bottom sheet on mobile). Chip law and trust
// states per SCHEMA_V2.md §14: dashed border = machine-claimed only,
// solid green = human-confirmed (binding decision exists); status badge
// lives in the card corner, never inline with the label.

const KEEP_POLICY = new Set(["floor_plan", "finish_plan", "finish_schedule", "demo_plan"]);

// 8 flag toggles. Stored via claim='page_flags', value_json={flags:[...]}
// on the same append-only /api/v2/decide route used for page_category.
// Canonical 8 flags per SCHEMA_V2 §4 — do not invent alternates.
const FLAGS = [
  { key: "contains_floor_plan", label: "contains floor plan" },
  { key: "contains_finish_schedule", label: "contains finish schedule" },
  { key: "contains_legend", label: "contains legend" },
  { key: "contains_area_table", label: "contains area table" },
  { key: "multiple_viewports", label: "multiple viewports" },
  { key: "enlarged_plan", label: "enlarged plan" },
  { key: "flooring_scope", label: "flooring scope" },
  { key: "geometry_candidate", label: "geometry candidate" },
] as const;

type DocGroup = {
  document_id: number;
  onestop_doc_id: string;
  filename: string | null;
  filed_date: string | null;
  pages: V2PageRow[];
};

type PageState = {
  binding: string | null;
  decisionId: number | null;
  flags: string[];
};

function fmtDate(d: string | null) {
  if (!d) return null;
  try {
    return new Date(d).toLocaleDateString("en-US", { month: "2-digit", day: "2-digit", year: "numeric" });
  } catch {
    return d;
  }
}

function caption(page: V2PageRow, idx: number) {
  const title = page.sheet_title?.trim();
  return `${idx + 1}. ${title || `PDF p.${page.pdf_page_index}`}`;
}

export default function V2ReviewBoard({ permit, building, docs }: { permit: string; building: { building_name: string } | null; docs: DocGroup[] }) {
  const flat = useMemo(() => docs.flatMap((d) => d.pages), [docs]);
  const [state, setState] = useState<Map<number, PageState>>(
    () => new Map(flat.map((p) => [p.page_id, { binding: p.binding_category, decisionId: p.binding_decision_id, flags: p.flags }]))
  );
  const [selectedId, setSelectedId] = useState<number | null>(flat[0]?.page_id ?? null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const selectedPage = flat.find((p) => p.page_id === selectedId) ?? null;
  const selectedState = selectedId ? state.get(selectedId) : undefined;
  const [draftCategory, setDraftCategory] = useState<string>("");

  useEffect(() => {
    setDraftCategory(selectedState?.binding ?? selectedPage?.claimed_category ?? "");
    setErr(null);
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  const confirmedCount = Array.from(state.values()).filter((s) => s.binding).length;
  const totalCount = flat.length;

  async function postDecide(page_id: number, body: Record<string, unknown>) {
    const res = await fetch("/api/v2/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page_id, ...body }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error ?? "decide failed");
    return data;
  }

  async function confirmCategory() {
    if (!selectedPage || !draftCategory) return;
    setBusy(true);
    setErr(null);
    try {
      const data = await postDecide(selectedPage.page_id, { category: draftCategory });
      setState((prev) => {
        const next = new Map(prev);
        const cur = next.get(selectedPage.page_id)!;
        next.set(selectedPage.page_id, { ...cur, binding: draftCategory, decisionId: data.decision_id });
        return next;
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggleFlag(flagKey: string) {
    if (!selectedPage || !selectedState) return;
    const current = selectedState.flags;
    const next = current.includes(flagKey) ? current.filter((f) => f !== flagKey) : [...current, flagKey];
    // optimistic
    setState((prev) => {
      const m = new Map(prev);
      m.set(selectedPage.page_id, { ...m.get(selectedPage.page_id)!, flags: next });
      return m;
    });
    try {
      await postDecide(selectedPage.page_id, { claim: "page_flags", value_json: { flags: next } });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "flag save failed");
    }
  }

  const goNextFlagged = useCallback(() => {
    const idx = flat.findIndex((p) => p.page_id === selectedId);
    for (let i = idx + 1; i < flat.length; i++) {
      if (!state.get(flat[i].page_id)?.binding) {
        setSelectedId(flat[i].page_id);
        return;
      }
    }
  }, [flat, selectedId, state]);

  const moveSelection = useCallback(
    (delta: number) => {
      const idx = flat.findIndex((p) => p.page_id === selectedId);
      const next = flat[idx + delta];
      if (next) setSelectedId(next.page_id);
    },
    [flat, selectedId]
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); moveSelection(1); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); moveSelection(-1); }
      else if (e.key === "Enter") { e.preventDefault(); confirmCategory(); }
      else if (e.key === "f" || e.key === "F") { e.preventDefault(); goNextFlagged(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }); // re-bind every render so closures see latest draftCategory/selection

  return (
    <div className="v2board">
      <div className="v2board-main">
        <div className="page-head" style={{ marginBottom: 8 }}>
          <Link href="/v2" style={{ fontSize: 13 }}>&larr; Pilot Buildings</Link>
        </div>
        <div className="page-head">
          <h1 style={{ marginBottom: 2 }}>{building?.building_name ?? permit}</h1>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--muted)" }}>{permit}</span>
          </div>
        </div>
        <V2Tabs permit={permit} active="pages" />

        {docs.map((doc) => {
          const confirmed = doc.pages.filter((p) => state.get(p.page_id)?.binding).length;
          return (
            <details key={doc.document_id} className="v2doc" open>
              <summary className="v2doc-summary">
                <span>Arch Set {fmtDate(doc.filed_date) ? `(${fmtDate(doc.filed_date)})` : ""} — {doc.pages.length} pages · doc {doc.onestop_doc_id}</span>
                <span style={{ color: "var(--muted)", fontSize: 12, fontFamily: "var(--font-mono)" }}>{confirmed}/{doc.pages.length} confirmed</span>
              </summary>
              <div className="v2grid">
                {doc.pages.map((page, i) => {
                  const s = state.get(page.page_id)!;
                  const isSelected = page.page_id === selectedId;
                  const thumbSrc = `/api/opspage/${page.onestop_doc_id}/${page.pdf_page_index}?w=560`;
                  const statusLabel = s.binding ? "confirmed" : page.claimed_category ? "suggested" : "unlabeled";
                  const shownFlags = s.flags.slice(0, 2);
                  const overflow = s.flags.length - shownFlags.length;
                  return (
                    <button
                      key={page.page_id}
                      type="button"
                      className={`v2card${isSelected ? " v2card-selected" : ""}`}
                      onClick={() => setSelectedId(page.page_id)}
                    >
                      <div className="v2card-thumbwrap">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={thumbSrc} alt={caption(page, i)} loading="lazy" className="v2card-thumb" />
                        <span className={`v2card-status v2card-status-${statusLabel}`}>{statusLabel}</span>
                      </div>
                      <div className="v2card-cap">{caption(page, i)}</div>
                      <div className="v2card-chips">
                        <span className="chip" style={s.binding ? { borderStyle: "solid", borderColor: "var(--good)", color: "var(--good)" } : { borderStyle: "dashed" }}>
                          {s.binding ?? page.claimed_category ?? "unlabeled"}
                        </span>
                        {shownFlags.map((f) => (
                          <span key={f} className="chip">{FLAGS.find((x) => x.key === f)?.label ?? f}</span>
                        ))}
                        {overflow > 0 && <span className="chip">+{overflow}</span>}
                      </div>
                    </button>
                  );
                })}
              </div>
            </details>
          );
        })}
        {docs.length === 0 && <p style={{ color: "var(--muted)" }}>No documents backfilled for this permit.</p>}

        <div className="v2progress">
          <span>{confirmedCount} of {totalCount} pages confirmed</span>
          <div className="v2progress-bar"><div className="v2progress-fill" style={{ width: totalCount ? `${(100 * confirmedCount) / totalCount}%` : "0%" }} /></div>
        </div>
      </div>

      <aside className="v2panel">
        {selectedPage ? (
          <>
            <div className="v2panel-img">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/opspage/${selectedPage.onestop_doc_id}/${selectedPage.pdf_page_index}?w=900`} alt="selected page" />
            </div>
            <div className="v2panel-body">
              <div className="eyebrow" style={{ marginBottom: 6 }}>Category (choose one)</div>
              <div className="v2panel-catgrid">
                {TAXONOMY_V2.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    className="btn"
                    style={draftCategory === cat ? { background: "var(--accent)", color: "#fff", borderColor: "var(--accent)" } : undefined}
                    onClick={() => setDraftCategory(cat)}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <div className="eyebrow" style={{ margin: "14px 0 6px" }}>Flags (select all that apply)</div>
              <div className="v2panel-flags">
                {FLAGS.map((f) => {
                  const on = selectedState?.flags.includes(f.key);
                  return (
                    <label key={f.key} className="v2flag">
                      <span className={`v2toggle${on ? " v2toggle-on" : ""}`} onClick={() => toggleFlag(f.key)} />
                      <span>{f.label}</span>
                    </label>
                  );
                })}
              </div>

              <div className="v2keepline">
                <span aria-hidden>&#128274;</span>
                {KEEP_POLICY.has(draftCategory)
                  ? `KEEP — used for takeoff (${draftCategory})`
                  : "not in keep policy (site plan, detail, etc. are never used for takeoff)"}
              </div>

              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button type="button" className="btn primary" disabled={!draftCategory || busy} onClick={confirmCategory}>
                  {busy ? "Confirming…" : "Confirm (Enter)"}
                </button>
                <button type="button" className="btn" onClick={goNextFlagged}>Next flagged &rarr;</button>
              </div>
              {err && <div style={{ color: "var(--bad)", fontSize: 12, marginTop: 6 }}>{err}</div>}
              <div className="v2micro">your decision outranks machine suggestions</div>
            </div>
          </>
        ) : (
          <div className="v2panel-body"><p style={{ color: "var(--muted)" }}>Select a page.</p></div>
        )}
      </aside>
    </div>
  );
}
