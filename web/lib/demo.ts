import fs from "fs";
import path from "path";
import type { DemoData } from "@/lib/demoTypes";

// Static demo data loader (server-only). Data itself is written by
// scripts/export_demo_json.py into web/public/demo/<permit>.json, in the
// PRODUCT-shaped schema described in lib/demoTypes.ts -- designed like a
// future DB table so swapping this loader for a real upload pipeline later
// doesn't change the component shape.

export function loadDemo(permit: string): DemoData | null {
  const p = path.join(process.cwd(), "public", "demo", `${permit}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

export { DEMO_PERMITS } from "@/lib/demoTypes";
