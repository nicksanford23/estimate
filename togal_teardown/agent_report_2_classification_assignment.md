# Agent report 2/3 — classification & material assignment (frames 2.29.14–2.30.11 PM)

*Background Sonnet-fleet report, 2026-07-11, chunk 2 (16 frames, video
time 2:40→3:27). Blind: produced without GPT's analysis or the transcript.*

## Meta-context
Frames of the Togal marketing demo "4.5 min Flooring Takeoff in Togal.AI"
(4:54 total), chapter "**Classification and assignment**". Browser is a
Togal insider's (bookmarks: ADP, "Togal vs PlanSwift/Bluebeam/Onscreen",
Stripe Dashboard, Usage By Org) — best-case footage. Sheet: "1 FLOOR PLAN
LEVELS 9-15 (HOTEL UNITS)", page 14/16, scale 1/8"=1'0".

## Frame-by-frame (deltas)

- **F1 2:40** — post-detection, whole plate colorized per class. Tree root
  "Togal areas 693" with rows (name/count/area): Footprint 1 — 17,735 SF;
  GIA 180 — 17,358; Gross 182 — 17,752; Doors 147 — 320; Corridor 1 —
  1,511; Hotel Room 17 — 5,171; Living Area 4 — 1,096; Stairs 2 — 420;
  Lobby Elevator 1 — 171; Bedroom 20 — 2,783; Shafts 85 — 1,351; Utility
  3 — 342; Bathroom 23 — 1,361; Elevator 4 — 307; Closet 22 — 932;
  Balcony 1 — 78; (dimmed) Togal lines 1,119; Togal counts 352. Green
  popup "How would you rate this take-off? [Great/OK/Poor]".
- **F2 2:44** — row hover (Corridor) → canvas highlight sync.
- **F3–F4** — `/library` panel: tabs **Organization | Private**; catalogs:
  Blain's Paint + Waterproofing, Frame Construction, Lumber & Framing,
  Roofing, Plumbing, Drywall, **Flooring**, Demo.
- **F5 3:03** — Flooring catalog expanded: Misc Flooring (Rubber, Quartz,
  Polished Concrete, Hardwood); Carpet (Carpet 1/2/3); Tile (**LVT Type 1
  (10x10), Type 2 (6x12), Type 3 (14x14)**); "+ Add Classification". They
  file LVT under "Tile"; names carry plank/tile sizes.
- **F6–F7 3:05–3:09** — drag-and-drop import of Carpet/Tile/Polished
  Concrete groups into the project tree (~6s).
- **F8** — library closed; project tree now has empty material folders.
- **F9 3:19** — bulk select Hotel Room (17) + Living Area (4); only those
  polygons highlighted; chip "**6270 SF / 1989 FT**" (area + perimeter of
  selection). Right-click: search, "Living Area >", Create and assign,
  Copy, Duplicate, Delete, green **Auto Classify**. Transform bar: Group
  ⌘G, Flip H ⌘H, Flip V ⌘Y, Combine ⌘B, Rotate.
- **F10 3:22** — assigned: 21 polygons recolored to Tile; root 693→672;
  Hotel Room/Living Area rows EMPTIED; "Tile 21" appears. Assignment
  **moves** polygons out of the room-class bucket — room identity consumed.
- **F12 3:27** — Bedroom (20) selected; chip "2782 SF / 1019 FT" (tree
  says 2,783 — agree to rounding).
- **F13–F15** — right-click → Tile > LVT Type 1 (10x10): 20 bedrooms
  assigned in 2 clicks; root 672→652; "Tile 41". Cumulative: 41 rooms
  ≈ 9,050 SF assigned in ~12s of video.
- **F16** — cursor drifts toward Bathroom/Elevator rows (next targets).

## Synthesis

### What this captures
The manual mapping chapter: AI already produced 693 area polygons + 1,119
lines + ~352 counts on one hotel plate (17,735 SF footprint), classified
into ~16 semantic classes. User imports a flooring material library,
bulk-selects rooms BY CLASS, right-click assigns to products. ~47s covers
rating prompt → library import → 41 rooms (~9,050 SF) → LVT. Per-class
bulk assignment makes room count nearly irrelevant to labor. Suspicious:
**Shafts 85** on one floor (over-segmentation of poché/cavities); GIA 180
vs Gross 182 fragment counts.

### UI/UX worth copying
- **Area + perimeter chip on every selection** — perimeter IS wall-base
  LF; for flooring the highest-value secondary number. Surface both,
  always.
- Class-tree ↔ canvas sync; per-row eye toggles; Hide all / Select all.
- **Bulk assign by semantic class** (select "Bedroom (20)" → 2 clicks to a
  product). Room-class detection turns 693 polygons into ~10 decisions.
- Right-click menu with search + Recently Used + Create-and-assign.
- Material library with Organization/Private tabs, drag-into-project.
- Post-run rating prompt = labeled-outcome stream. Build ours day one.
- "Re-Togal" — detection treated as cheap/idempotent re-run.
- Product naming with dimensions ("LVT Type 2 (6x12)") — estimators think
  in SKUs and sizes.

### Weaknesses (flooring wedge)
- **Materials are 100% manual.** Nothing reads the finish schedule. Our
  finish_schedule class + schedule-reader can auto-map room → finish → SF,
  collapsing this whole chapter to zero clicks. That's the wedge.
- **Assignment destroys the room dimension** (class rows empty when
  assigned). Keep the room-type × material matrix intact — that's how
  flooring bids are checked and change orders priced.
- Generic taxonomy noise (85 shafts, doors-area, 3 gross rollups, 1,119
  lines, 352 counts) clutters a flooring takeoff.
- No deductions (casework/tubs), no waste factors, no seams/roll
  direction, no transitions at the 147 detected doors.
- Clean vector-ish hotel plan = best case; no evidence on scanned/noisy
  sheets (our corpus).

### Implications for our data/models NOW
- Treat boundary detection and **room-type labeling as one task**; their
  observed class set is a reasonable starter taxonomy (Corridor, Guest
  Room, Living Area, Bedroom, Bathroom, Closet, Utility, Stairs, Elevator,
  Shaft, Balcony, Lobby).
- **Emit perimeter LF per room now** in sf-extraction — it's free.
- Doors as objects (transitions + closure points) — worth a class later.
- Emit rollup sanity invariants (Σ rooms ≈ GIA ≈ footprint − walls).
- Instrument every AI output with a 3-level rating.
- Prioritize schedule extraction + room-name↔schedule join — Togal shows
  zero capability there.

### Open questions for the transcript
- Detection latency for the "Togal" click → 693 polygons.
- What **Auto Classify** does (auto-material? if so our wedge narrows).
- Any stated error rates; what "Compare" compares.
- Export/Breakdown formats; what Togal.CHAT does here.
- Pricing/seats; raster-sheet performance.
- "Togal vs PlanSwift/Bluebeam/Onscreen" bookmarks → published
  head-to-heads worth mining.
