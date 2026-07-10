import Link from "next/link";
import { DEMO_PERMITS, loadDemo } from "@/lib/demo";

const fmt = (n: number) => Math.round(n).toLocaleString("en-US");

export default function DemoIndexPage() {
  const projects = DEMO_PERMITS.map((id) => ({ id, data: loadDemo(id) })).filter(
    (x): x is { id: string; data: NonNullable<ReturnType<typeof loadDemo>> } => x.data != null
  );

  return (
    <main className="container">
      <div className="page-head">
        <div className="eyebrow">Review screen · concept prototype</div>
        <h1>Pick a building</h1>
        <p>
          Three real permits run through the takeoff pipeline. Click through each one the way an
          estimator would — accept the confident rooms, see where the pipeline needs your eyes.
        </p>
      </div>
      <div className="permit-grid">
        {projects.map(({ id, data }) => {
          // same policy as the review screen: unanchored (unlabeled) shapes
          // never contribute to room counts or SF totals
          const rooms = data.pages.flatMap((p) => p.rooms).filter((r) => !r.unlabeled);
          const totalSf = rooms.reduce((s, r) => s + (r.sf || 0), 0);
          const verifiedSf = rooms
            .filter((r) => r.status === "accepted")
            .reduce((s, r) => s + (r.sf || 0), 0);
          const needsReview = rooms.filter((r) => r.status !== "accepted").length;
          return (
            <Link
              key={id}
              href={`/review/${encodeURIComponent(id)}`}
              className="permit-card"
            >
              <div className="top">
                <span className="pnum">{data.project.name}</span>
              </div>
              <div className="addr mono">{id}</div>
              <div className="foot">
                <span className="chip">{rooms.length} rooms</span>
                <span className="chip">{fmt(totalSf)} SF total</span>
                <span className="chip">{fmt(verifiedSf)} SF verified</span>
                {needsReview > 0 && (
                  <span className="badge rendered">{needsReview} need review</span>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </main>
  );
}
