import Link from "next/link";
import { notFound } from "next/navigation";
import { getLabeledDoc } from "@/lib/queries";
import LabeledGrid from "@/components/LabeledGrid";

export const dynamic = "force-dynamic";

export default async function DocLabeled({
  params,
}: {
  params: Promise<{ docId: string }>;
}) {
  const { docId } = await params;
  if (!/^\d+$/.test(docId)) notFound();
  const data = await getLabeledDoc(docId);
  if (!data.pages.length) notFound();

  return (
    <main className="container">
      <Link
        href={data.permit ? `/permits/${encodeURIComponent(data.permit)}` : "/permits"}
        className="back"
      >
        ← {data.permit ?? "permits"}
      </Link>
      <LabeledGrid {...data} />
    </main>
  );
}
