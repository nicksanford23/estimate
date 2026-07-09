// Per-project Takeoff Guide data. The narrative (estimator steps, our-steps)
// is templated in the guide page; this holds the project-specific facts.
// New capability filled by AI reading the finish schedule -> material buckets.

export type MaterialBucket = {
  type: string;
  codes: string[];
  unit: "SF" | "SY" | "LF" | "EA";
  quantity?: string;
  rooms: string;
  product: string;
};

export type RoomAction =
  | "auto_quantity"
  | "geometry_review"
  | "open_zone_split"
  | "vision_correct_or_redraw";

export type Room = {
  num: number;
  name: string;
  material: string;
  code: string;
  action?: RoomAction;
  sfNote?: string;
};

export type AutomationRow = {
  step: string;
  pipeline: string;
  status: "ok" | "warn" | "pend" | "bad";
  note: string;
};

export type Guide = {
  permit: string;
  docId: number; // the labeled combined set
  rooms: Room[];
  planSet: { docName: string; totalPages: number; flooringPages: number; specPages: number };
  scale: string;
  finishPlanPage: number;
  floorPlanPage: number;
  materials: MaterialBucket[];
  // custom overlays we generated (served from /public/guide/<permit>/…)
  overlays?: { src: string; label: string }[];
  // per-permit findings + how they'd adjust the approach (shown as sections)
  findings?: string[];
  adjustments?: string[];
  // per-permit automation status; falls back to the bank template if absent
  automation?: AutomationRow[];
  takeoff?: {
    netFloorSf: number;
    branchGrossSf: number;
    note: string;
  };
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
      { num: 101, name: "Vestibule", material: "Ceramic tile", code: "CT-1", action: "vision_correct_or_redraw", sfNote: "fragment; vision/redraw" },
      { num: 102, name: "Lobby", material: "Ceramic tile", code: "CT-1", action: "open_zone_split", sfNote: "front open zone" },
      { num: 103, name: "Tellers", material: "Carpet", code: "CP-2", action: "open_zone_split", sfNote: "front open zone" },
      { num: 104, name: "Workroom", material: "Carpet", code: "CP-1", action: "auto_quantity", sfNote: "164 SF validated" },
      { num: 105, name: "Self-Service", material: "Carpet", code: "CP-1", action: "open_zone_split", sfNote: "front open zone" },
      { num: 106, name: "Office", material: "Carpet", code: "CP-1", action: "auto_quantity", sfNote: "119 SF validated" },
      { num: 107, name: "Office", material: "Carpet", code: "CP-1", action: "auto_quantity", sfNote: "125 SF validated" },
      { num: 108, name: "Conference", material: "Carpet", code: "CP-1", action: "auto_quantity", sfNote: "214 SF validated" },
      { num: 109, name: "Office", material: "Carpet", code: "CP-1", action: "geometry_review", sfNote: "125 vs 100 SF" },
      { num: 110, name: "Copy/Fax", material: "Carpet", code: "CP-2", action: "open_zone_split", sfNote: "back open zone" },
      { num: 111, name: "Mortgage", material: "Carpet", code: "CP-2", action: "open_zone_split", sfNote: "back open zone" },
      { num: 112, name: "Vestibule", material: "Ceramic tile", code: "CT-1", action: "auto_quantity", sfNote: "78 SF validated" },
      { num: 113, name: "Break Room", material: "Resilient", code: "RF-1", action: "auto_quantity", sfNote: "111 SF validated" },
      { num: 114, name: "Corridor", material: "Carpet", code: "CP-2", action: "geometry_review", sfNote: "47 vs 37 SF" },
      { num: 115, name: "Men", material: "Resilient", code: "RF-1", action: "auto_quantity", sfNote: "52 SF validated" },
      { num: 116, name: "Women", material: "Resilient", code: "RF-1", action: "auto_quantity", sfNote: "54 SF validated" },
      { num: 117, name: "Elect/Data", material: "Carpet", code: "CP-2", action: "auto_quantity", sfNote: "37 SF validated" },
      { num: 118, name: "Jan", material: "Resilient", code: "RF-1", action: "auto_quantity", sfNote: "23 SF validated" },
    ],
    planSet: { docName: "Approved Set Plans 14-11290.pdf", totalPages: 75, flooringPages: 6, specPages: 2 },
    scale: '1/4" = 1\'-0"',
    finishPlanPage: 42,
    floorPlanPage: 3,
    materials: [
      { type: "Carpet", codes: ["CP-1", "CP-2"], unit: "SY", quantity: "2,058 SF / 229 SY",
        rooms: "Offices, Conference, Tellers, Self-Service, Copy/Fax, Mortgage, Corridor, Workroom, Elect/Data",
        product: 'Fortune Contract "Piece of Cake" / Patcraft "Headlines II", 12 ft rolls' },
      { type: "Ceramic tile", codes: ["CT-1"], unit: "SF", quantity: "455 SF",
        rooms: "Lobby and Vestibules",
        product: 'Ceramic Technics "Cooperative Iron Ore", 16×24, Sable Brown grout' },
      { type: "Resilient tile", codes: ["RF-1"], unit: "SF", quantity: "242 SF",
        rooms: "Break Room, Men, Women, Jan",
        product: 'Centiva "Riverrock", 18×18 tile' },
      { type: "Rubber base", codes: ["RB-1"], unit: "LF", quantity: "691 LF",
        rooms: "Perimeter of nearly every room",
        product: 'Johnsonite 4″ cove base, Brown' },
      { type: "Wood base", codes: ["WB-1"], unit: "LF", quantity: "129 LF",
        rooms: "Select areas (Self-Service, Conference)",
        product: "Randall Bros RB620, paint grade" },
      { type: "Transition strips", codes: ["TS-1", "TS-2"], unit: "EA", quantity: "~7 locations",
        rooms: "At every material change (tile↔carpet, resilient↔carpet)",
        product: "Schluter Reno-TK-AE / Johnsonite CTA" },
    ],
    takeoff: {
      netFloorSf: 2755,
      branchGrossSf: 3190,
      note: "Completed bank pass: 2,755 SF net vs 3,190 SF branch gross (-14%). Geometry layer alone found 2,719 SF; the final assembly uses geometry, finish splits, and review corrections.",
    },
    fit: {
      verdict: "partial",
      vector: true,
      scale: true,
      dimensions: true,
      geometryCloses: false,
      footprintFound: 2719,
      note: "Vector, scaled, richly dimensioned inputs. The right product read is not 'room model failed'; it is '10 enclosed rooms auto-quantity, 2 enclosed rooms need geometry review, 1 vestibule needs vision/redraw, and 5 open-plan rooms need finish-zone splitting.' The 7,090 SF permit value is the whole building; this guide takes off the 3,190 SF Business branch.",
    },
  },

  // ── Second building: office renovation, clean 2D wall layers. The method
  //    works end-to-end here (vision scale → layer geometry → vision room
  //    anchoring on a vectorized plan → finish material).
  "26-10321-RNVN": {
    permit: "26-10321-RNVN",
    docId: 9058456,
    rooms: [
      { num: 901, name: "Office", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "159 SF (geom)" },
      { num: 902, name: "Office", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "109 SF (geom)" },
      { num: 903, name: "Office", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "108 SF (geom)" },
      { num: 905, name: "Office", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "116 SF (geom)" },
      { num: 907, name: "Office", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "108 SF (geom)" },
      { num: 916, name: "Wellness", material: "LVT", code: "LVT", action: "auto_quantity", sfNote: "136 SF (geom)" },
      { num: 918, name: "Office", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "147 SF (geom)" },
      { num: 923, name: "Breakroom", material: "LVT", code: "LVT", action: "auto_quantity", sfNote: "249 SF (geom)" },
      { num: 931, name: "Waiting", material: "LVT", code: "LVT", action: "auto_quantity", sfNote: "192 SF (geom)" },
      { num: 933, name: "Workroom", material: "LVT", code: "LVT", action: "auto_quantity", sfNote: "102 SF (geom)" },
      { num: 934, name: "Supply", material: "LVT", code: "LVT", action: "auto_quantity", sfNote: "94 SF (geom)" },
      { num: 937, name: "File Room", material: "LVT", code: "LVT", action: "auto_quantity", sfNote: "185 SF (geom)" },
      { num: 941, name: "Conference", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "382 SF (geom)" },
      { num: 943, name: "Office", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "118 SF (geom)" },
      { num: 944, name: "Office", material: "Carpet", code: "C1", action: "auto_quantity", sfNote: "118 SF (geom)" },
      { num: 917, name: "Open Office", material: "Carpet", code: "C1", action: "open_zone_split", sfNote: "in open blob (~4,724 SF)" },
      { num: 936, name: "Open Office", material: "Carpet", code: "C1", action: "open_zone_split", sfNote: "in open blob (~2,652 SF)" },
      { num: 906, name: "Open Office", material: "Carpet", code: "C1", action: "open_zone_split", sfNote: "open plan, no walls" },
      { num: 940, name: "Training", material: "Carpet", code: "C1", action: "open_zone_split", sfNote: "open plan" },
      { num: 921, name: "Director's Office", material: "Carpet", code: "C2", action: "geometry_review", sfNote: "did not close cleanly" },
    ],
    planSet: { docName: "100 CD_ARCH 04-06-26.pdf", totalPages: 42, flooringPages: 15, specPages: 0 },
    scale: '1/8" = 1\'-0" (read by vision, not regex)',
    finishPlanPage: 33,
    floorPlanPage: 18,
    materials: [
      { type: "Carpet", codes: ["C1", "C2"], unit: "SF", quantity: "1,365 SF (anchored rooms)",
        rooms: "Private offices + Conference; open-office areas also carpet (not room-split)",
        product: 'Shaw Contract "Diffuse Tile" 59575, 24×24, ashlar install; C2 = Director\'s office' },
      { type: "LVT", codes: ["LVT"], unit: "SF", quantity: "958 SF (anchored rooms)",
        rooms: "Wellness, Breakroom, Waiting, Workroom, Supply, File Room (service/wet rooms)",
        product: 'Tarkett "ID Latitude Abstract", 18×18, Harbor 7566, 1/4-turn' },
      { type: "Rubber base", codes: ["B1"], unit: "LF", quantity: "not yet measured",
        rooms: "Perimeter of nearly every room",
        product: 'Roppe 4" cove base, Pewter 178' },
    ],
    overlays: [
      { src: "/guide/26-10321/takeoff-final.jpg", label: "Final anchored takeoff — 15 rooms, colored by material (blue=carpet, orange=LVT), room# + SF" },
      { src: "/guide/26-10321/all-polygons.jpg", label: "All 63 geometry polygons — private rooms close; open-office core merges into two blobs" },
      { src: "/guide/26-10321/room-anchoring.jpg", label: "Vision room-anchoring — outlined crops let one vision pass read room numbers off a vectorized plan" },
    ],
    takeoff: {
      netFloorSf: 2323,
      branchGrossSf: 9700,
      note: "15 private rooms auto-quantified: 2,323 SF (Carpet 1,365 + LVT 958). Full-floor ≈ 2,323 anchored + ~7,400 open-office carpet (not room-split) ≈ ~9,700 SF. No area schedule on this permit, so per-room SF is geometry-only (no independent truth).",
    },
    findings: [
      "Scale was read by VISION off the trimmed sheet (1/8\" = 1'-0\"); the regex scale-parser missed it because the page has only 98 text tokens and the scale note isn't in a matchable form. On a single trimmed page, look — don't scrape.",
      "Room numbers (901, 902…) are VECTORIZED (drawn as curves, not text) — text-anchoring is impossible. Vision anchoring via outlined-crop montage read all 15 in one pass.",
      "Geometry nails hard-walled private rooms but the open-office/cubicle core merges into two large blobs (~4,724 + ~2,652 SF) — no enclosing walls, only furniture. That's a real product limit, not a bug.",
      "Material split (offices→carpet, service/wet→LVT) matched the finish-key logic exactly — an independent check that the room anchoring is correct.",
    ],
    adjustments: [
      "Lock the room-anchoring method into a reusable script: outline-only crops (no fill — fill hides the room bubble; no-fill is ambiguous) tiled into one montage, one vision read.",
      "Open-plan areas need finish-zone/gross-SF treatment, not more wall closure — same conclusion as the bank's open zones.",
    ],
    automation: [
      { step: "Get plans", pipeline: "Download from R2", status: "ok", note: "done" },
      { step: "Read finish materials", pipeline: "A5.4 finish plan hex tags + legend", status: "ok", note: "Carpet C1 / LVT read" },
      { step: "Set scale", pipeline: "Vision off trimmed page", status: "ok", note: "1/8\"=1'-0\"" },
      { step: "Trace enclosed rooms", pipeline: "NEW/EXIST WALL layer → polygonize", status: "warn", note: "15 private auto; open core merges" },
      { step: "Anchor room numbers", pipeline: "Vision outlined-crop montage", status: "ok", note: "15 rooms named on vectorized plan" },
      { step: "Split open finish zones", pipeline: "finish-boundary / gross-SF", status: "warn", note: "917, 936, 906 open office" },
      { step: "Sum by material", pipeline: "anchored rooms × finish map", status: "ok", note: "Carpet 1,365 + LVT 958 SF" },
      { step: "Base / transitions", pipeline: "perimeter + material-change pass", status: "pend", note: "not measured" },
      { step: "Waste / prep / price", pipeline: "—", status: "pend", note: "not built" },
    ],
    fit: {
      verdict: "partial",
      vector: true,
      scale: true,
      dimensions: false,
      geometryCloses: false,
      footprintFound: 18462,
      note: "Clean 2D wall layers → geometry closes the hard-walled private rooms cleanly and vision anchors their numbers on an otherwise text-less (vectorized) plan. The open-office core is the honest limit: no walls to polygonize. Product read: 15 rooms auto-quantity, open zones need finish-splitting. This is the second building the full method works on.",
    },
  },

  // ── Third building: "layered" by segment count, but the wall layer is a 3D
  //    solid that will not polygonize. The key negative result for the plan.
  "25-33341-NEWC": {
    permit: "25-33341-NEWC",
    docId: 8640130,
    rooms: [
      { num: 101, name: "Lobby / Exhibit", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "geometry unusable" },
      { num: 103, name: "Shop Fab", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "big lab, did not close" },
      { num: 104, name: "Foam Lab 1", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "big lab, did not close" },
      { num: 105, name: "Foam Lab 2", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "big lab, did not close" },
      { num: 106, name: "Foam Lab 3", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "big lab, did not close" },
      { num: 107, name: "Foam Lab 4", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "big lab, did not close" },
      { num: 108, name: "Wet Lab", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "big lab, did not close" },
      { num: 109, name: "Project Area", material: "Concrete", code: "CN-2", action: "vision_correct_or_redraw", sfNote: "exterior conc. finish" },
      { num: 114, name: "Shower", material: "Tile", code: "FT-1", action: "geometry_review", sfNote: "core room; small polys closed" },
      { num: 110, name: "Female RR", material: "Sealed concrete", code: "CN-1", action: "geometry_review", sfNote: "core room closed" },
      { num: 111, name: "Male RR", material: "Sealed concrete", code: "CN-1", action: "geometry_review", sfNote: "core room closed" },
      { num: 118, name: "Event", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "did not close" },
      { num: 122, name: "Corridor", material: "Sealed concrete", code: "CN-1", action: "vision_correct_or_redraw", sfNote: "did not close" },
    ],
    planSet: { docName: "4480 Dauphine Street ARCH_ Issued for Permit_251024 (RCC).pdf", totalPages: 36, flooringPages: 5, specPages: 1 },
    scale: '3/32" = 1\'-0" (read by vision; not a 1/N scale, regex mis-parses)',
    finishPlanPage: 35,
    floorPlanPage: 11,
    materials: [
      { type: "Sealed concrete", codes: ["CN-1"], unit: "SF", quantity: "not measurable (geometry failed)",
        rooms: "Nearly every room — labs, event, lobby, corridors, most cores",
        product: "Floated concrete diamond finish with matte sealant" },
      { type: "Concrete", codes: ["CN-2"], unit: "SF", quantity: "not measurable",
        rooms: "Project Area (exterior concrete finish)",
        product: "Exterior concrete finish" },
      { type: "Tile", codes: ["FT-1"], unit: "SF", quantity: "not measurable",
        rooms: "Showers / wet rooms",
        product: 'Daltile Keystones porcelain mosaic, Artic White D617 2×2' },
      { type: "Vinyl / tile base", codes: ["VB-1", "VB-2", "WT-3"], unit: "LF", quantity: "not measured",
        rooms: "Perimeter; tile cove base in wet rooms",
        product: "Johnsonite millwork base M25; tile cove in wet areas" },
    ],
    overlays: [
      { src: "/guide/25-33341/geometry-fail.jpg", label: "Geometry FAILS: only small core rooms fill green; the big labs (Wet Lab, Foam Labs) never close — the .3D wall layer fragments into 16k segments" },
    ],
    findings: [
      "Wall layer is `A - Walls - Exterior.3D` — a 3D SOLID representation, not clean 2D centerlines. 16,264 raw segments; even with all filters off the largest polygon is only 263 SF, on a ~10k+ SF building.",
      "Exterior walls ARE captured (87–88 ft segments) but don't node at corners — the junction geometry is in the tiny sub-segments the length filter drops, and interior partitions meet mid-span of exterior walls with no shared vertex. So cycles form only for the tightly-drawn small core rooms (~2,055 SF).",
      "Parameter sweep did not fix it: snap 0.0025→0.005, door 4.5→6 ft, self-snap 1–2 ft. Self-snap collapsed the network to 0 rooms. This is a bad wall representation, not a tolerance problem.",
      "The finish schedule (A-603) is a real per-room table but has NO area column → MATERIAL_ONLY, not TRUTH_AREA. Floors are almost all CN-1 sealed concrete: flooring scope here is sealing/polishing, not carpet/resilient install.",
      "THE FINDING: \"layered\" (by segment count) is NOT the same as \"geometry-usable.\" Of the 2 LAYERED READY permits, only 26-10321 is actually usable.",
    ],
    adjustments: [
      "Add a polygonize-QUALITY gate to segment_ready.py: score by closeability (largest room ≥150 SF AND ≥3 rooms 40–2000 SF), not by segment count. Re-score all 23 READY permits — the usable-layered pile likely shrinks.",
      "Re-tier this permit to MODEL_TARGET (needs the ML wall-model for area) + MATERIAL_ONLY (finish read is good).",
      "The ML vector-first wall-model matters MORE, not less: clean-2D layered files are rarer than the raw layered count implied, so a model that learns walls from any representation (incl. .3D solids) is the durable path.",
    ],
    automation: [
      { step: "Get plans", pipeline: "Download from R2", status: "ok", note: "done" },
      { step: "Read finish schedule", pipeline: "A-603 table (real, no area column)", status: "ok", note: "materials read; MATERIAL_ONLY" },
      { step: "Set scale", pipeline: "Vision off trimmed page", status: "ok", note: "3/32\"=1'-0\"" },
      { step: "Trace enclosed rooms", pipeline: ".3D solid layer → polygonize", status: "bad", note: "FAILS: 16k fragments, max poly 263 SF" },
      { step: "Anchor room numbers", pipeline: "Vision montage", status: "pend", note: "blocked — no geometry to anchor" },
      { step: "Split open finish zones", pipeline: "—", status: "pend", note: "blocked" },
      { step: "Sum by material", pipeline: "geometry × finish map", status: "bad", note: "no usable area from geometry" },
      { step: "Waste / prep / price", pipeline: "—", status: "pend", note: "not built" },
    ],
    fit: {
      verdict: "not_suitable",
      vector: true,
      scale: true,
      dimensions: true,
      geometryCloses: false,
      footprintFound: 2055,
      note: "Vector, scaled, dimensioned — and STILL not automatable, because the wall layer is a 3D solid ('.3D') that fragments into 16k segments and won't polygonize. Only ~2,055 SF of small core rooms close on a ~10k+ SF building. This is the key negative result: 'layered' by segment count is not 'geometry-usable.' Route: MODEL_TARGET for the future wall-model + MATERIAL_ONLY for the (good) finish read.",
    },
  },
};
