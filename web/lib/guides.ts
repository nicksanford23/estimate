// Per-project Takeoff Guide data. The narrative (estimator steps, our-steps)
// is templated in the guide page; this holds the project-specific facts.
// New capability filled by AI reading the finish schedule -> material buckets.

export type MaterialBucket = {
  type: string;
  codes: string[];
  unit: "SF" | "SY" | "LF";
  rooms: string;
  product: string;
};

export type Room = { num: number; name: string; material: string; code: string };

export type Guide = {
  permit: string;
  docId: number; // the labeled combined set
  rooms: Room[];
  planSet: { docName: string; totalPages: number; flooringPages: number; specPages: number };
  scale: string;
  finishPlanPage: number;
  floorPlanPage: number;
  materials: MaterialBucket[];
  fit: {
    verdict: "good" | "partial" | "not_suitable";
    vector: boolean;
    scale: boolean;
    dimensions: boolean;
    geometryCloses: boolean;
    footprintFound: number | null;
    note: string;
  };
};

export const GUIDES: Record<string, Guide> = {
  "14-11290-NEWC": {
    permit: "14-11290-NEWC",
    docId: 1494156,
    rooms: [
      { num: 101, name: "Vestibule", material: "Ceramic tile", code: "CT-1" },
      { num: 102, name: "Lobby", material: "Ceramic tile", code: "CT-1" },
      { num: 103, name: "Tellers", material: "Carpet", code: "CP-2" },
      { num: 104, name: "Workroom", material: "Carpet", code: "CP-1" },
      { num: 105, name: "Self-Service", material: "Carpet", code: "CP-1" },
      { num: 106, name: "Office", material: "Carpet", code: "CP-1" },
      { num: 107, name: "Office", material: "Carpet", code: "CP-1" },
      { num: 108, name: "Conference", material: "Carpet", code: "CP-1" },
      { num: 109, name: "Office", material: "Carpet", code: "CP-1" },
      { num: 110, name: "Copy/Fax", material: "Carpet", code: "CP-2" },
      { num: 111, name: "Mortgage", material: "Carpet", code: "CP-2" },
      { num: 112, name: "Vestibule", material: "Ceramic tile", code: "CT-1" },
      { num: 113, name: "Break Room", material: "Resilient", code: "RF-1" },
      { num: 114, name: "Corridor", material: "Carpet", code: "CP-2" },
      { num: 115, name: "Men", material: "Resilient", code: "RF-1" },
      { num: 116, name: "Women", material: "Resilient", code: "RF-1" },
      { num: 117, name: "Elect/Data", material: "Carpet", code: "CP-2" },
      { num: 118, name: "Jan", material: "Resilient", code: "RF-1" },
    ],
    planSet: { docName: "Approved Set Plans 14-11290.pdf", totalPages: 75, flooringPages: 6, specPages: 2 },
    scale: '1/4" = 1\'-0"',
    finishPlanPage: 42,
    floorPlanPage: 2,
    materials: [
      { type: "Carpet", codes: ["CP-1", "CP-2", "CP-3"], unit: "SY",
        rooms: "Offices, Conference, Self-Service, Copy/Fax, Mortgage, Corridor, Workroom",
        product: 'Fortune Contract "Piece of Cake" / Patcraft "Headlines II" / Fortune "Forecast", 12′ rolls' },
      { type: "Ceramic tile", codes: ["CT-1"], unit: "SF",
        rooms: "Lobby, Vestibules, Teller area (the public floor)",
        product: 'Ceramic Technics "Cooperative Iron Ore", 16×24, Sable Brown grout' },
      { type: "Resilient tile", codes: ["RF-1"], unit: "SF",
        rooms: "Restrooms (Men/Women), Break Room",
        product: 'Centiva "Riverrock", 18×18 tile' },
      { type: "Rubber base", codes: ["RB-1"], unit: "LF",
        rooms: "Perimeter of nearly every room",
        product: 'Johnsonite 4″ cove base, Brown' },
      { type: "Wood base", codes: ["WB-1"], unit: "LF",
        rooms: "Select areas (Self-Service, Conference)",
        product: "Randall Bros RB620, paint grade" },
      { type: "Transition strips", codes: ["TS-1", "TS-2"], unit: "LF",
        rooms: "At every material change (tile↔carpet, resilient↔carpet)",
        product: "Schluter Reno-TK-AE / Johnsonite CTA" },
    ],
    fit: {
      verdict: "partial",
      vector: true,
      scale: true,
      dimensions: true,
      geometryCloses: false,
      footprintFound: 364,
      note: "Vector, scaled, and richly dimensioned — ideal inputs. The only failure is closing walls into rooms (footprint came out ~364 sq ft vs 7,090 recorded).",
    },
  },
};
