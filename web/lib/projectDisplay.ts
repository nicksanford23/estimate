// Shared project display-identity resolution
// (V2_PRODUCT_REBUILD_PLAN_V1.md §4.1). A project is shown by address/name,
// never primarily by permit number. Priority:
//   1. user_project_name (not stored yet)
//   2. normalized property address
//   3. short project/development description
//   4. permit number (last-resort fallback only)
// Changing display identity never changes internal permit/document keys.

export type ProjectDisplayInput = {
  permit_num: string;
  building_name?: string | null;
  address_raw?: string | null;
  city_description?: string | null;
};

// City descriptions ramble ("...as per plans, HDLC C/A #..."); keep the lead clause.
export function shortDescription(d: string | null | undefined): string {
  if (!d) return "";
  const cut = d.split(/ as per | per plans|, HDLC|, BZA/i)[0];
  return cut.length > 110 ? cut.slice(0, 107) + "…" : cut;
}

export function displayTitle(p: ProjectDisplayInput): string {
  return (
    (p.address_raw && p.address_raw.trim()) ||
    (p.building_name && p.building_name.trim()) ||
    shortDescription(p.city_description) ||
    p.permit_num
  );
}
