"use client";
import { useCallback, useEffect, useMemo, useState } from "react";

export type PagesTabDoc = {
  docId: string;
  name: string | null;
  pageCount: number;
  titles: (string | null)[];
  labels: (string | null)[]; // latest category per page index, null = unlabeled
  suggestions?: ({ label: string; evidence: string } | null)[]; // pre-filled proposals, index = page
};

// The 16-slug v2 taxonomy (.claude/skills/label-pages/SKILL.md is the
// source of truth — NOT the older list with separate elevation/section and
// no reflected_ceiling/life_safety).
const TAXONOMY = [
  "floor_plan",
  "finish_plan",
  "finish_schedule",
  "demo_plan",
  "reflected_ceiling",
  "furniture_plan",
  "site_plan",
  "elevation_section",
  "detail",
  "schedule_other",
  "structural",
  "mep",
  "life_safety",
  "cover_index",
  "specs_notes",
  "other",
] as const;

// Keyboard shortcuts for the most-common labels (shown in the modal legend).
const KEY_MAP: Record<string, (typeof TAXONOMY)[number]> = {
  "1": "floor_plan",
  "2": "finish_plan",
  "3": "finish_schedule",
  "4": "demo_plan",
  "5": "cover_index",
  "6": "specs_notes",
  "7": "site_plan",
  "8": "other",
};

const KEEP_CATEGORIES = new Set(["floor_plan", "finish_plan", "finish_schedule", "demo_plan"]);

// label_proposals_<permit>.json is written by an older/looser taxonomy
// (e.g. "elevation", "section", "interior_elevation", "roof_plan") — map
// those onto the current 16-slug taxonomy so suggestion buttons are valid.
const PROPOSAL_ALIASES: Record<string, (typeof TAXONOMY)[number]> = {
  elevation: "elevation_section",
  section: "elevation_section",
  interior_elevation: "elevation_section",
  roof_plan: "other",
};
function normalizeProposal(label: string): (typeof TAXONOMY)[number] | null {
  if ((TAXONOMY as readonly string[]).includes(label)) return label as (typeof TAXONOMY)[number];
  return PROPOSAL_ALIASES[label] ?? null;
}

function LabelChip({ category }: { category: string | null }) {
  if (!category) return <span className="label-chip unlabeled">unlabeled</span>;
  const keep = KEEP_CATEGORIES.has(category);
  return <span className={`label-chip ${keep ? "keep" : "nokeep"}`}>{category}</span>;
}

export default function PagesTab({ permit, docs }: { permit: string; docs: PagesTabDoc[] }) {
  // local mutable copy so labeling updates the grid optimistically
  const [labelState, setLabelState] = useState<(string | null)[][]>(() => docs.map((d) => [...d.labels]));
  const [openDocIdx, setOpenDocIdx] = useState<number | null>(null);
  const [openPage, setOpenPage] = useState<number | null>(null);
  const [posting, setPosting] = useState(false);
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set(docs.length ? [0] : []));

  const modalOpen = openDocIdx != null && openPage != null;
  const curDoc = openDocIdx != null ? docs[openDocIdx] : null;

  const close = useCallback(() => {
    setOpenDocIdx(null);
    setOpenPage(null);
  }, []);

  const step = useCallback(
    (d: 1 | -1) => {
      setOpenPage((p) => {
        if (p == null || curDoc == null) return p;
        const next = p + d;
        if (next < 0 || next >= curDoc.pageCount) return p;
        return next;
      });
    },
    [curDoc]
  );

  const submitLabel = useCallback(
    async (category: string) => {
      if (openDocIdx == null || openPage == null) return;
      const doc = docs[openDocIdx];
      setPosting(true);
      try {
        const r = await fetch("/api/ops/label", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ doc_id: doc.docId, page: openPage, category, permit }),
        });
        if (r.ok) {
          setLabelState((prev) => {
            const copy = prev.map((arr) => [...arr]);
            copy[openDocIdx][openPage] = category;
            return copy;
          });
        } else {
          const body = await r.json().catch(() => ({}));
          alert(`Label failed: ${body.error ?? r.status}`);
        }
      } finally {
        setPosting(false);
      }
    },
    [openDocIdx, openPage, docs, permit]
  );

  useEffect(() => {
    if (!modalOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") step(1);
      else if (e.key === "ArrowLeft") step(-1);
      else if (KEY_MAP[e.key]) submitLabel(KEY_MAP[e.key]);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalOpen, close, step, submitLabel]);

  const toggle = (i: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  const legend = useMemo(
    () =>
      Object.entries(KEY_MAP).map(([key, cat]) => (
        <span key={key} className="legend-item">
          <kbd>{key}</kbd> {cat}
        </span>
      )),
    []
  );

  if (docs.length === 0) {
    return <p className="hint">No downloaded/processed documents for this permit yet.</p>;
  }

  return (
    <div className="pages-tab">
      {docs.map((doc, di) => (
        <details key={doc.docId} open={expanded.has(di)} onToggle={(e) => {
          const isOpen = (e.target as HTMLDetailsElement).open;
          setExpanded((prev) => {
            const next = new Set(prev);
            if (isOpen) next.add(di);
            else next.delete(di);
            return next;
          });
        }}>
          <summary className="pages-doc-summary">
            <b>{doc.name ?? `Document ${doc.docId}`}</b>{" "}
            <span className="pc">· {doc.pageCount} pages · doc {doc.docId}</span>
          </summary>
          <div className="thumb-grid">
            {Array.from({ length: doc.pageCount }, (_, pi) => (
              <button
                key={pi}
                className="thumb-card"
                onClick={() => {
                  setOpenDocIdx(di);
                  setOpenPage(pi);
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/api/opspage/${doc.docId}/${pi}?w=220`} alt={`Page ${pi + 1}`} loading="lazy" />
                <span className="thumb-cap">
                  p{pi + 1}
                  {doc.titles[pi] ? ` · ${doc.titles[pi]}` : ""}
                </span>
                <LabelChip category={labelState[di][pi]} />
                {!labelState[di][pi] && doc.suggestions?.[pi] && (
                  <span className="suggest-chip">
                    suggested: {normalizeProposal(doc.suggestions[pi]!.label) ?? doc.suggestions[pi]!.label}
                  </span>
                )}
              </button>
            ))}
          </div>
        </details>
      ))}

      {modalOpen && curDoc && (
        <div className="lightbox" onClick={close} role="dialog" aria-modal="true">
          <div className="lightbox-bar" onClick={(e) => e.stopPropagation()}>
            <span className="cap">
              {curDoc.name ?? `Document ${curDoc.docId}`} — page {openPage! + 1} / {curDoc.pageCount}
              {curDoc.titles[openPage!] ? ` · ${curDoc.titles[openPage!]}` : ""}
            </span>
            <div className="tools">
              <button onClick={() => step(-1)} disabled={openPage! <= 0}>
                ←
              </button>
              <button onClick={() => step(1)} disabled={openPage! >= curDoc.pageCount - 1}>
                →
              </button>
              <button onClick={close}>✕</button>
            </div>
          </div>
          <div className="lightbox-stage" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/opspage/${curDoc.docId}/${openPage}`} alt={`Page ${openPage! + 1} full size`} />
          </div>
          <div className="label-picker" onClick={(e) => e.stopPropagation()}>
            <div className="label-picker-row">
              <span>Current:</span>
              <LabelChip category={labelState[openDocIdx!][openPage!]} />
              {posting && <span className="hint">saving…</span>}
            </div>
            {!labelState[openDocIdx!][openPage!] &&
              curDoc.suggestions?.[openPage!] &&
              (() => {
                const s = curDoc.suggestions![openPage!]!;
                const norm = normalizeProposal(s.label);
                return (
                  <div className="label-picker-row suggest-row">
                    <span>
                      Suggested: <b>{norm ?? s.label}</b> — {s.evidence}
                    </span>
                    {norm && (
                      <button className="btn primary" disabled={posting} onClick={() => submitLabel(norm)}>
                        Confirm ✓
                      </button>
                    )}
                  </div>
                );
              })()}
            <div className="label-picker-grid">
              {TAXONOMY.map((cat) => {
                const sugg = curDoc.suggestions?.[openPage!];
                const norm = sugg ? normalizeProposal(sugg.label) : null;
                const isSuggested = !labelState[openDocIdx!][openPage!] && norm === cat;
                return (
                  <button
                    key={cat}
                    className={`label-btn ${labelState[openDocIdx!][openPage!] === cat ? "active" : ""} ${
                      isSuggested ? "suggested" : ""
                    }`}
                    onClick={() => submitLabel(cat)}
                    disabled={posting}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>
            <div className="legend">
              {legend}
              <span className="legend-item">
                <kbd>←</kbd>/<kbd>→</kbd> prev/next
              </span>
              <span className="legend-item">
                <kbd>Esc</kbd> close
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
