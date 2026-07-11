"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// V2 screens own their chrome — the legacy global nav hides there.
export default function GlobalNav() {
  const pathname = usePathname();
  if (pathname?.startsWith("/v2")) return null;
  return (
    <nav className="nav">
      <div className="container nav-in">
        <Link href="/" className="brand">
          <span className="dot" />
          PLAN&nbsp;SETS
        </Link>
        <Link href="/permits" className="link" style={{ opacity: 0.6 }}>
          Legacy
        </Link>
        <Link href="/ops" className="link">
          Ops
        </Link>
        <span className="spacer" />
        <span className="link mono" style={{ fontSize: 12 }}>
          NOLA · commercial
        </span>
      </div>
    </nav>
  );
}
