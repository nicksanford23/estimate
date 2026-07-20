"use client";
// TEMP ML workbench — the review queue (the star of the project page). Renders
// each measured surface awaiting an S8 human decision with proof image(s) and
// the four decision buttons, POSTing to /api/lab/decide (append-only). Local
// state reflects the just-saved decision; the durable truth is the JSONL.
//
// FOUNDER CAVEAT: functional slice, pending founder visual sign-off.
import { useState } from "react";

export interface QueueItemView {
  id: string;
  identities: string[];
  identityLabel: string | null;
  verdict: string;
  worstDeviationIn: number | null;
  reason: string | null;
  proofImages: string[];
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
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 14, marginTop: 8 }}>
      {items.map((it) => {
        const st = state[it.id];
        return (
          <div key={it.id} className="permit-card" style={{ cursor: "default" }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <strong>{it.identities.join(" · ") || it.id}</strong>
              {it.identityLabel && <span style={{ fontSize: 12, opacity: 0.7 }}>{it.identityLabel}</span>}
              <span className="chip code">{it.verdict}</span>
              {it.worstDeviationIn != null && <span className="chip">worst {it.worstDeviationIn.toFixed(1)} in</span>}
              {it.referenceConfirmed != null && (
                <span className="chip">ref {it.referenceConfirmed ? "confirmed" : "unconfirmed"}</span>
              )}
            </div>
            {it.reason && <p style={{ fontSize: 12.5, opacity: 0.8, margin: "6px 0 0" }}>{it.reason}</p>}
            {it.proofImages.length > 0 && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                {it.proofImages.map((name) => (
                  <a key={name} href={fileUrl(permit, name)} target="_blank" rel="noreferrer" style={{ flex: "1 1 140px", minWidth: 0 }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={fileUrl(permit, name)}
                      alt={name}
                      loading="lazy"
                      style={{ width: "100%", borderRadius: 8, border: "1px solid var(--line)" }}
                    />
                  </a>
                ))}
              </div>
            )}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
              {ACTIONS.map((a) => (
                <button
                  key={a.key}
                  className={`btn${st?.decision === a.decision ? " primary" : ""}`}
                  disabled={st?.busy}
                  onClick={() => decide(it, a)}
                >
                  {a.label}
                </button>
              ))}
            </div>
            {st?.decision && !st.error && (
              <p style={{ fontSize: 12, marginTop: 6, color: "var(--accent-ink)" }}>saved: {st.decision}</p>
            )}
            {st?.error && <p style={{ fontSize: 12, marginTop: 6, color: "crimson" }}>error: {st.error}</p>}
          </div>
        );
      })}
    </div>
  );
}
