import Link from "next/link";
import { notFound } from "next/navigation";
import { getPermit, CODE_LABEL, type DocRow } from "@/lib/queries";

export const dynamic = "force-dynamic";

const fmt = (n: number) => n.toLocaleString("en-US");

export default async function PermitDetail({
  params,
}: {
  params: Promise<{ permitNum: string }>;
}) {
  const { permitNum } = await params;
  const data = await getPermit(decodeURIComponent(permitNum));
  if (!data) notFound();
  const p = data.permit as Record<string, unknown>;
  const docs = data.docs;

  const str = (k: string) => {
    const v = p[k];
    return v == null || v === "" ? null : String(v);
  };
  const meta: [string, string | null][] = [
    ["Code", str("code") ? `${str("code")} · ${CODE_LABEL[str("code")!] ?? ""}` : null],
    ["Use class", str("permit_class")],
    ["Address", [str("address"), str("city"), str("zip")].filter(Boolean).join(", ") || null],
    ["Sq ft", str("sqft")],
    ["Cost", str("cost") ? `$${Number(str("cost")).toLocaleString()}` : null],
    ["Contractor", str("contractor")],
    ["Status", str("status")],
    ["Applied", str("applied_date")],
  ];
  const nDown = docs.filter((d) => d.downloaded).length;
  const withFile = docs
    .filter((d) => d.downloaded)
    .sort(
      (a, b) =>
        Number(b.labeled) - Number(a.labeled) ||
        (a.name ?? "").localeCompare(b.name ?? "")
    );
  const noFile = docs.filter((d) => !d.downloaded);

  const Row = (d: DocRow) => (
    <div className="doc-row" key={d.doc_id}>
      <span className="nm" title={d.name ?? ""}>
        {d.name || `Document ${d.doc_id}`}
      </span>
      <div className="badges">
        {d.downloaded ? (
          <span className="badge downloaded">downloaded</span>
        ) : (
          <span className="badge none">not downloaded</span>
        )}
        {d.rendered && <span className="badge rendered">{fmt(d.pages)} pp</span>}
        {d.labeled && <span className="badge labeled">labeled</span>}
      </div>
      <div className="actions">
        {d.labeled && (
          <Link className="btn primary" href={`/documents/${d.doc_id}`}>
            View labels
          </Link>
        )}
        {d.downloaded ? (
          <a
            className={d.labeled ? "btn ghost" : "btn primary"}
            href={`/api/pdf/${d.doc_id}`}
            target="_blank"
            rel="noopener"
          >
            View PDF
          </a>
        ) : (
          <span className="btn disabled" title="Download coming in a later step">
            Download
          </span>
        )}
      </div>
    </div>
  );

  return (
    <main className="container">
      <Link href="/permits" className="back">
        ← all permits
      </Link>

      <div className="detail-head">
        <div className="eyebrow">{CODE_LABEL[str("code") ?? ""] ?? "Permit"}</div>
        <h1>{String(p.permit_num)}</h1>
        <div style={{ color: "var(--muted)", fontSize: 15 }}>
          {str("description") || "—"}
        </div>
        <div className="meta-grid">
          {meta
            .filter(([, v]) => v)
            .map(([k, v]) => (
              <div key={k}>
                <div className="k">{k}</div>
                <div className="v">{v}</div>
              </div>
            ))}
        </div>
      </div>

      <div className="section-title">
        Documents — {fmt(docs.length)} total · {fmt(nDown)} downloaded
      </div>

      {docs.length === 0 ? (
        <div className="empty">No document list scraped for this permit yet.</div>
      ) : (
        <>
          {withFile.length > 0 ? (
            <div className="doc-list">{withFile.map((d) => Row(d))}</div>
          ) : (
            <div className="empty" style={{ padding: "24px 0" }}>
              No documents downloaded for this permit yet.
            </div>
          )}
          {noFile.length > 0 && (
            <details className="more">
              <summary>{fmt(noFile.length)} more documents (not downloaded)</summary>
              <div className="doc-list" style={{ marginTop: 10 }}>
                {noFile.map((d) => Row(d))}
              </div>
            </details>
          )}
        </>
      )}
      <div style={{ height: 50 }} />
    </main>
  );
}
