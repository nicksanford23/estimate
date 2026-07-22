"use client";
// TEMP ML workbench — the review queue (the star of the project page). Renders
// each measured surface awaiting an S8 human decision with proof image(s) and
// the four decision buttons, POSTing to /api/lab/decide (append-only). Local
// state reflects the just-saved decision; the durable truth is the JSONL.
//
// FOUNDER CAVEAT: functional slice, pending founder visual sign-off.
import { useState } from "react";
import LabProofGallery from "@/components/LabProofGallery";

export interface QueueItemView {
  id: string;
  identities: string[];
  identityLabel: string | null;
  verdict: string;
  worstDeviationIn: number | null;
  reason: string | null;
  proofImages: string[];
  edgeZooms: string[];
  referenceConfirmed: boolean | null;
  decision: { decision: string; reviewer?: string } | null;
}

const ACTIONS: { key: string; decision: string; reference_confirmed?: boolean; label: string }[] = [
  { key: "accept", decision: "accept", reference_confirmed: true, label: "Confirm reference + accept" },
  { key: "reject", decision: "reject_reference", reference_confirmed: false, label: "Reject reference" },
  { key: "judge", decision: "needs_judgment", label: "Needs my judgment" },
  { key: "skip", decision: "skip", label: "Skip w/ note" },
];

function fileUrl(permit: string, name: string): string {
  return `/api/lab/file?permit=${encodeURIComponent(permit)}&kind=proof&name=${encodeURIComponent(name)}`;
}

function proofLabel(name: string): string {
  if (name.startsWith("review_")) return "Whole-room review";
  const part = name.match(/_(e\d+|room)\.png$/)?.[1];
  return part === "room" ? "Room overview" : part ? `Edge ${part.slice(1)}` : name;
}

export default function LabReviewQueue({ permit, items }: { permit: string; items: QueueItemView[] }) {
  const [state, setState] = useState<Record<string, { decision: string; busy?: boolean; error?: string }>>(() => {
    const init: Record<string, { decision: string }> = {};
    for (const it of items) if (it.decision) init[it.id] = { decision: it.decision.decision };
    return init;
  });

  async function decide(it: QueueItemView, action: (typeof ACTIONS)[number]) {
    let notes: string | null = null;
    if (action.key === "skip" || action.key === "judge") {
      notes = window.prompt(`Note for "${action.label}" on ${it.id}:`, "") || null;
    }
    setState((s) => ({ ...s, [it.id]: { decision: s[it.id]?.decision ?? "", busy: true } }));
    try {
      const res = await fetch("/api/lab/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          permit,
          task_id: it.id,
          identities: it.identities,
          decision: action.decision,
          reference_confirmed: action.reference_confirmed,
          notes,
        }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j?.error ?? `HTTP ${res.status}`);
      setState((s) => ({ ...s, [it.id]: { decision: action.decision } }));
    } catch (e) {
      setState((s) => ({ ...s, [it.id]: { decision: s[it.id]?.decision ?? "", error: String(e) } }));
    }
  }

  if (items.length === 0) return <p style={{ opacity: 0.7 }}>Queue file present but empty — no surfaces awaiting a decision.</p>;

  return (
    <div className="lab-review-list">
      {items.map((it, index) => {
        const st = state[it.id];
        return (
          <article key={it.id} id={`room-${it.identities[0] ?? it.id}`} className="lab-review-card">
            <header className="lab-review-card-head">
              <div>
                <span className="eyebrow">Review {index + 1} of {items.length}</span>
                <h3>
                  Room {it.identities.join(" · ") || it.id}
                  {it.identityLabel && <span>{it.identityLabel}</span>}
                </h3>
              </div>
              <div className="lab-review-chips">
                <span className="chip code">{it.verdict.replaceAll("_", " ")}</span>
                {it.worstDeviationIn != null && <span className="chip">worst edge {it.worstDeviationIn.toFixed(1)} in</span>}
                {it.referenceConfirmed != null && (
                  <span className="chip">reference {it.referenceConfirmed ? "confirmed" : "unconfirmed"}</span>
                )}
              </div>
            </header>

            <div className="lab-review-layout">
              <LabProofGallery
                primary={it.proofImages.map((name) => ({ src: fileUrl(permit, name), label: `${it.identities.join(" · ")}: ${proofLabel(name)}` }))}
                details={it.edgeZooms.map((name) => ({ src: fileUrl(permit, name), label: proofLabel(name) }))}
              />

              <aside className="lab-review-controls">
                <div className="lab-review-explanation">
                  <span className="eyebrow">Why it was flagged</span>
                  <p>{it.reason ?? "No measurement explanation was recorded."}</p>
                </div>
                <div className="lab-review-decision-copy">
                  <strong>Your decision</strong>
                  <span>Check the colored room outline first. Open an edge detail only when the room view is not enough.</span>
                </div>
                <div className="lab-decision-actions">
                  {ACTIONS.map((action) => (
                    <button
                      key={action.key}
                      className={`btn${st?.decision === action.decision ? " primary" : ""}`}
                      disabled={st?.busy}
                      onClick={() => decide(it, action)}
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
                {st?.busy && <p className="lab-save-state">saving…</p>}
                {st?.decision && !st.busy && !st.error && <p className="lab-save-state saved">Saved: {st.decision}</p>}
                {st?.error && <p className="lab-save-state error">Error: {st.error}</p>}
              </aside>
            </div>
          </article>
        );
      })}
    </div>
  );
}
