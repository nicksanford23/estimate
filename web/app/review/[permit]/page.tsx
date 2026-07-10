import Link from "next/link";
import { loadDemo } from "@/lib/demo";
import ReviewScreen from "@/components/ReviewScreen";

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ permit: string }>;
}) {
  const { permit } = await params;
  const id = decodeURIComponent(permit);
  const data = loadDemo(id);

  if (!data) {
    return (
      <main className="container">
        <Link href="/demo" className="back">
          ← All projects
        </Link>
        <div className="empty" style={{ paddingTop: 60 }}>
          No demo data for {id}.
        </div>
      </main>
    );
  }

  return <ReviewScreen permit={id} data={data} />;
}
