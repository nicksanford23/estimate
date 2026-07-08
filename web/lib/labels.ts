// Client-safe label maps (no server imports).
export const KEEP_CATS = new Set([
  "floor_plan",
  "finish_plan",
  "finish_schedule",
  "demo_plan",
]);

export const CAT_LABEL: Record<string, string> = {
  floor_plan: "Floor plan",
  finish_plan: "Finish plan",
  finish_schedule: "Finish schedule",
  demo_plan: "Demo plan",
  reflected_ceiling: "Reflected ceiling",
  furniture_plan: "Furniture",
  mep: "MEP",
  structural: "Structural",
  elevation_section: "Elev/section",
  detail: "Detail",
  specs_notes: "Specs/notes",
  schedule_other: "Schedule (other)",
  cover_index: "Cover/index",
  site_plan: "Site plan",
  life_safety: "Life safety",
  other: "Other",
};
