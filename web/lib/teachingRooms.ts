import fs from "fs";
import path from "path";
import { SMOKE } from "@/lib/lab";

export interface TeachingBoundarySide {
  id: string;
  human_name: string;
  draft_meaning: string;
  draft_claim: string;
  measurement_in: number;
  measurement_math: string;
  evidence_status: string;
  why_not_confirmed: string;
  current_conclusion: string;
  next_action: string;
}

export interface TeachingRoom {
  schema_version: string;
  project: string;
  address: string;
  room: {
    code: string;
    name: string;
    sheet: string;
    printed_area_sf_diagnostic_only: number;
    draft_area_sf_diagnostic_only: number;
  };
  status: string;
  status_explanation: string;
  training_eligible: boolean;
  source_images: {
    original_crop: string;
    draft_overlay: string;
    numbered_draft: string;
    measurement_diagnostic: string;
  };
  scale: {
    note: string;
    pdf_points_per_real_foot: number;
    real_inches_per_pdf_point: number;
    machine_status: string;
    qualified_reviewer_status: string;
  };
  plain_goal: string;
  draft: {
    source: string;
    confidence: number;
    shape: string;
    warning: string;
  };
  boundary_sides: TeachingBoundarySide[];
  machine_history: { stage: string; result: string }[];
  required_next_steps: string[];
}

export function loadTeachingRoom(permit: string, room: string): TeachingRoom | null {
  if (!/^[A-Za-z0-9-]+$/.test(permit) || !/^[A-Za-z0-9]+$/.test(room)) return null;
  const file = path.join(SMOKE, permit, "teaching", `room_${room}_v1.json`);
  if (!fs.existsSync(file)) return null;
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as TeachingRoom;
    if (parsed.project !== permit || parsed.room?.code !== room || !Array.isArray(parsed.boundary_sides)) return null;
    return parsed;
  } catch {
    return null;
  }
}

