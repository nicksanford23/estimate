# Agent report 3/3 — cleanup & finalizing the takeoff (frames 2.30.17–2.32.10 PM)

*Background Sonnet-fleet report, 2026-07-11, chunk 3 (18 frames, video
time 3:35→4:45 — the last quarter). Blind: produced without GPT's
analysis or the transcript.*

## Frame-by-frame (deltas)

- **3:35–3:39** — Corridor (1,511 SF) selected → right-click → assigned to
  **Carpet** (~2s). Root 652→651. Tooltip "1511 SF / 553 FT".
- **3:43–3:47** — all 23 bathrooms class-selected (tooltip "1359 SF /
  760 FT" vs tree 1,361 — 2 SF discrepancy) → Tile > **LVT Type 3
  (14x14)**: ~4s, 3 clicks. Root 651→628; "Tile 64".
- **3:55–3:59** — Shafts (85, 1,351 SF) toggled visible: dozens of small
  teal polygons across the plan. One selected; cursor on **Auto Classify**.
- **4:08** — marquee selection; root 628→**542** (~86 areas = Shafts +
  Balcony purged between frames).
- **4:17–4:21** — **"Delete features" confirm modal three times in a row**
  (checkbox "Don't ask me for now" never checked) deleting 15–36 SF sliver
  polygons one at a time. Running SF readout 883→848→836.
- **4:30** — cleanup done. Material groups: **Carpet 1** (1,511 SF);
  **Tile 64**: LVT Type 3 (14x14) ×23 = 1,361 SF, LVT Type 2 (6x12) ×20 =
  2,783 SF, LVT Type 1 (10x10) ×21 = 6,267 SF; **Polished Concrete 15 =
  786 SF**. (~56 more areas assigned off-camera in ~9s.)
- **4:32** — chapter "**Finalizing the takeoff**": plan = color-coded
  material map (green LVT-1, yellow LVT-3, violet carpet, teal other).
- **4:36–4:45** — quantities table with derived columns: Carpet — 1,511 SF
  | 252 | $$$; Tile 64 — 10,411 SF | 15,264 | 649; LVT Type 3 ×23 — 1,361
  SF | **987 EA** | 76 boxes | $$; LVT Type 2 ×20 — 2,783 SF | **5,431
  EA** | 155 | $$; LVT Type 1 ×21 — 6,267 SF | **8,846 EA** | 418 | $$;
  Polished Concrete ×15 — 786 SF | 39 | $$. Togal lines 1,119 — 11,047 LF.
  SF → piece counts from tile dims → box counts (13.0/35.0/21.2 pcs per
  box) → cost columns (values redacted). Video outro.

**Arithmetic check on their EA math**: 14×14 ⇒ 1,361/1.361≈1,000 vs 987
shown; 6×12 ⇒ 2,783/0.5=5,566 vs 5,431; 10×10 ⇒ 6,267/0.694≈9,030 vs
8,846. All ~1.5–2% BELOW naive division — netting something out, and **no
waste factor anywhere** (a real estimator adds 5–10%).

## Synthesis

### What this captures + effort accounting
The manual half of Togal's flow on one ~17.7k SF hotel plate (652 AI
areas): corridor→carpet ~4s; 23 bathrooms→LVT ~4s (class-select makes
n-rooms as cheap as 1); **junk removal ~40s and the worst UX** — 85 shaft
polygons + slivers deleted with repeated confirm modals; whole
classify+assign+cleanup pass ~60s of video for one page. Room detection
looks solid on this clean CAD-quality plan (bathroom count 23 plausibly
exact), but raw output is heavily over-segmented for flooring (85 shafts,
147 door areas, 3 redundant gross layers, 1,119 lines, 352 counts). Also
a 1,359 vs 1,361 SF tooltip/tree discrepancy on the same selection.

### UI/UX worth copying
- Class-level select → bulk assign (the single highest-leverage
  interaction in the video).
- Live SF/FT tooltip on any selection (perimeter = wall base for free).
- Layer tree with instant per-class count + SF rollups, eye toggles.
- Material catalog with dimensions in the name driving automatic
  SF→EA→boxes→$ derivation.
- Color-coded material map as the reviewable deliverable; Export PDF.
- Re-Togal one-button re-run; Auto Classify in the context menu;
  contextual keyboard chords (⌘G group, ⌘B combine).

### Weaknesses (flooring wedge)
- **No finish-schedule intelligence** — the entire 3:35–4:32 segment
  exists because Togal doesn't know what goes ON the floor. Schedule-reader
  + room-label join automates their whole manual chapter away.
- **Junk firehose**: all-trades detection leaves flooring users wading
  through shafts/doors-area/gross layers/lines/counts. A flooring-only
  view suppresses non-floor classes at inference.
- **Sliver deletion via per-item confirm modals** — no "delete all areas
  < X SF" bulk action.
- No waste factor, roll/seam planning, direction-of-lay, or transition
  strips (147 doors detected, unexploited). EA math is naive division.
- Redundant tri-layer gross areas left for the user to ignore.

### Implications for our data/models NOW
- **Room-TYPE labels, not just boundaries** — type enables bulk material
  assignment and schedule joins. Attach a room-type head or harvest
  room-name text within each polygon.
- **Door openings as first-class geometry** (closure + transition LF).
- **Junk suppression is a labeled concept**: shafts, chases, cores,
  slivers < ~20 SF as negative classes — saves the 40s/page cleanup Togal
  makes manual.
- Perimeter alongside area in every SF output.
- **Schedule → room-type → material auto-assignment is the wedge**;
  everything after the AI run is mechanical given a parsed schedule.
- Piece/box/cost derivation = static material table + arithmetic (no ML,
  build late) but store tile dimensions in the material model from day
  one.
- Persistent scale chip confirms scale detect/confirm belongs in our UX.

### Open questions for the transcript
- Minutes 0:00–3:35 (upload flow, per-page AI latency, whether any room
  BOUNDARIES were corrected — true boundary accuracy).
- Does classification/assignment propagate across pages, or per-page?
  (Page 14 of 16 — what about the other 15?)
- What Auto Classify fires on (hovered twice, never used).
- $$ column configuration (pricing DB vs user cost codes); Export/
  Breakdown/Compare outputs.
- Can Togal.CHAT do the material assignment via natural language (would
  erode the wedge)?
- Units: "252" for Carpet (SY? rolls?), "39" for Polished Concrete (bags?).
