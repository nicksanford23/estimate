// The ONE permitted mutation in the Ops dashboard: append a row to
// data/triage/eyeball_verdicts.csv (Screen C). Append-only — never rewrites
// or deletes existing rows, matching CLAUDE.md's append-only label rule
// extended to verdicts.
import fs from "node:fs";
import path from "node:path";
import { DATA_ROOT, PATHS } from "./opsData";

const COLUMNS = ["permit", "doc_id", "page", "verdict", "is_floor_plan", "reason", "slice", "ts_utc"];

function csvField(v: string): string {
  if (v == null) return "";
  const s = String(v);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export type NewVerdict = {
  permit: string;
  doc_id: string;
  page: string;
  verdict: "CONFIRMED" | "FALSE_PASS" | "UNCLEAR";
  reason: string;
};

export function appendVerdict(v: NewVerdict): void {
  if (!/^[A-Za-z0-9-]+$/.test(v.permit)) throw new Error("bad permit");
  if (!/^\d*$/.test(v.doc_id)) throw new Error("bad doc_id");
  if (!/^\d*$/.test(v.page)) throw new Error("bad page");
  if (!["CONFIRMED", "FALSE_PASS", "UNCLEAR"].includes(v.verdict)) throw new Error("bad verdict");

  const is_floor_plan =
    v.verdict === "CONFIRMED" ? "true" : v.verdict === "FALSE_PASS" ? "false" : "unclear";
  const row = [
    v.permit,
    v.doc_id,
    v.page,
    v.verdict,
    is_floor_plan,
    v.reason ?? "",
    "nick",
    new Date().toISOString(),
  ];
  const line = row.map(csvField).join(",") + "\n";
  const p = path.join(DATA_ROOT, PATHS.eyeballVerdicts);
  const header = fs.readFileSync(p, "utf8").slice(0, 200).split("\n")[0];
  if (header.split(",").join(",") !== COLUMNS.join(",")) {
    throw new Error(`eyeball_verdicts.csv header changed — expected ${COLUMNS.join(",")}, got ${header}`);
  }
  fs.appendFileSync(p, line, "utf8");
}
