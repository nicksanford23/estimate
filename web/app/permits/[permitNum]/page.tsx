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
  // The city stores repeat uploads as separate records with identical
  // filenames (mostly inspection photos), so collapse documents by name.
  const groupMap = new Map<string, DocRow[]>();
  for (const d of docs) {
    const key = (d.name ?? `Document ${d.doc_id}`).trim();
    const arr = groupMap.get(key) ?? [];
    arr.push(d);
    groupMap.set(key, arr);
  }
  type Grp = { name: string; docs: DocRow[]; down: boolean; lab: boolean };
  const groups: Grp[] = [...groupMap.entries()].map(([name, gd]) => ({
    name,
    docs: gd,
    down: gd.some((d) => d.downloaded),
    lab: gd.some((d) => d.labeled),
  }));
  const withFile = groups
    .filter((g) => g.down)
    .sort((a, b) => Number(b.lab) - Number(a.lab) || a.name.localeCompare(b.name));
  const noFile = groups.filter((g) => !g.down).sort((a, b) => a.name.localeCompare(b.name));
  const uniqueNames = groups.length;

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

  const groupRow = (g: Grp) => {
    if (g.docs.length === 1) return Row(g.docs[0]);
    const sorted = [...g.docs].sort(
      (a, b) =>
        Number(b.labeled) - Number(a.labeled) ||
        Number(b.downloaded) - Number(a.downloaded)
    );
    return (
      <details className="dupgroup" key={g.name}>
        <summary>
          <span className="nm">{g.name}</span>
          <span className="chip">×{g.docs.length} copies</span>
          {g.lab ? (
            <span className="badge labeled">labeled</span>
          ) : g.down ? (
            <span className="badge downloaded">has file</span>
          ) : null}
        </summary>
        <div className="doc-list" style={{ marginTop: 8 }}>
          {sorted.map((d) => Row(d))}
        </div>
      </details>
    );
  };

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
        Documents — {fmt(uniqueNames)} unique · {fmt(docs.length)} total · {fmt(nDown)} downloaded
      </div>

      {docs.length === 0 ? (
        <div className="empty">No document list scraped for this permit yet.</div>
      ) : (
        <>
          {withFile.length > 0 ? (
            <div className="doc-list">{withFile.map((g) => groupRow(g))}</div>
          ) : (
            <div className="empty" style={{ padding: "24px 0" }}>
              No documents downloaded for this permit yet.
            </div>
          )}
          {noFile.length > 0 && (
            <details className="more">
              <summary>{fmt(noFile.length)} more document names (not downloaded)</summary>
              <div className="doc-list" style={{ marginTop: 10 }}>
                {noFile.map((g) => groupRow(g))}
              </div>
            </details>
          )}
        </>
      )}
      <div style={{ height: 50 }} />
    </main>
  );
}
