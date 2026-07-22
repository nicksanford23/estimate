import { notFound } from "next/navigation";
import Link from "next/link";
import { getPermitDocuments } from "@/lib/v2Db";
import V2Tabs from "@/components/V2Tabs";

export const dynamic = "force-dynamic";

export default async function V2DocsPage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const data = await getPermitDocuments(permit);
  if (!data) return notFound();
  const { building, docs } = data;

  return (
    <div className="v2board">
      <div className="v2board-main">
        <div className="page-head" style={{ marginBottom: 0 }}>
          <Link href={`/v2/b/${permit}/plan-set`} style={{ fontSize: 13 }}>&larr; Plan Set</Link>
          <h1 style={{ margin: "6px 0 2px" }}>{building?.building_name ?? permit}</h1>
          <span className="proj-permit" style={{ fontSize: 12 }}>Permit {permit}</span>
        </div>
        <V2Tabs permit={permit} active="planset" />

        <p style={{ color: "var(--muted)", fontSize: 13, margin: "0 0 10px" }}>
          Every document on file for this permit ({docs.length}). The one loaded into the tools is tagged{" "}
          <b>loaded plan set</b>. Click any row to open the PDF in a new tab.
        </p>

        <div className="v2docs-list">
          {docs.map((d) => (
            <a
              key={d.doc_id}
              href={`/api/pdf/${d.doc_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="v2docrow"
            >
              <span className="v2docrow-name">{d.name ?? `doc ${d.doc_id}`}</span>
              <span style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
                {d.is_loaded && (
                  <span className="chip" style={{ borderColor: "var(--accent)", color: "var(--accent-ink)" }}>
                    loaded plan set
                  </span>
                )}
                <span className="v2docrow-open">Open&nbsp;&#8599;</span>
              </span>
            </a>
          ))}
          {docs.length === 0 && <p style={{ color: "var(--muted)" }}>No documents on file for this permit.</p>}
        </div>
      </div>
    </div>
  );
}
