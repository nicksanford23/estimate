"use client";

import { useEffect, useMemo, useState } from "react";
import V2Tabs from "@/components/V2Tabs";
import type { RoomsFinishesData } from "@/lib/v2Db";

// Rooms & Finishes — matches design_specs/rooms_finishes_APPROVED.png:
// left = source schedule page + crop-zoom strip of the selected row; right
// = extracted rows table (dashed = machine, solid green check = confirmed)
// with totals bar (extracted vs printed, cross-verified chip) and bulk
// "Accept N clean rows". Deviation from the mockup, noted here: the
// truth_area backfill JSON has no per-cell bbox, so the crop strip
// approximates the row's vertical position as (row_index / total rows) of
// the page height rather than a pixel-exact crop — a heuristic, not a real
// coordinate lookup.

type Props = { data: NonNullable<RoomsFinishesData> };

function fieldStr(raw: Record<string, unknown>, key: string): string {
  const v = raw[key];
  return v == null ? "" : String(v);
}

export default function RoomsFinishesBoard({ data }: Props) {
  const { permit, building, rows, printed_total_sf, extracted_total_sf, legacy_doc_id, pdf_page_index, sheet } = data;
  const [rowState, setRowState] = useState(() => new Map(rows.map((r) => [r.schedule_row_id, r.confirmed])));
  const [selectedId, setSelectedId] = useState<number | null>(rows[0]?.schedule_row_id ?? null);
  const [busy, setBusy] = useState<number | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const selected = rows.find((r) => r.schedule_row_id === selectedId) ?? null;
  const selectedIdx = rows.findIndex((r) => r.schedule_row_id === selectedId);

  const confirmedCount = useMemo(() => [...rowState.values()].filter(Boolean).length, [rowState]);
  const cleanRows = rows.filter((r) => !rowState.get(r.schedule_row_id));

  const pageSrc = legacy_doc_id ? `/api/opspage/${legacy_doc_id}/${pdf_page_index}?w=1100` : null;

  async function confirmRow(rowId: number) {
    const row = rows.find((r) => r.schedule_row_id === rowId);
    if (!row) return;
    setBusy(rowId);
    setErr(null);
    try {
      const res = await fetch("/api/v2/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_type: "schedule_row",
          target_id: rowId,
          claim: "schedule_row_confirm",
          value_json: { schedule_row_id: rowId, ...row.raw },
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "confirm failed");
      setRowState((prev) => new Map(prev).set(rowId, true));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "error");
    } finally {
      setBusy(null);
    }
  }

  async function acceptClean() {
    setBulkBusy(true);
    setErr(null);
    for (const r of cleanRows) {
      // eslint-disable-next-line no-await-in-loop
      await confirmRow(r.schedule_row_id);
    }
    setBulkBusy(false);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowDown") { e.preventDefault(); const n = rows[selectedIdx + 1]; if (n) setSelectedId(n.schedule_row_id); }
      else if (e.key === "ArrowUp") { e.preventDefault(); const p = rows[selectedIdx - 1]; if (p) setSelectedId(p.schedule_row_id); }
      else if (e.key === "Enter") { e.preventDefault(); if (selectedId) confirmRow(selectedId); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIdx, selectedId, rows]);

  const cross = printed_total_sf != null;
  const totalsMatch = cross && Math.abs((printed_total_sf as number) - extracted_total_sf) < 1;

  // heuristic crop position: (row_index / n) of page height, object-position %
  const cropPct = rows.length ? Math.round((100 * (selected?.row_index ?? 0)) / rows.length) : 0;

  return (
    <div className="v2board">
      <div className="v2board-main">
        <div className="page-head" style={{ marginBottom: 8 }}>
          <a href={`/v2/b/${permit}`} style={{ fontSize: 13 }}>&larr; {building?.building_name ?? permit}</a>
        </div>
        <div className="page-head">
          <h1 style={{ marginBottom: 2 }}>{building?.building_name ?? permit}</h1>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--muted)" }}>{permit}</span>
        </div>
        <V2Tabs permit={permit} active="rooms" />

        {!pageSrc ? (
          <p style={{ color: "var(--muted)", marginTop: 24 }}>No schedule page backfilled for this permit yet.</p>
        ) : (
          <div className="rf-left">
            <div className="rf-eyebrow">{sheet ?? "Room Finish Schedule"}</div>
            <div className="rf-cropstrip">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={pageSrc}
                alt="crop zoom of selected row"
                style={{ objectPosition: `50% ${cropPct}%`, transform: "scale(2.4)" }}
              />
            </div>
            <div className="rf-pageimg">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={pageSrc} alt="source schedule page" />
            </div>
          </div>
        )}
      </div>

      <aside className="v2panel rf-panel">
        <div className="v2panel-body">
          <div className="eyebrow">Extracted rooms — {rows.length} rows &middot; {confirmedCount} confirmed</div>
          <p style={{ fontSize: 12.5, color: "var(--muted)", margin: "4px 0 10px" }}>
            machine read {rows.length} rows from this table — confirm each or Accept all clean rows ({cleanRows.length})
          </p>
          <button type="button" className="btn primary" disabled={bulkBusy || cleanRows.length === 0} onClick={acceptClean} style={{ width: "100%", marginBottom: 12 }}>
            {bulkBusy ? "Accepting…" : `Accept ${cleanRows.length} clean rows`}
          </button>

          <div className="rf-table">
            <div className="rf-row rf-row-head">
              <span>Room#</span><span>Name</span><span>Floor</span><span>Base</span><span>Area SF</span><span>Notes</span><span>status</span>
            </div>
            {rows.map((r) => {
              const confirmed = rowState.get(r.schedule_row_id);
              const isSelected = r.schedule_row_id === selectedId;
              return (
                <button
                  key={r.schedule_row_id}
                  type="button"
                  className={`rf-row rf-row-body${isSelected ? " rf-row-selected" : ""}${confirmed ? " rf-row-confirmed" : " rf-row-machine"}`}
                  onClick={() => setSelectedId(r.schedule_row_id)}
                >
                  <span>{fieldStr(r.raw, "room") || fieldStr(r.raw, "room_number")}</span>
                  <span>{fieldStr(r.raw, "name")}</span>
                  <span>{fieldStr(r.raw, "floor_code") || fieldStr(r.raw, "floor_material")}</span>
                  <span>{fieldStr(r.raw, "base")}</span>
                  <span>{fieldStr(r.raw, "area_sf")}</span>
                  <span className="rf-notes">{fieldStr(r.raw, "notes") || fieldStr(r.raw, "comments")}</span>
                  <span>{confirmed ? <span style={{ color: "var(--good)" }}>&#10003; confirmed</span> : <span style={{ color: "var(--muted)" }}>machine</span>}</span>
                </button>
              );
            })}
          </div>

          <button
            type="button"
            className="btn primary"
            style={{ width: "100%", marginTop: 12 }}
            disabled={!selected || busy === selectedId || !!rowState.get(selectedId ?? -1)}
            onClick={() => selectedId && confirmRow(selectedId)}
          >
            {busy === selectedId ? "Confirming…" : "Confirm row (Enter)"}
          </button>
          {err && <div style={{ color: "var(--bad)", fontSize: 12, marginTop: 6 }}>{err}</div>}

          <div className="rf-totals">
            <span>Extracted total: <b>{extracted_total_sf} SF</b></span>
            {cross && (
              <span title="printed total on sheet, compared against summed extracted rows (v2.extraction manifest)">
                &middot; Printed total on sheet: <b>{printed_total_sf} SF</b> {totalsMatch ? <span className="chip" style={{ borderStyle: "solid", borderColor: "var(--muted)" }}>&#10003; cross-verified</span> : <span className="chip" style={{ borderStyle: "solid", borderColor: "var(--warn)" }}>Δ mismatch</span>}
              </span>
            )}
          </div>
          <div className="v2micro">confirmed rows become the room roster + answer key &middot; linked to spaces (pilot: link deferred)</div>
        </div>
      </aside>
    </div>
  );
}
