"use client";
import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import type { QueueItem } from "@/lib/opsQueue";

const KIND_LABEL: Record<QueueItem["kind"], string> = {
  unclear: "Unclear",
  borderline: "Borderline",
  dual: "Dual-engine",
};

export default function CheckQueue({ items }: { items: QueueItem[] }) {
  const [idx, setIdx] = useState(0);
  const [reason, setReason] = useState("");
  const [reasonKey, setReasonKey] = useState<string | null>(null);
  const [done, setDone] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const remaining = useMemo(() => items.filter((it) => !done.has(it.key)), [items, done]);
  const clampedIdx = Math.max(0, Math.min(idx, remaining.length - 1));
  const shown = remaining[clampedIdx] ?? null;

  // Reset the reason field when the displayed item changes. This runs
  // during render (not an effect) — the recommended pattern for "adjust
  // state when a derived value changes" (react.dev/learn/you-might-not-need-an-effect).
  if (shown && shown.key !== reasonKey) {
    setReasonKey(shown.key);
    if (reason !== "") setReason("");
  } else if (!shown && reasonKey !== null) {
    setReasonKey(null);
  }

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2200);
    return () => clearTimeout(t);
  }, [toast]);

  const submit = useCallback(
    async (verdict: "CONFIRMED" | "FALSE_PASS" | "UNCLEAR") => {
      if (!shown || busy) return;
      setBusy(true);
      try {
        const res = await fetch("/api/ops/verdict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            permit: shown.permit,
            doc_id: shown.doc_id,
            page: shown.page,
            verdict,
            reason,
          }),
        });
        if (!res.ok) throw new Error((await res.json()).error ?? "failed");
        setDone((d) => new Set(d).add(shown.key));
        setToast(`${verdict} — ${shown.permit} logged`);
      } catch (e) {
        setToast(`Failed to save: ${e instanceof Error ? e.message : e}`);
      } finally {
        setBusy(false);
      }
    },
    [shown, reason, busy]
  );

  const skip = useCallback(
    (dir: 1 | -1) => {
      setIdx((i) => Math.max(0, Math.min(remaining.length - 1, i + dir)));
    },
    [remaining.length]
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLInputElement) return;
      if (e.key === "y") submit("CONFIRMED");
      else if (e.key === "n") submit("FALSE_PASS");
      else if (e.key === "u") submit("UNCLEAR");
      else if (e.key === "ArrowRight") skip(1);
      else if (e.key === "ArrowLeft") skip(-1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [submit, skip]);

  if (!items.length) {
    return (
      <div className="check-stage check-empty">
        <div className="big">✓</div>
        <h2>Queue drained</h2>
        <p className="hint">No UNCLEAR permits, borderline gate candidates, or logged dual-engine disagreements right now.</p>
      </div>
    );
  }
  if (!shown) {
    return (
      <div className="check-stage check-empty">
        <div className="big">✓</div>
        <h2>All caught up</h2>
        <p className="hint">You cleared everything in this session&apos;s queue.</p>
        <Link href="/ops/check" className="btn primary" style={{ marginTop: 14, display: "inline-block" }}>
          Check for new items
        </Link>
      </div>
    );
  }

  const imgSrc = shown.overlay ? `/api/opsimg/${shown.overlay.rel.split("/").map(encodeURIComponent).join("/")}` : null;
  const pdfHref = shown.doc_id ? `/api/pdf/${shown.doc_id}` : null;

  return (
    <div className="check-wrap">
      <div className="check-remain">
        {remaining.length} remaining · {done.size} logged this session
      </div>
      <div className="check-stage">
        <div className="check-imgwrap">
          {imgSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={imgSrc} alt={shown.permit} />
          ) : (
            <div className="check-noimg">
              No rendered overlay for this candidate yet.
              {pdfHref && (
                <>
                  {" "}
                  <a href={pdfHref} target="_blank" rel="noreferrer" style={{ color: "#83b6e4" }}>
                    Open the source PDF ↗
                  </a>
                </>
              )}
            </div>
          )}
        </div>
        <div className="check-meta">
          <div className="kind">{KIND_LABEL[shown.kind]}</div>
          <h2>
            {shown.permit}
            {shown.doc_id ? ` · doc ${shown.doc_id}` : ""}
            {shown.page ? ` · p${shown.page}` : ""}
          </h2>
          <div>{shown.kindLabel}</div>
          {shown.priorReason && <div className="prior">Prior note: {shown.priorReason}</div>}
          {Object.keys(shown.metrics).length > 0 && (
            <div className="check-metrics">
              {Object.entries(shown.metrics).map(([k, v]) => (
                <span key={k}>
                  {k}: {v}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="check-reason">
          <textarea
            placeholder="Optional reason (why confirmed / rejected / unsure)…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
        <div className="check-actions">
          <button className="check-btn confirm" disabled={busy} onClick={() => submit("CONFIRMED")}>
            CONFIRMED
            <span className="k">y</span>
          </button>
          <button className="check-btn reject" disabled={busy} onClick={() => submit("FALSE_PASS")}>
            FALSE PASS
            <span className="k">n</span>
          </button>
          <button className="check-btn unsure" disabled={busy} onClick={() => submit("UNCLEAR")}>
            UNSURE
            <span className="k">u</span>
          </button>
        </div>
      </div>
      <p className="hint" style={{ textAlign: "center", marginTop: 10 }}>
        Keyboard: y = confirmed, n = false pass, u = unsure, ← → = browse the queue
      </p>
      {toast && <div className="check-toast">{toast}</div>}
    </div>
  );
}
