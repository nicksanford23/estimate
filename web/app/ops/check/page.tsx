import { buildCheckQueue } from "@/lib/opsQueue";
import CheckQueue from "@/components/CheckQueue";

export const dynamic = "force-dynamic";

export default async function OpsCheckPage() {
  const items = buildCheckQueue();
  return (
    <main>
      <div className="page-head" style={{ padding: "8px 0 4px" }}>
        <div className="eyebrow">{items.length} in queue</div>
        <h1 style={{ fontSize: 20 }}>Check queue</h1>
        <p>
          Unclear permits first, then borderline gate candidates never eyeballed, then logged
          rules-vs-model disagreements. Every judgment appends one row to
          data/triage/eyeball_verdicts.csv (slice=nick) — nothing is ever rewritten.
        </p>
      </div>
      <CheckQueue items={items} />
    </main>
  );
}
