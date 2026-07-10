"use client";
import { useState, type ReactNode } from "react";
import PagesTab, { type PagesTabDoc } from "./PagesTab";

export type WorkbenchTab = "overview" | "documents" | "pages" | "history" | "takeoff";

const TAB_LABELS: Record<WorkbenchTab, string> = {
  overview: "Overview",
  documents: "Documents",
  pages: "Pages",
  history: "History",
  takeoff: "Takeoff",
};

export default function PermitWorkbenchTabs({
  permit,
  overview,
  documents,
  pagesDocs,
  history,
  takeoff,
}: {
  permit: string;
  overview: ReactNode;
  documents: ReactNode;
  pagesDocs: PagesTabDoc[];
  history: ReactNode;
  takeoff: ReactNode;
}) {
  const [tab, setTab] = useState<WorkbenchTab>("overview");

  const tabs: WorkbenchTab[] = ["overview", "documents", "pages", "history", "takeoff"];

  return (
    <div className="workbench">
      <div className="workbench-tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`workbench-tab ${tab === t ? "active" : ""}`}
            onClick={() => setTab(t)}
          >
            {TAB_LABELS[t]}
            {t === "pages" && pagesDocs.length > 0 && <span className="wt-count">{pagesDocs.length}</span>}
          </button>
        ))}
      </div>
      <div className="workbench-panel">
        {tab === "overview" && overview}
        {tab === "documents" && documents}
        {tab === "pages" && <PagesTab permit={permit} docs={pagesDocs} />}
        {tab === "history" && history}
        {tab === "takeoff" && takeoff}
      </div>
    </div>
  );
}
