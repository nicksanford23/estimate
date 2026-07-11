// Client-safe: no pg import. Split out of v2Db.ts so client components
// (V2PageCard) don't drag `pg` into the browser bundle.
export const TAXONOMY_V2 = [
  "floor_plan",
  "finish_plan",
  "finish_schedule",
  "demo_plan",
  "reflected_ceiling",
  "furniture_plan",
  "site_plan",
  "elevation_section",
  "detail",
  "schedule_other",
  "structural",
  "mep",
  "life_safety",
  "cover_index",
  "specs_notes",
  "other",
] as const;
