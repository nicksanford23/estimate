// Pure types + constants for the Review Screen demo data (no Node built-ins
// here -- this file is imported by CLIENT components, unlike lib/demo.ts
// which reads from disk and must stay server-only).

export type Evidence = {
  schedule_row?: string;
  printed_dim?: string;
  why_flagged?: string;
};

export type RoomStatus = "accepted" | "review" | "open" | "draw_needed";

export type DemoRoom = {
  id: string;
  name: string;
  polygon: [number, number][] | null; // pixel coords in the page image's own space, or null = no plan geometry yet
  sf: number | null;
  status: RoomStatus;
  material: string | null;
  evidence: Evidence;
  sf_source?: "schedule"; // present when sf comes from the finish schedule, not measured geometry
  // true = closed geometry with NO room-number anchor. Not a peer of real
  // rooms: excluded from Verified/Estimated totals and from the review queue
  // proper (shown as one collapsed group row + de-emphasized on canvas).
  unlabeled?: boolean;
};

export type DemoPage = {
  id: string;
  image: string;
  image_width: number;
  image_height: number;
  feet_per_pixel: number;
  rooms: DemoRoom[];
};

export type DemoProject = {
  id: string;
  name: string;
  address?: string | null;
};

export type DemoData = {
  project: DemoProject;
  pages: DemoPage[];
};

export const DEMO_PERMITS = ["14-11290-NEWC", "26-10321-RNVN", "24-06748-RNVS"];

export const STATUS_LABEL: Record<RoomStatus, string> = {
  accepted: "Accepted",
  review: "Needs review",
  open: "Open zone",
  draw_needed: "Draw needed",
};
