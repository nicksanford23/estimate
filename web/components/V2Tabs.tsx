import Link from "next/link";

export default function V2Tabs({ permit, active }: { permit: string; active: "pages" | "rooms" | "geometry" }) {
  const tabs = [
    { key: "pages", label: "Pages", href: `/v2/b/${permit}` },
    { key: "rooms", label: "Rooms & Finishes", href: `/v2/b/${permit}/rooms` },
    { key: "geometry", label: "Geometry Review", href: `/v2/b/${permit}/geometry` },
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
