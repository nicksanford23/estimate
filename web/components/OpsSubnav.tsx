"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/ops", label: "Funnel" },
  { href: "/ops/permits", label: "Buildings" },
  { href: "/ops/check", label: "Check queue" },
  { href: "/ops/models", label: "Model report card" },
];

export default function OpsSubnav() {
  const pathname = usePathname();
  return (
    <nav className="ops-subnav">
      {TABS.map((t) => {
        const on = t.href === "/ops" ? pathname === "/ops" : pathname.startsWith(t.href);
        return (
          <Link key={t.href} href={t.href} className={on ? "on" : ""}>
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
