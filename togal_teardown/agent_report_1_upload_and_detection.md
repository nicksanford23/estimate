# Agent report 1/3 — upload, ingest, detection (frames: named files + 2.20–2.28 PM)

*Background Sonnet-fleet report, 2026-07-11, from togal_teardown/screenshots/
chunk 1 (21 frames). Part of the blind teardown: produced WITHOUT seeing
GPT's analysis or the video transcript.*

## Meta-context
Frames are from a YouTube demo titled **"4.5 min Flooring Takeoff in
Togal.AI"** (duration 4:54), user "Anthony … togal ai", project "Demo
Project / Residential", URL `www-prod.togal.ai/editor/<uuid>/page/<uuid>/quantities`.
Editor chrome: page nav ("14 of 16"), buttons **Re-Togal** (green),
**Togal.CHAT**, tabs **Quantities | Breakdown | Export | Compare | Export
PDF**. Left toolbar ~15 icons (select, pan, shapes, measure, magic-detect,
undo/redo, zoom, layers, search). Persistent green chip bottom-left:
**"Scale: 1/8" = 1'0""**. Right panel: layer tree with per-row counts +
quantities. Floating widget: **"How would you rate this take-off?
[Great / OK / Poor]"**. Demo plan: residential apartment tower floor plate
("FLOOR PLAN LEVELS 9-15", sheet A.105), rooms UNIT A1–A6/B1–B3, MECH.,
ELEC./IDF, FIRE+SERVICE LOBBY, STORAGE.

## Per-frame records

1. **20sec.png — Project library / drawing-set manager.** "Anthony's
   Project set **513** pages", auto-grouped: Electrical 99, Interior Design
   15, Mechanical 26, Structural 21, Architectural 52, **Autonaming 305**,
   Roof Plans 3, Exterior Elevations 21; "By Type 3"; "Specs". Thumbnails
   carry **auto-extracted sheet titles + numbers** as blue chips
   ("ELECTRICAL LEGEND / E-001", "FIRST FLOOR POWER PLAN – OVERALL /
   E-101", …); two cards still show raw filenames. Green status dots.
   → discipline classification AND sheet-title/number extraction at upload.
2. **30sec.png — Togal.CHAT "Ask the project".** Doc-grounded RAG Q&A.
   Flooring general notes quoted (ceramic tile joints, shop drawings) with
   a clickable page citation ("COSA-Ella_DD 100_-_Drawings (1) 2-155").
   On "approved suppliers for flooring": honest miss — says docs may not
   specify, suggests spec manual, offers another search.
3. **50.png — Togal.CHAT flooring scope-of-work extraction.** Returns a
   product-level list: PT-1 Daltile Beige RK11 24"x48" (restrooms); CP-1
   Interface Beaumont Range 107515 Fern 25cm×1m plank (second floor,
   Ashlar); CON-1/CON-2 sealed/finished concrete; LVT-1 Daltile AB23 Asher
   Bend Hearth 9"x7"; LVT-2 Daltile BL30 Bellant 36"x36"; LVT-3 Daltile
   White; VCT-1 Mannington 12"x12" (gym + storage); RT-1 rubber treads
   (stairs). NOTE: many entries end "**for unspecified areas**" — the chat
   never joins finish codes to room geometry/SF.
4. **95sec.png — Editor pre-detection.** Clean plan; red dashed rectangle
   marks the detected drawing extent; right panel empty.
5. **96sec.png — Feature-selection popover.** Tabs "All Features | Custom":
   checkbox tree **Togal areas** (Net, Gross, Footprint, GIA, Doors area),
   **Togal lines** (Wall centerline, Doors centerline, Wall Perimeter),
   **Togal counts**; green **Go**. → user scopes detections per run.
6. **1.46.png — "Togal in progress"** + progress bar; plan dimmed.
7. **1.48.png — "Preparing data"** spinner + onboarding tooltip ("Check out
   the other take-offs…"). Combined timing with 95sec/96sec ⇒
   **full-plate inference ≈ 10–15 seconds**.
8. **1.50.png — Detection results (the money frame).** Per-room net-area
   polygons fill the plate. Tree: **Togal areas 693** — Footprint 1 =
   17,735 SF; **Net area 183 = 15,524 SF**; Doors area 147 = 320 SF; Gross
   area 182 = 17,752 SF; GIA 180 = 17,358 SF. **Togal lines 1,119** — Doors
   centerline 147 = 522 FT; Wall centerline 788 = 3,796 FT; Wall Perimeter
   184 = 6,729 FT. **Togal counts 352** — Toilet 23, Sink 43, Bathtub 23,
   Dryer 1, Single Swing Door 129, Double Swing Door 1, Sliding Door 20,
   Double Bed 23, Small table 46, Cooktop 18, Sofa Multi 18, Living Table
   3, Tv/Monitor 4. → one pass yields areas + lines + object counts incl.
   furniture — generic all-trades detector.
9. **1.58.png — 1:57/4:54, chapter "Automatic takeoff generation".** Same
   results hi-res. Bookmarks bar: "Togal vs PlanSwift", "Togal vs
   Bluebeam", "Togal vs Onscreen…", "3-min demo", "Stripe Dashboard",
   "Usage By Org" → browser belongs to a Togal insider; this is their own
   curated best-case demo.
10. **cntrlA.png — Select-all (2:30).** Badge **"15525 SF / 6730 FT"**
    (live selection totals). Context bar: Group ⌘G, Flip H/V, Combine ⌘B,
    Rotate.
11–17. **2.20.57–2.26.39 PM.** Near-dup of 1.58; zoomed views: per-room
    polygon granularity, fills stop at wall faces, door openings visible as
    gaps, room-name text legible over fill; selection badges "300 SF /
    92 FT", corridor "1511 SF / 553 FT"; cursor hovers rating widget.
18. **2.28.15 PM — chapter "Classification and assignment".** Right-click
    menu on select-all: search, "Net area >", "Create and assign", Copy,
    Duplicate, Delete, green **"Auto Classify"**.
19. **2.28.31 PM — Auto Classify results.** Rooms recolored by predicted
    type: Corridor 1 = 1,511 SF; Hotel Room 17 = 5,171; Living Area 4 =
    1,096; Stairs 2 = 420; Lobby Elevator 1 = 171; Bedroom 20 = 2,783;
    **Shafts 85 = 1,351**; Utility 3 = 342; Bathroom 23 = 1,361; Elevator
    4 = 307; Closet 22 = 932; Balcony 1 = 78. (Counts sum to 183 = Net-area
    polygon count; internally consistent.)
20–21. **2.28.41/42 PM.** Row hover ↔ canvas highlight linking.

Pricing/plan info: none visible. Timing: per-page AI inference ~10–15s;
video claims 4.5-min flooring takeoff.

## Synthesis

### Workflow observed
Upload → auto page split + discipline classification + sheet autonaming
(305/513 pages) → open sheet (scale chip) → select drawing region → choose
detections (All/Custom) → Go → ~10–15s → layer tree (areas/lines/counts)
→ polygon edit verbs → right-click **Auto Classify** → per-room-type SF
breakdown → Quantities/Breakdown/Export/Compare/Export PDF. Parallel:
Togal.CHAT RAG over the doc set with page citations; honest misses.
Feedback: Great/OK/Poor widget per takeoff.

### UI/UX worth copying
- Layer tree with count + quantity per row, eye toggles, row↔canvas hover
  highlight.
- Live selection badge (SF + perimeter FT); Ctrl+A = whole-floor totals.
- Pre-run feature scoping (checkbox tree).
- Persistent scale chip.
- Auto Classify as a right-click verb staged AFTER detection (user can
  inspect raw polygons first).
- Great/OK/Poor rating widget = free labeled-feedback flywheel.
- Sheet autonaming + discipline folders at ingest (= our Model 1 shipped
  as a feature, with blue sheet-number chips + processed dots).
- Chat citations that deep-link to the source page.
- Progress states + onboarding tooltips.

### Weaknesses (where flooring-specialization wins)
- **Room taxonomy wrong for the building**: apartment tower classified as
  "Hotel Room 17" — fixed generic ontology; no evidence it reads the room
  name text ("UNIT A2") sitting on the polygon.
- **Shafts 85 / Elevator 307 SF / Stairs 420 SF are inside Net area** —
  non-finished areas not excluded by default; manual filtering after.
- **The two halves never join**: chat knows PT-1=restrooms, VCT-1=gym;
  geometry knows Bathroom 23 = 1,361 SF — nothing maps finish codes →
  polygons → SF-per-material. Most LVT entries "for unspecified areas".
  **This join is our product.**
- Counts are all-trades noise for flooring (sofas, beds, TVs); no
  transition strips, no wall-base LF as a flooring quantity, no
  direction/pattern awareness (Ashlar lives only in chat text).
- No per-material area; no casework/millwork deductions visible.
- 85 "Shafts" from 183 polygons — over-fragmented slivers dumped into a
  junk class.

### Implications for our data/model engineering NOW
- **Room-type labels belong in our schema**: record per-room name text +
  inferred type during SF extraction (we have vector text — structural
  advantage over their raster CV) to (a) exclude non-flooring SF by
  default, (b) join to finish schedules.
- **The finish-code join is the moat**: schedule row (PT-1/CP-1/LVT-n +
  designated-area text) → room polygons → SF per material. Togal has both
  endpoints, no bridge.
- **Benchmark units**: full plate (~17.7k SF, 183 rooms) in 10–15s; whole
  16-page doc in 4.5 min; 513-page set auto-classified at ingest. Measure
  our pipeline in the same units.
- Title-block extraction (sheet no + title) validated as first-class
  ingest output.
- Build the feedback widget into anything we ship.
- Keep door openings explicit in the geometry model (they detect Doors
  area + centerlines separately) — closure at openings + future
  transition quantities.
- Name WHICH area definition each output computes (net/gross/GIA/footprint).

### Open questions for the transcript
- Scale auto-detected or manual?
- What Re-Togal re-runs; what Compare compares.
- Does Auto Classify use room-label OCR; can users remap categories
  ("Hotel Room" → "Unit") persistently?
- Actual post-AI edit burden in the last 2+ minutes.
- Does 4.5 min include the 513-page ingest or just this sheet?
- Export/Breakdown outputs (Excel? pricing? waste factors?).
- Pricing/seat model.
- Can Togal.CHAT act on the takeoff or is it doc-RAG only?
