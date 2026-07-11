"use client";
import { useState } from "react";

export type DocumentsTabRow = {
  docId: string;
  name: string | null;
  downloaded: boolean;
  downloadedAt: string | null;
};

// Documents tab, rebuilt per founder feedback: drop the type-badge (mostly
// wrong), pages-count, and downloaded-checkmark columns. Each row is just
// filename + date + one action button: Open PDF when we have it, else
// Download (which fetches it server-side on demand and flips to Open PDF).
export default function DocumentsTab({ permit, rows }: { permit: string; rows: DocumentsTabRow[] }) {
  const [state, setState] = useState(() => new Map(rows.map((r) => [r.docId, r])));
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Map<string, string>>(new Map());

  const download = async (docId: string) => {
    setPending((prev) => new Set(prev).add(docId));
    setErrors((prev) => {
      const next = new Map(prev);
      next.delete(docId);
      return next;
    });
    try {
      const r = await fetch("/api/ops/fetch-doc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: docId, permit }),
      });
      const body = await r.json().catch(() => ({}));
      if (r.ok && (body.status === "ok" || body.status === "already_in_r2")) {
        setState((prev) => {
          const next = new Map(prev);
          const row = next.get(docId);
          if (row) next.set(docId, { ...row, downloaded: true, downloadedAt: new Date().toISOString() });
          return next;
        });
      } else {
        setErrors((prev) => new Map(prev).set(docId, body.status ?? body.error ?? `HTTP ${r.status}`));
      }
    } catch (e) {
      setErrors((prev) => new Map(prev).set(docId, String(e)));
    } finally {
      setPending((prev) => {
        const next = new Set(prev);
        next.delete(docId);
        return next;
      });
    }
  };

  const rowsOrdered = rows.map((r) => state.get(r.docId) ?? r);

  return (
    <>
      <div className="section-title">Documents ({rowsOrdered.length})</div>
      <div className="ops-table-wrap">
        <table className="ops-table">
          <thead>
            <tr>
              <th>Doc</th>
              <th>Name</th>
              <th>Date</th>
              <th>File</th>
            </tr>
          </thead>
          <tbody>
            {rowsOrdered.map((d) => {
              const isPending = pending.has(d.docId);
              const error = errors.get(d.docId);
              return (
                <tr key={d.docId}>
                  <td className="mono-num">{d.docId}</td>
                  <td className="wrap">{d.name ?? <span className="dash">—</span>}</td>
                  <td className="mono-num">{d.downloadedAt ? d.downloadedAt.slice(0, 10) : <span className="dash">—</span>}</td>
                  <td>
                    {d.downloaded ? (
                      <a href={`/api/pdf/${d.docId}`} target="_blank" rel="noreferrer" className="btn ghost">
                        Open PDF ↗
                      </a>
                    ) : (
                      <>
                        <button
                          className="btn"
                          disabled={isPending}
                          onClick={() => download(d.docId)}
                        >
                          {isPending ? "Downloading…" : "Download"}
                        </button>
                        {error && (
                          <span className="hint" style={{ marginLeft: 8, color: "var(--bad)" }}>
                            {error}
                          </span>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
            {rowsOrdered.length === 0 && (
              <tr>
                <td colSpan={4} className="empty">
                  No document inventory on file for this permit.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
