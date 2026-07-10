import type { ReactNode } from "react";
import OpsSubnav from "@/components/OpsSubnav";

export default function OpsLayout({ children }: { children: ReactNode }) {
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
