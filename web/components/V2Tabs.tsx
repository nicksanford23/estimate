import Link from "next/link";

// Product navigation for one project (V2_PRODUCT_REBUILD_PLAN_V1.md §6).
// The permanent set is Overview | Plan Set | Rooms & Finishes | Floor Areas.
// `Estimate` is intentionally absent until it performs a real end-to-end
// quantity function (§6, §19 non-goal: no decorative tab). The old
// `Outline Rooms` and `Geometry Review` screens are removed from normal
// navigation; they survive as internal/legacy routes but are not linked here.
export type V2Tab = "overview" | "planset" | "rooms" | "floor";

export default function V2Tabs({ permit, active }: { permit: string; active: V2Tab }) {
  const tabs = [
    { key: "overview", label: "Overview", href: `/v2/b/${permit}` },
    { key: "planset", label: "Plan Set", href: `/v2/b/${permit}/plan-set` },
    { key: "rooms", label: "Rooms & Finishes", href: `/v2/b/${permit}/rooms` },
    { key: "floor", label: "Floor Areas", href: `/v2/b/${permit}/floor-areas` },
  ] as const;
  return (
    <div className="v2tabs">
      {tabs.map((t) => (
        <Link key={t.key} href={t.href} className={`v2tab${active === t.key ? " v2tab-on" : ""}`}>
          {t.label}
        </Link>
      ))}
    </div>
  );
}
