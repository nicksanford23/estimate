import { notFound } from "next/navigation";
import Link from "next/link";
import { getBuildingDetail } from "@/lib/v2Db";
import V2PageCard from "@/components/V2PageCard";

export const dynamic = "force-dynamic";

export default async function V2BuildingPage({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  const detail = await getBuildingDetail(permit);
  if (!detail) return notFound();

  return (
    <div className="container">
      <div className="page-head">
        <Link href="/v2" style={{ fontSize: 13 }}>&larr; Pilot Buildings</Link>
        <h1>{detail.building?.building_name ?? permit}</h1>
        <p style={{ fontFamily: "var(--font-mono)" }}>{detail.permit}</p>
      </div>
      {detail.docs.map((doc) => (
        <section key={doc.document_id} style={{ marginTop: 20 }}>
          <h3 style={{ fontFamily: "var(--font-mono)", fontSize: 14 }}>
            doc {doc.onestop_doc_id} {doc.filename ? `— ${doc.filename}` : ""}
          </h3>
          {doc.pages.length === 0 && <p style={{ color: "var(--muted)" }}>No page rows yet for this doc.</p>}
          {doc.pages.map((page) => (
            <V2PageCard key={page.page_id} page={page} />
          ))}
        </section>
      ))}
      {detail.docs.length === 0 && <p style={{ color: "var(--muted)" }}>No documents backfilled for this permit.</p>}
    </div>
  );
}
