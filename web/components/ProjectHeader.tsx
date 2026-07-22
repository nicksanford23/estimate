import Link from "next/link";
import V2Tabs, { type V2Tab } from "@/components/V2Tabs";
import { displayTitle, shortDescription, type ProjectDisplayInput } from "@/lib/projectDisplay";

// Shared project header (V2_PRODUCT_REBUILD_PLAN_V1.md §4). Address/name is the
// dominant title; the permit number is subdued metadata. Used across Overview,
// Plan Set, Rooms & Finishes, and Floor Areas so identity reads the same
// everywhere.
export default function ProjectHeader({
  identity,
  active,
  permit,
}: {
  identity: ProjectDisplayInput | null;
  active: V2Tab;
  permit: string;
}) {
  const title = identity ? displayTitle(identity) : permit;
  const sub = identity ? shortDescription(identity.city_description) : "";
  return (
    <div className="page-head" style={{ marginBottom: 0 }}>
      <Link href="/v2" style={{ fontSize: 13 }}>&larr; Projects</Link>
      <h1 style={{ margin: "6px 0 2px" }}>{title}</h1>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        {sub && sub !== title && <span style={{ color: "var(--muted)", fontSize: 13 }}>{sub}</span>}
        <span className="proj-permit" style={{ fontSize: 12 }}>Permit {permit}</span>
      </div>
      <V2Tabs permit={permit} active={active} />
    </div>
  );
}
