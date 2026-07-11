# Togal.AI flooring-takeoff teardown — Claude's independent analysis

*2026-07-11. Sources: full video transcript (4:54, "4.5 min Flooring
Takeoff in Togal.AI", youtube PbvupUyQHeY) + all 55 screenshots in
togal_teardown/screenshots/ (read frame-by-frame by a 3-agent fleet;
reports in agent_report_1/2/3*.md). Produced BLIND to GPT's analysis per
protocol. Timestamps are video time; frame files cited where load-bearing.*

**Meta-caveat that colors everything:** this is Togal's own marketing
demo, screen-recorded from a Togal insider's browser (bookmarks: "Togal
vs PlanSwift/Bluebeam/Onscreen", Stripe Dashboard, "Usage By Org",
"Clicks, Unclaimed"). Best-case footage, clean CAD-quality vector-looking
hotel plate, one page of a 16-page doc. Every number below is happy-path.

## 1. Feature inventory

| Capability | Tag | Evidence |
|---|---|---|
| Togal.CHAT project-wide doc Q&A (RAG over uploaded set incl. spec book) | demonstrated | 0:20–1:24; 30sec.png, 50.png |
| Chat page-level citations that deep-link ("…Drawings (1) 2-155") | demonstrated | 30sec.png |
| Chat honest-miss behavior (admits docs may not contain answer) | demonstrated | 30sec.png |
| Chat product-level finish extraction (PT-1 Daltile SKU/size/pattern/area designations) | demonstrated | 50.png; 0:35–0:48 |
| Ingest: auto page-split + discipline classification (513-page set → Electrical 99 / Mechanical 26 / Structural 21 / Arch 52…) | demonstrated, not narrated | 20sec.png |
| Sheet autonaming (title + sheet number chips; 305/513 via "Autonaming") | demonstrated, not narrated | 20sec.png |
| One-click detection: areas + wall/door lines + object counts, one pass | demonstrated | 1:34–1:55; 96sec–1.50.png |
| Detection speed ~10–15 s for a 17.7k SF plate (183 net-area rooms) | demonstrated (frame-timing inference) | 95sec→1.50.png |
| Pre-run feature scoping (All Features / Custom checkbox tree) | demonstrated | 96sec.png |
| Net area with walls removed, per-room polygons | demonstrated | 2:05–2:26; 1.50.png |
| Multiple area definitions (Footprint / Net / Gross / GIA / Doors) | demonstrated | 1.50.png |
| Wall centerline 3,796 FT / wall perimeter 6,729 FT / door centerlines | demonstrated | 1.50.png |
| Object counts incl. furniture (23 toilets, 23 bathtubs, beds, sofas, TVs) | demonstrated | 1.50.png |
| Auto Classify → room types (Corridor/Bedroom/Bathroom/Closet/Shafts…) | demonstrated | 2:35–2:51; 2.28.31.png |
| Mechanism of Auto Classify ("a couple of things it's picking up") | claimed verbally only — undisclosed | 2:46 |
| Classification library (Org/Private tabs, trade catalogs, drag-import) | demonstrated | 2:55–3:10; F3–F7 |
| Class-level bulk select → right-click assign to material (2–3 clicks per room class) | demonstrated | 3:13–3:48 |
| Selection chip with SF + perimeter FT on any selection | demonstrated | cntrlA.png, F9, F12 |
| SF → tile piece counts (EA) → box counts → price-per-SF columns | demonstrated ($ values redacted) | 4:31–4:44; report 3 |
| "Fastest and easiest takeoff software" | claimed only | 0:03 |
| "On ANY floor plan it's going to do exactly what you're seeing here" | claimed only — single clean plate shown | 2:08 |
| "Saves thousands of clicks / countless hours" | claimed only | 1:55 |
| Re-Togal (re-run detection), Compare, Breakdown, Export, Export PDF | implied/ambiguous — buttons visible, never used | top bar, all frames |
| 3D toggle | implied — visible, unused | editor chrome |
| Post-run rating widget (Great/OK/Poor) | demonstrated (their feedback flywheel) | 1.48+ every frame |

Forensic notes: the balcony/shaft **misclassification is shown and
spun live** ("it looks like it's calling them shafts… AI is not smarter
than you and I… very easy to do this cleanup", 3:50–4:20). What the
narration does NOT mention: the raw run produced **85 "Shafts"** polygons
and the cleanup includes marquee-deleting ~86 areas plus three
one-at-a-time "Delete features" confirm modals on 15–36 SF slivers
(frames 4:08–4:21) — silent in the voiceover. Also tooltip/tree SF
disagreements (1,359 vs 1,361) and EA math ~1.5–2% below naive division
with **no waste factor anywhere**.

## 2. Workflow reconstruction

1. **Ingest (not narrated, glimpsed):** 513-page set already uploaded,
   auto-split into discipline folders with autonamed sheets. Setup
   time: never shown.
2. **Scope discovery (0:20–1:24, human-driven):** estimator asks
   Togal.CHAT for a flooring scope of work; gets product-level finish
   list with citations. Chat output is *read*, not wired to anything.
3. **Detection (1:28–2:05, automatic):** open sheet (scale chip
   "1/8"=1'0"" present — provenance never shown), region pre-boxed,
   optional feature scoping, green button → ~10–15 s → 693 areas +
   1,119 lines + 352 counts.
4. **Room typing (2:29–2:51, one gesture):** Ctrl+A → right-click →
   Auto Classify → 183 net polygons sorted into ~12 room types.
5. **Material mapping (2:51–4:30, fully manual):** drag flooring
   catalog in; per room-class: select class → right-click → product.
   Hotel rooms/living→LVT-1, bedrooms→LVT-2, corridors→carpet,
   bathrooms→LVT-3, "shafts"(=balconies)→polished concrete. **The
   assignments come from the estimator's head, NOT from the finish
   schedule the chat read at 0:35** — demo materials don't even match
   the chat's PT-1/CP-1 list. ~60 s for one plate.
6. **Cleanup (3:55–4:21, manual, downplayed):** toggle shaft class,
   delete ~86 junk polygons; repeated confirm modals on slivers.
7. **Output (4:31–4:44):** quantities table SF/EA/boxes/$-per-SF.
   Export never clicked.

Conspicuously NOT shown: upload + processing time for 513 pages; scale
detection/confirmation; any boundary correction (not one polygon edge is
fixed in the whole video); multi-sheet propagation (page 14 of 16 — the
other 15 pages of takeoff never happen); scanned/raster or rotated
plans; schedule→material join; waste factors; deliverable file; failure
or empty states; pricing.

## 3. UX patterns worth stealing

- **Class-level select → bulk assign** (3:13–3:48): room-type detection
  turns 183 polygons into ~6 decisions. The single highest-leverage
  interaction shown.
- **SF + perimeter FT chip on every selection** (cntrlA, 2:21): perimeter
  = wall-base LF, a top-3 flooring line item, surfaced for free.
- **Layer tree ↔ canvas sync** (2:40–2:44): row hover highlights
  polygons; per-row eye toggles; count + SF on every row.
- **Right-click assign menu** with search + Recently Used +
  Create-and-assign (3:27–3:46): user never leaves the canvas.
- **Material names carry dimensions** ("LVT Type 2 (6x12)") driving
  automatic SF→EA→box→$ columns (4:36).
- **Rating widget on every AI run** (from 1:48): a zero-friction labeled
  feedback stream. We planned correction capture; add the cheap 3-level
  rating too.
- **Ingest classification as a visible feature** (20sec.png): discipline
  folders + sheet-number chips + processed dots — our Model 1, shipped
  as UI.
- **Persistent scale chip**; progress states ("Togal in progress" →
  "Preparing data"); pre-run feature scoping.
- Chat citations that deep-link to the source page (30sec.png).

## 4. Weaknesses and gaps

- **The two halves never meet.** Chat reads finish schedules to product
  level (50.png) and geometry knows Bathroom 23 = 1,361 SF, but nothing
  joins finish code → rooms → SF-per-material. The estimator does that
  join by hand, from memory, on camera. This is the entire middle of
  the video.
- **Zero evidence trail.** No number is ever justified: no printed-dim
  cross-check, no confidence, no provenance, no flag states. 15,524 SF
  appears and is trusted because it's green. Their own frames show SF
  discrepancies (1,359 vs 1,361) and sub-naive EA math with no waste —
  numbers an estimator can't audit.
- **Confidently wrong by default**: balconies classed as "Shafts"; 85
  shaft polygons on one floor (over-segmented cavities/slivers); stairs,
  elevators, shafts all included in "net area" a flooring user must
  manually exclude. Everything renders as equally-confident solid fill.
- **Generic all-trades noise**: furniture counts, 3 redundant gross-area
  layers, 1,119 lines — a flooring estimator's tree is mostly junk.
- **Assignment destroys the room dimension**: assigning Bedroom→LVT
  empties the Bedroom row (693→672→652…). The room-type × material
  matrix — how flooring bids get checked — is gone.
- **Cleanup UX is bad**: per-item delete confirm modals; no "delete all
  areas < X SF".
- **No flooring math**: no waste, no roll/seam direction, no transitions
  (147 doors detected, unused), no base derived from the perimeter they
  already compute.
- Demo evasions: one clean vector-ish page; no corrections; no other 15
  pages; "any floor plan" claimed, not shown.

## 5. Head-to-head vs us

**Where they're ahead (honest):**
- Working end-to-end product at market scale; we're pre-launch.
- Raster-capable detection (~10–15 s/plate) covering areas+lines+counts.
  Our geometry needs vectors and is honest-but-weak (probe 30/30b).
- A functioning room-TYPE classifier — we don't have one at all yet.
- Ingest classification at 500-page scale in production (our Model 1 is
  0.267 finish-recall on the frozen split — theirs ships).
- Doc-chat with citations (commodity to build, but it exists and demos
  well).
- Material library / pricing columns / polish; distribution, brand,
  "vs PlanSwift/Bluebeam" collateral; a live feedback flywheel at scale.

**Advantage type:** detection quality = data+engineering (hard to match
head-on); room classifier = moderate ML; chat = commodity engineering;
library/pricing = pure engineering (cheap to match); distribution =
distribution.

**Where we're ahead or can be:**
- **The schedule join** — their demo's entire manual middle is our core
  pipeline (finish_schedule classification → schedule-reader → room-name
  ↔ schedule join → SF per material with zero clicks). They show zero
  capability here.
- **Evidence-first trust**: our V2 trust states (dashed/cross-verified/
  confirmed), every number traceable to a schedule row or printed dim,
  unmeasured shown as unmeasured. They have literally nothing in this
  category — and their demo leaks the discrepancies that positioning
  punishes.
- **Honest accuracy**: answer-key-graded numbers vs their unverifiable
  green fill; our confident-but-wrong-is-unforgivable rule is a stated
  differentiator they can't retrofit cheaply (their UX trains users to
  trust fill colors).
- **Flooring-native quantities**: base LF, transitions from doors, waste
  factors, room×material matrix preserved.
- Vector advantage where it applies: room-name text sits on our polygons
  natively; their raster CV apparently ignores it (apartment "UNIT A2"
  classified "Hotel Room").

**Skeptical read of our own claims:** our differentiators are currently
mostly *designs*, not shipped capability; our boundary engine underperforms
their demo on their happy path and our corpus is NOLA-permit-shaped. The
wedge is real only if the schedule join actually works end-to-end on
pilot buildings.

## 6. What we should change NOW (prioritized)

1. **Emit perimeter LF per room polygon** in sf-extraction/takeoff.py —
   free, immediate, unlocks wall-base quantities. (Engineering, hours.)
2. **Make the schedule→room→material join the demo centerpiece** — the
   exact chapter their video does by hand (2:51–4:30) should be our
   zero-click moment. Measure it in their units: minutes per plan set.
3. **Room-TYPE taxonomy into the plan**: when boundary work resumes,
   harvest room-label text per polygon + a type head; add junk/negative
   classes (shaft/elevator/stair/balcony/sliver<20 SF) excluded from
   flooring SF *by default*. Their observed 12-class set is a starter
   taxonomy. Feeds SCHEMA_V2 `space.kind`.
4. **3-level rating widget + correction capture on every AI output** in
   V2 (SCHEMA_V2 already has the decision machinery; add the one-click
   rating as a machine-feedback observation).
5. **Class-tree ↔ canvas + bulk-accept patterns** into the design-loop
   backlog for Geometry Review/Rooms&Finishes (bulk accept exists in
   §14; add class-level select).
6. **Ship sheet autonaming visibly** at ingest (we already extract
   titles) — table-stakes polish they've normalized.
7. **Counter-claims to prepare**: "Togal colors rooms; it doesn't read
   your finish schedule — you assign every material by hand." / "Ask
   them where any number comes from." / "No waste factor, no base, no
   transitions in the flooring takeoff."
8. Keep tile-dimension fields in the material model (SF→EA→box math is
   trivial, build late, schema now).

## 7. What we should NOT copy

- **All-trades object detection** (furniture, fixtures) — impressive,
  irrelevant to flooring, and it created the junk firehose.
- **Confident uniform fill with no trust states** — directly opposed to
  our positioning; their "everything is green" is the thing we attack.
- **Auto-assignment that consumes room identity** — keep the
  room×material matrix.
- **Multiple redundant gross-area layers** dumped on the user.
- **Price-per-SF columns before an accuracy story** — pricing polish on
  unaudited quantities is exactly "confident-but-wrong at the bid line."
- **Fixed generic room ontology** over reading the drawing's own room
  names/schedule codes.
- Chat as a headline feature: cheap to add later; it's a spec-reader,
  not a takeoff engine, and it anchors expectations to chatbots.

## 8. Positioning & sales intel

- **Pricing:** nothing shown; $ values redacted in the demo table.
  Stripe Dashboard + "Usage By Org" bookmarks ⇒ SaaS, org-level usage
  tracking, likely seat/usage tiers. Investigate published pricing.
- **Target customer:** generalist estimator at GC/sub, all trades —
  "flooring" here is one use-case video in a series ("3-min demo",
  vs-competitor pages). Nobody flooring-native made this: LVT filed
  under "Tile," no base/waste/seams.
- **Onboarding friction:** demo implies upload→magic, but library
  building, room-type correction, junk cleanup, and material mapping are
  all user labor; the video's own 4.5 min covers ONE page of 16.
- **Integration claims:** none shown (Export/Compare/Breakdown unused).
- **One-sentence pitch against them, to a flooring estimator:** "Togal
  makes you faster at coloring the plan — we read the finish schedule
  and the plan together, hand you the flooring quantities with every
  number traceable to a schedule row or printed dimension, and tell you
  honestly which rooms we couldn't measure instead of shading them
  green."

## 9. Open questions (investigate outside the video)

1. What Auto Classify actually uses (room-label OCR? geometry priors?)
   and whether it can auto-assign MATERIALS — if yes, our wedge narrows;
   menu placement suggests classify-only today.
2. Whether assignments/classifications propagate across sheets, and real
   per-set (not per-page) takeoff time.
3. Raster/scanned-plan performance (our corpus reality; their demo plate
   looks vector-derived).
4. Pricing/seats; trial availability (their CTA is sales-led "send us
   your drawings" — suggests they want to control first impressions).
5. Their training-data story (patents, blog, "millions of plans" claims)
   — sizes the detection moat for our demo-data-sufficiency analysis
   (FABLE_FINAL_DAYS §5b).
6. Export/Breakdown/Compare outputs (Excel? bid formats?), Togal.CHAT
   write-actions, and the units in the carpet "252" / concrete "39"
   columns.
7. Mine their "Togal vs PlanSwift/Bluebeam/Onscreen" pages for the
   claims they think win deals.
8. User reviews/forums on where detection actually fails in the field
   (the corrections their rating widget is harvesting).

## Recommended decisions for the cross-exchange with GPT

(a) Adopt perimeter-LF and rating-capture immediately (cheap, no
conflicts possible). (b) The schedule-join-as-demo-centerpiece should be
tested against GPT's read — if GPT saw the same gap, it's confirmed as
the positioning spine. (c) Data-engineering change: add room-type +
junk-class labels to the boundary track's schema now, before the ML
architecture session locks the model portfolio. (d) Treat their 10–15 s
raster detection as the benchmark to NOT chase head-on; we win on the
join + evidence, not on generic segmentation speed.
