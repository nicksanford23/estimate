"use client";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import OpsSubnav from "@/components/OpsSubnav";

// Building workbench pages (/ops/permits/<id>) render their own compact
// header + tab strip and must NOT show the Mission Control eyebrow/subnav —
// founder feedback: workbench page = compact header + tabs only, back link
// is the only nav affordance. The /ops/permits list page itself still gets
// the full frame.
const WORKBENCH_RE = /^\/ops\/permits\/[^/]+$/;

export default function OpsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isWorkbench = WORKBENCH_RE.test(pathname ?? "");

  if (isWorkbench) {
    return <div className="container">{children}</div>;
  }

  return (
    <div className="container">
      <div className="page-head">
        <div className="eyebrow">Internal · read-only except the check queue</div>
        <h1>Mission Control</h1>
        <p>See the data machine, check the models, catch what agents miss.</p>
      </div>
      <OpsSubnav />
      {children}
    </div>
  );
}
