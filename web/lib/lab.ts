// Temporary ML-workbench helpers — deliberately minimal (founder-requested
// interim surface, 2026-07-17). Reads the data/sam_smoke pipeline artifacts
// directly. Replaced by the real product surface after the process stabilizes.
import fs from "fs";
import path from "path";

const ROOT = path.join(process.cwd(), "..");
export const SMOKE = path.join(ROOT, "data", "sam_smoke");
export const PDF_DIR = path.join(ROOT, "data", "render_cache", "pdf");

// Source plan documents per project (active revision first).
export const PROJECT_DOCS: Record<string, string[]> = {
  "24-06748-RNVS": ["7372349"],
  "14-11290-NEWC": ["1494156"],
  "20-29653-RNVS": ["4941409", "4941399", "4941401", "4941403"],
};

// Human names (address + what it is). Projects are never shown to people by
// permit number — that's internal plumbing (founder rule, 2026-07-17).
export const PROJECT_NAMES: Record<string, { name: string; blurb: string }> = {
  "24-06748-RNVS": { name: "600 Baronne St", blurb: "4-story corner building — mixed use, decks on top" },
  "14-11290-NEWC": { name: "Liberty Bank — 3002 Gentilly Blvd", blurb: "new bank branch with retail space" },
  "20-29653-RNVS": { name: "1514 Calhoun St", blurb: "interior renovation — two of four units on file" },
};

export function projectName(permit: string): string {
  return PROJECT_NAMES[permit]?.name ?? permit;
}

export type LabRoom = {
  code: string;
  overlay: boolean;
  confidence: number | null;
  outcome: string | null;      // proposal outcome suggestion
  decision: string | null;     // latest human decision if any
  inspection: "pass" | "repaired" | "unresolved" | null; // edge-inspection room verdict
  repairImage: boolean;        // before/after render exists
};

export type LabProject = {
  permit: string;
  rooms: LabRoom[];
  keptPdf: boolean;
  docs: string[];
  report: boolean;
};

function latestDecisions(permit: string): Record<string, string> {
  const p = path.join(ROOT, "data", "geometry_annotations", "human", `${permit}.outcomes.jsonl`);
  const out: Record<string, string> = {};
  if (!fs.existsSync(p)) return out;
  for (const line of fs.readFileSync(p, "utf8").split("\n").filter(Boolean)) {
    try {
      const r = JSON.parse(line);
      out[r.task_id] = r.decision ?? "saved";
    } catch { /* skip */ }
  }
  return out;
}

export function loadProject(permit: string): LabProject | null {
  const dir = path.join(SMOKE, permit);
  if (!fs.existsSync(dir) || !/^[A-Za-z0-9-]+$/.test(permit)) return null;
  const propsPath = path.join(dir, "results", "proposals_for_editor.json");
  // edge-inspection verdicts, if the inspector has run on this project
  const inspection: Record<string, { verdict: string }> = {};
  const inspPath = path.join(dir, "inspection", "edge_inspection.json");
  if (fs.existsSync(inspPath)) {
    try {
      const raw = JSON.parse(fs.readFileSync(inspPath, "utf8"));
      const roomsArr = Array.isArray(raw) ? raw : raw.rooms ?? Object.values(raw);
      for (const r of roomsArr) {
        if (r && typeof r === "object" && "code" in r)
          inspection[String(r.code)] = { verdict: String(r.room_verdict ?? "") };
      }
    } catch { /* ignore unreadable inspection */ }
  }
  const rooms: LabRoom[] = [];
  const decisions = latestDecisions(permit);
  if (fs.existsSync(propsPath)) {
    try {
      const props = JSON.parse(fs.readFileSync(propsPath, "utf8"));
      for (const [taskId, p] of Object.entries<Record<string, unknown>>(props)) {
        const code = String(p.code ?? taskId);
        const v = inspection[code]?.verdict ?? null;
        rooms.push({
          code,
          overlay: fs.existsSync(path.join(dir, "claude_vision", `overlay_${code}.png`)),
          confidence: typeof p.confidence === "number" ? p.confidence : null,
          outcome: typeof p.outcome_suggestion === "string" ? p.outcome_suggestion : null,
          decision: decisions[taskId] ?? null,
          inspection: v === "pass" ? "pass" : v === "needs_repair" ? "repaired" : v === "unresolved" ? "unresolved" : null,
          repairImage: fs.existsSync(path.join(dir, "inspection", `repair_${code}.png`)),
        });
      }
    } catch { /* unreadable proposals -> empty room list */ }
  }
  rooms.sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true }));
  return {
    permit,
    rooms,
    keptPdf: fs.existsSync(path.join(dir, `${permit}_kept_pages.pdf`)),
    docs: (PROJECT_DOCS[permit] ?? []).filter((d) => fs.existsSync(path.join(PDF_DIR, `${d}.pdf`))),
    report: fs.existsSync(path.join(dir, "PIPELINE_REPORT.md")),
  };
}

export function listProjects(): LabProject[] {
  if (!fs.existsSync(SMOKE)) return [];
  return fs.readdirSync(SMOKE)
    .filter((d) => fs.statSync(path.join(SMOKE, d)).isDirectory())
    .map(loadProject)
    .filter((p): p is LabProject => p !== null)
    .sort((a, b) => b.rooms.length - a.rooms.length);
}
