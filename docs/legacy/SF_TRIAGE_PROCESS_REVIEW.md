# Flooring Estimator — SF/Takeoff Process & Plan (for external review)

**Date:** 2026-07-08, patched 2026-07-09. **Branch:** `web`. **Purpose:** hand an
outside reviewer (ChatGPT/Codex) the full picture — the goal, what we've learned,
the triage process we just built, the ML plan, the data situation, and the
specific decisions we want critiqued. Please push back hard; we value
disagreement over agreement.

**This is v2 — revised after a first GPT + Codex review — patched again after the
Codex v2 review (`SF_TRIAGE_PROCESS_CODEX_REVIEW_V2.md`).** All counts are
**snapshots** (2026-07-08/09, from our inventory scripts) and shift as we scan
more.

## v2 changelog (what the first review changed)
Both reviewers converged, so we adopted almost everything:
- **Softened over-strong claims:** "geometry is exact" → *accurate for a correct
  polygon + verified scale/scope*; "CAD layers are exact walls" → *near-ground-
  truth weak labels needing QA*; "zero human labeling" → *minimal labeling after
  sampled QA*; "validated" → *two independent estimates agree* (not vs bid truth).
- **Stricter tiers:** GOLD_ALIGNED / TRAIN_LAYERED / TRUTH_AREA / MATERIAL_ONLY /
  MODEL_TARGET / DISMISS, with explicit alignment (room#s map to the plan; same
  scope/floor/revision). TRUTH_AREA is *area* truth, not final *bid* truth.
- **ML: vector-first, not U-Net-only** — our corpus is ~98% vector, so a
  vector/graph segment classifier is the primary approach; raster segmentation is
  the fallback for scanned pages; benchmark both.
- **Added a validation-discipline section** (frozen by-permit eval; **green
  precision** as the primary metric; no accuracy claim without a named ground-
  truth source) and a **failure-mode taxonomy**.
- **Measurement boundary** (centerline vs inside face) called out as a real
  systematic bias, not a footnote.
- **Softened acquisition wording** (rate-limited resumable crawler; no proxy
  emphasis) and added a small-batch **download policy** + a **HAND_CALIBRATION**
  set requirement.
- **Fixed `scripts/triage.py`** (append + run_id, `{doc_id,page_index}` refs,
  resolved-label view, dropped an unimplemented "density" claim).

## v3 patch (this cleanup — Codex v2 review consistency fixes)
The v2 Codex review approved the strategy but flagged wording that had drifted
from what `scripts/triage.py` and the rest of the pipeline actually do:
- Dropped the remaining "floor-plan density" wording (§3) — the mechanical scan
  never implemented a density model; it's resolved labels + wall-segment count +
  schedule text + a per-room SF regex.
- Removed "exact" from the runtime-pipeline CAD-layer branch (§5) and replaced
  "wall-segmentation model" with the vector-classifier/raster-fallback split
  already used in §4 (§5).
- Defined "flattened" explicitly (§2.3) — most of it is still vector linework.
- Rewrote the stale §7 as the five questions still actually open.
- Added the explicit `MATERIAL_ONLY` confirmation rule (§3).
- Added a paragraph on how provisional triage becomes confirmed, naming which
  file holds what today (§3).
- Folded in probe 24's closeability finding everywhere LAYERED tiering is
  discussed: a wall-segment count is necessary but not sufficient — TRAIN_LAYERED
  also requires passing the polygonize-quality gate (`scripts/scan_closeability.py`).
  See `experiments/probe24_two_permit_takeoff.md`.

---

## 1. What this is

A training-data pipeline + models for a **commercial flooring estimating app**.
An estimator today manually "takes off" a plan set: for each room, how many SF of
each flooring material (carpet / tile / resilient), plus linear feet of base and
transition strips. We want to automate as much of that as possible.

Data we have: **New Orleans "One Stop" public permit records** — 12,106 permits,
35,756 document records, PDFs stored in R2 (snapshot 2026-07-08). Table ownership:
**source tables are READ-only** (`estimate.permits`, `estimate.documents`);
**pipeline tables are writable/ours** (`estimate.document`, `estimate.page`,
`estimate.page_label`) plus local files under `data/`.

**Two models:**
- **Model 1 — page classifier:** which pages of a 50–100pp plan set matter for
  flooring (floor plans, finish plans/schedules, demo). Currently **PAUSED**.
  Best result was ~0.27 finish-recall on a frozen by-permit split; bottleneck is
  cross-permit generalization (signal organizes within-project).
- **Model 2 — square footage / the takeoff:** the current focus. Get per-room SF
  + material. This doc is mostly about Model 2.

**Immediate goal (Nick):** maximize takeoff accuracy/value before a meeting with a
flooring company (a likely data partner). Get the *process* solid on a few permits
first; that makes the ML better long-term and gives accuracy short-term.

---

## 2. What we learned about SF geometry (the honest arc)

Worked one permit end-to-end (14-11290, a Liberty Bank branch) then several more.

1. **Rules geometry (angle/width heuristics to guess walls) fails broadly** —
   ~11% clean, 61% "blob," and it silently fabricates rooms from legend boxes.
   Proven not tunable on dense/repeated-unit/rotated plans.
2. **Meaningful CAD layers are near-ground-truth for boundary classification.**
   If the PDF kept its layers, we grab the wall layer directly → clean rooms, even
   dense service cores. On the bank, a clean office measured 119 SF by geometry
   and the printed dimension also agreed at 119. But this needs QA: a layer like
   `A-WALL` can be centerlines, outlines, hatch, or demo/existing/new walls, on the
   wrong sheet. **Geometry is accurate for a correct polygon and a verified scale;
   the risk is whether that polygon is the right *flooring* boundary** (see §2a on
   measurement boundary).
3. **But only ~16–18% of files keep named layers**; 82% flatten every line onto
   one blank layer at PDF export. So layers are best used as **free training
   data**, not a runtime solution. (Corpus: of 150 downloaded permits, 27
   geometry-confirmed wall-layer permits.) **What "flattened" means, precisely
   (v3 clarification):** ~82% of files are *layerless/flattened-by-layer-name* —
   the export stripped layer names, not the linework. Our corpus is still ~98%
   vector even among the flattened files (only 1 of 51 sampled scanned pages was a
   true raster image; see §4). So "flattened" ≈ "no usable layer names, but still
   vector lines underneath" for the large majority; only a small slice are true
   raster scans with no vector geometry at all. This distinction is why the ML bet
   (§4) is a vector classifier first, not raster segmentation first.
4. **Layers = low-cost WEAK labels.** Render the flattened page as the INPUT, the
   wall layer as the LABEL → train a boundary model for the flattened 82%. Labels
   are weak, not gospel (`A-WALL` may include hatch; `A-DOOR` swing arcs; a finish
   layer may not be the finish *boundary*), so they need sampled QA + normalization
   — minimal human labeling, not zero. (Also carries door/finish/furniture.)
5. **"Merges" are mostly correct, not bugs.** On the bank, 4 of 5 merged rooms
   were open-plan (lobby/tellers/self-service is one space — the architect drew
   no wall). Open areas must be split by **finish boundaries**, not walls. Our
   *metric* ("one polygon per room label") was wrong, not the tool.
6. **Vision READS, geometry MEASURES.** A frontier vision model is great at
   reading printed dimensions, finish schedules, room labels — but a poor *ruler*
   (dimensions on plans are ambiguous, grid-to-grid). So vision = read text/
   tables; geometry = measure area; never the reverse.
7. **First validated takeoff (bank):** geometry cross-checked against
   independently-read dimensions → **10 of 13 enclosed rooms validated** (agree
   ≤15%, tight <5% on clean rooms), 1 genuine failure (a rotated glass vestibule),
   5 open (need finish split). Total 2,719 SF net vs 3,190 branch GROSS = −15%
   (normal net/gross gap). CAVEAT: "validated" = two independent estimates agree,
   not vs a true SF schedule (the bank has none).
8. **Ground truth exists in our own data.** A scan of schedule/life-safety pages
   found ~36 permits with per-room area tables. Confirmed one (26-05332) is a full
   Room Finish Schedule: room# + name + floor material + base + **area** + total.
   So we can measure accuracy WITHOUT the flooring company (their takeoffs still
   add volume + per-material quantities).
9. **The "golden" permit (layers AND per-room SF, on the same aligned floor plan)
   is RARE** — ~0 in the current 150-permit slice when you require page-alignment
   (layers were on demo/other sheets; or were hatch not centerlines). This forced
   a key relaxation (below).
10. **"Layered" also isn't the same as "geometry-usable" (probe 24, v3
    addition).** A wall-segment count only tells you linework exists on a named
    layer, not that it *polygonizes into rooms*. 25-33341's wall layer is a `.3D`
    solid (16,264 fragments, corner geometry never shares vertices) and closes
    almost nothing despite passing the segment-count test; 26-10321's clean 2D
    `NEW WALL`/`EXIST WALL` centerlines close cleanly. Of the closeability scan's
    11 permits with any named wall layer, ~2 are proven usable and ~3 are
    candidates — see §3's TRAIN_LAYERED row and `experiments/probe24_two_permit_takeoff.md`.

**Honest meta-note:** we revised the picture in the optimistic direction several
times in one day (−62%→−15%, "5 merges"→1, "3 fragments"→1, "4 golden"→0-aligned,
"27 layered"→~2 proven closeable) — every time from lacking ground truth or a
missing quality gate. Treat any un-validated accuracy claim with suspicion.
Ground truth is the gate.

### 2a. Measurement boundary (a real systematic bias)
Flooring SF is measured to the **inside wall face**. Our polygons come from wall
**centerlines** → they systematically **overcount**, and the error is worse in
small rooms (wall thickness is a larger fraction). This partly explains the
net-vs-gross gaps we saw. So even the "good" layer path needs an inward offset by
~half the wall thickness (or measure to the inside face) before quoting finish
area. Open questions we still owe an answer on: door thresholds, and whether
columns / shafts / casework are deducted (estimator-dependent).

---

## 3. The triage-permits process (the main thing to review)

Full manual: `.claude/skills/triage-permits/SKILL.md`. Agent:
`.claude/agents/schedule-reader.md`. Scanner: `scripts/triage.py`. Closeability
gate: `scripts/scan_closeability.py`.

**Principle:** decide *what the product should do with each permit* (a tier), not
"did geometry solve every room." Auto-triage everything cheaply; hand-invest only
where it pays.

**Tiers (v2, closeability gate added in v3):**
| tier | requires | use |
|---|---|---|
| GOLD_ALIGNED | centerline layers on the floor plan that PASS the closeability gate **+** per-room area schedule **+** room#s that map to that plan **+** same scope/floor/revision | full validation (rare) |
| TRAIN_LAYERED | wall centerline layers on a floor plan (not hatch/demo/legend) that PASS the polygonize-quality/closeability gate (`scripts/scan_closeability.py`) — a wall-segment count above threshold is necessary but NOT sufficient (probe 24: a `.3D`-solid layer can clear the segment count and still fail to close a single real room) | boundary-model training (weak labels, QA'd) |
| TRUTH_AREA | schedule with a per-room area column, rows mapping to the plan | grade geometry *area* (not final bid) |
| MATERIAL_ONLY | finish schedule with materials but no area column | validate material assignment only |
| MODEL_TARGET | floor plans, no closeable layers, no per-room SF | PARK — future flattened-plan inference |
| DISMISS | no floor plans / no flooring scope | mark & move on |

**Key relaxation (the fix for GOLD being rare):** TRAIN_LAYERED (layers) and
TRUTH_AREA (schedules) are collected as **separate piles** — layers teach the
model on one set, schedules grade it on another. We do NOT need both in one permit.
GOLD_ALIGNED requires *alignment*, not just co-presence, or a schedule can grade
the wrong floor/phase. (Bid-quantity truth comes only from a flooring company.)

**Per-permit pipeline (mechanical vs agentic):**
- A. Metadata gate — MECHANICAL (description/class/code/sqft/doc list).
- B. Doc-selection — **AGENTIC** (read messy doc names, pick which to download;
  `doc-selector` agent).
- C/D. Download + render (existing scripts).
- D2. Signal scan — MECHANICAL (`scripts/triage.py`). Per page: resolved page
  label (floor_plan/finish_schedule/etc., one category per page by source
  priority), wall-segment count on layer-classed linework, finish-schedule TEXT
  match, and a CANDIDATE per-room SF regex → **provisional** tier + rendered
  candidate schedule pages + the best wall page. This is signal-based, not a
  floor-plan-density model (see the note at the top of `triage.py`); nothing here
  is trusted as final.
- D3. Closeability gate — MECHANICAL (`scripts/scan_closeability.py`), v3
  addition. For any permit whose provisional tier depends on wall segments,
  actually snap+polygonize the wall layer and score the output (room-band
  polygon count, footprint coverage, largest-polygon fraction) rather than
  trusting the segment count alone. A permit that clears the segment threshold
  but fails this gate is NOT TRAIN_LAYERED.
- E. Confirm + label — **AGENTIC**: `schedule-reader` (Sonnet vision) confirms/
  rejects each candidate schedule and extracts room→(material, area);
  `page-labeler` agents label the plan-set pages (feeds Model 1 good+bad AND flags
  flooring pages); orchestrator confirms wall segs are centerlines on a floor plan
  (and that D3 passed); `label-adjudicator` (Opus) on disputes.
- F. Record tier + evidence → `data/triage/results.jsonl` (our file).

**`MATERIAL_ONLY` confirmation rule (v3 addition, explicit):**
```
schedule-reader returns is_schedule=true AND has_area_column=false
  => confirmed_tier = MATERIAL_ONLY
```
This is the same `schedule-reader` pass that gates TRUTH_AREA — the only
difference is `has_area_column`. No separate agent/step is needed.

**How provisional triage becomes confirmed (v3 addition — describing reality,
not the intended design):**
- `scripts/triage.py` is the only writer of `data/triage/results.jsonl`. It
  appends one JSON line per `(run_id, permit)` with a `provisional_tier` (always
  suffixed `?`) and a `confirmed_tier` field that it always sets to `null` — the
  script never confirms anything itself, by design (mechanical signal only).
- The intended confirmation step is `schedule-reader` (for TRUTH_AREA/
  MATERIAL_ONLY/GOLD_ALIGNED's schedule half) plus an orchestrator/agent check
  that wall layers are centerlines on the floor plan AND pass the D3 closeability
  gate (for TRAIN_LAYERED/GOLD_ALIGNED's layer half). **As of this writing that
  write-back is not wired up**: nothing appends a second, confirmed record to
  `results.jsonl`, and no row's `confirmed_tier` has ever been set. This matches
  Codex v2 review finding #8 and is still open.
- Separately, `scripts/pipeline.py` (`mark` / `evaluate` commands) tracks a
  coarser per-permit **status**, not the GOLD/TRAIN/TRUTH tier, in
  `data/triage/permit_status.jsonl` (append-only, latest record per permit wins):
  `todo` / `in_progress` / `done` / `dismissed`, with a free-text `tier` field
  that today holds outcomes like `READY` / `NEEDS_SIBLING_DOC` / `DISMISS` from
  the completeness-gate check — a *different* vocabulary than the triage tiers
  above. Don't confuse the two files: `results.jsonl` is provisional
  tier-evidence from the mechanical scan; `permit_status.jsonl` is the
  hand-worked worklist/board. Neither file currently holds a confirmed
  GOLD_ALIGNED/TRAIN_LAYERED/TRUTH_AREA/MATERIAL_ONLY record — closing that gap
  (wiring `schedule-reader` + the closeability gate to write back into
  `results.jsonl`) is the next operational step.

**Hard rules:** never trust a mechanical GOLD/TRUTH (vision confirms); schedule
reading is vision not regex; layers must be centerlines on the floor plan (not a
demo/legend/hatch sheet) AND pass the closeability gate; page labels append-only;
don't trust sparse labels to judge flooring content (big docs are under-labeled —
saw 8 of 109 pages labeled).

**Why vision, not regex, for schedules (verified):** our regex SF-parser flagged
23-05848 as GOLD with a "9-room schedule" — but the numbers were *occupant-load
callouts printed on a floor plan* ("ENTERTAINMENT 765 SF"), not a table. The
confirmation step caught it → really TRAIN. Hence `schedule-reader` (vision) is the
gate for TRUTH/GOLD.

**One agentic pass produces both models' data:** labeling (E) yields Model-1
examples (keep + non-keep) *and* flags the flooring pages for SF — not two jobs.

---

## 4. The ML plan (Model 2 boundary-identifier)

The ML replaces exactly ONE step — classify which linework is
**wall / door / finish-boundary / clutter** — and keeps the rest (scale from text,
room labels, room-closing geometry we already have).

- **Data (free-ish):** layered PDFs → weak per-element labels from the layers
  (QA'd/sampled). ~27 layered permits by segment count now, but per probe 24 only
  a fraction of those actually pass the closeability gate (~2 proven, ~3
  candidates of the 11 permits with any named wall layer, per
  `data/triage/closeability.csv`) — grows as we download more and re-score.
  Split by permit. The real risk is firm-diversity (drafting/export style),
  orthogonal to model choice.
- **Model — VECTOR-FIRST (the v2 change).** Our corpus is **~98% vector** even
  when flattened (only 1 of 51 scanned) — the flattened files are vector linework
  with layer *names* stripped, not images (see §2.3's definition of "flattened").
  So the primary approach is a **vector/graph segment classifier**: each
  line/curve → features (length, angle, width, dash, connectivity, parallel-twin,
  near-room-label, near-door-arc, local crop) → wall/door/finish/clutter score.
  Layer labels map directly onto segments; more data-efficient than pixels
  (matters at ~27, closeability-gated to fewer, permits); output feeds geometry
  directly. **Raster segmentation (U-Net; prior art CubiCasa5K, Raster-to-Vector)
  is the fallback for genuinely scanned pages.** Benchmark both on the same
  by-permit split; likely hybrid (vector for vector PDFs, raster for scans).
- **Use:** flat plan → segment/pixel boundary scores → existing snap/polygonize →
  inside-face offset → rooms → × scale → SF.
- **Grade:** against TRUTH_AREA permits and the HAND_CALIBRATION set; green
  precision first (§4a).

**What it WILL do:** extend decent wall-finding from a closeability-gated ~16-18%
(layered) to most files; learn to ignore furniture/clutter (the thing that
blobbed rules).
**What it WON'T do (honest):** (a) make room-*closing* work — predicted walls are
messier than CAD lines, so closure is still hard; (b) split open-plan areas (no
walls there — needs a separate finish-boundary signal); (c) be *exact* like the
layer path (raster → approximate, and even the layer path needs the inside-face
offset of §2a); (d) generalize from a couple dozen permits (needs more).
**It's a bet** — thin-line floor-plan boundary classification is genuinely hard
(more so for raster than vector), and a closeability-gated layered set under-covers
firm diversity even more than the raw count suggested; even a win yields
*assisted* takeoff (model proposes, human confirms), not full automation. Minimum
viable bar: a boundary-model quality metric (per-class segment F1 / IoU on
held-out permits) before it's allowed near the geometry step.

### 4a. Validation discipline (mandatory — we have over-claimed)
- Split by permit, never by page. Freeze an eval set before tuning; don't inspect
  eval failures while changing rules.
- **No accuracy claim unless every number names its ground-truth source**
  (schedule SF vs dimension agreement vs hand-measured — never mixed).
- Report by room-type (enclosed / open-zone / restroom-core / corridor /
  rotated-glass) and by file-type (scanned / vector / layered) — never one global
  number without the failure mix.
- **Primary product metric = green precision:** when the system marks a room
  auto/accepted, how often is it actually right? For assisted takeoff that beats
  average SF error. Report accepted-only vs accepted+check vs all-attempted
  separately. Every demo shows a red/yellow failure, not only greens.
- Keep a **HAND_CALIBRATION** set (5–10 permits / 50–100 rooms, human-measured for
  scale, boundary, material, SF) as the honest yardstick — independent of training.

---

## 5. The product pipeline (runtime)

```
upload plan set
  → page filter: keep only flooring pages   [Model-1 ML paused → interim rule/agent filter;
                                             triage labeling still collects Model-1 data]
  → vision agent: read finish schedule (materials, rooms, SF)  [VISION]
  → floor plan → walls:
        has QA'd CAD layers (centerlines, closeability-gate passed)?
            → use wall/door/finish layers as high-confidence boundaries
        layerless vector PDF (the ~82% "flattened" majority, still vector linework)?
            → vector boundary classifier                        [ML, the bet]
        true raster scan (small minority, no vector geometry)?
            → raster segmentation fallback                      [ML, fallback]
  → geometry: close walls → room polygons → × scale → SF        [have it]
  → assemble: SF × material + base (perimeter) + transitions
  → human confirms the low-confidence rooms                     [assisted]
```

**Per-room state machine (Nick's loop) — how we operate + generate ML targets:**
each scheduled room gets a product action: `auto_quantity`, `open_zone_split`,
`geometry_review`, `vision_correct_or_redraw`, `scale_review`, `material_review`,
`no_geometry`. Debug only the non-green ones, and **log each failure's type →
which model/rule would fix it** (missed wall → wall model; open lobby → finish-
boundary model; glass vestibule → storefront model; schedule mismatch → extractor;
scale mismatch → scale validator). Failure notes become training labels. Over time
a "confidence/review classifier" learns to auto-route rooms → less agentic work.

---

## 6. Data landscape & acquisition

Funnel (real numbers):
```
12,106 permits total
 2,663 have scraped doc metadata
 1,300 have plan/drawing docs
 1,095 permits downloaded to R2 (2,327 docs)
```
Two gaps: **929 permits** have known plan-docs not yet downloaded (immediate);
**9,443 permits** have no doc metadata (needs discovery from One Stop: `ref` →
search → ItemID → view page → doc IDs). Acquisition is a **rate-limited, resumable
public-record crawler** that stops on 429/CAPTCHA and keeps request logs; we'll
pursue bulk/export access where possible.

**Download policy (don't bulk-pull):** reviewed queue → download 25–50 docs →
render → triage → choose permits. Never mass-download raw filename-regex
candidates unsampled.

**North-star for acquisition:** maximize the closeability-gated TRAIN_LAYERED and
TRUTH_AREA piles (not the raw wall-segment-count pile — see §3/§4). Prioritize
NEWC + has-sqft, and building-type diversity (restaurant/office/medical/
retail/warehouse — everything validated so far is one bank plus two more office/
lab buildings, so generalization is still thin).

---

## 7. Open questions (v3 — replaces the stale decisions list)

The v2 "specific decisions" section had gone stale (same questions carried since
v1, with no visible resolution marks). Per the Codex v2 review, here are the five
questions that are actually still open:

1. **How much hand calibration before the meeting?** How many HAND_CALIBRATION
   permits/rooms (§4a) do we need measured before we can show Nick's flooring-
   company contact a credible accuracy number, and who measures them?
2. **What is the first vector classifier baseline?** Given the closeability-gated
   layered set is smaller than the raw segment count suggested (§2.10, §4), what
   is the minimum viable vector/graph segment classifier we train first, and on
   how many permits, before judging vector-first vs raster-first?
3. **What is the threshold for green auto-quantity?** What green-precision number
   (§4a) is required before a room is allowed to auto-quantity without human
   review in the product, and does that threshold vary by room-type/file-type?
4. **Do we attempt finish-boundary detection now, or leave open zones
   human-split?** Open-plan areas (§2.5) have no walls to learn from; is a
   separate finish-boundary model worth building now, or do we ship with human
   split for open zones and revisit later?
5. **Which building types must be represented before any accuracy claim?**
   Every validated result so far is a bank plus two office/lab buildings
   (probe 24) — what's the minimum building-type spread (restaurant/medical/
   retail/warehouse/etc.) before an accuracy number is allowed to generalize
   beyond "we validated on N buildings of type X"?

---

## 8. Agents & skills used (what's in each)

The pipeline runs via **skills** (instruction manuals read by a model) and
**agents** (spawned sub-models that read a skill and do one scoped job). Quality
tiers: Sonnet does bulk/worker jobs; Opus adjudicates/judges; scripts do all
mechanical work.

### Skills (`.claude/skills/<name>/SKILL.md`)

- **triage-permits** (the thing under review) — the per-permit tiering
  process. Contents: the 6 tiers + what each is for (incl. the v3 closeability
  gate on TRAIN_LAYERED); the "separate TRAIN/TRUTH piles" relaxation; the A→F
  pipeline marking mechanical vs agentic; the hard rules (never trust mechanical
  GOLD/TRUTH, schedule-reading is vision not regex, layers must be centerlines on
  the floor plan AND closeability-gated, labels append-only, don't trust sparse
  labels); worker routing; the `data/triage/results.jsonl` schema. (Full text is
  essentially Section 3 above.)
- **label-pages** — how to classify a plan-set page into 16 categories
  (floor_plan, finish_plan, finish_schedule, demo_plan, reflected_ceiling,
  furniture_plan, site_plan, elevation_section, detail, schedule_other,
  structural, mep, life_safety, cover_index, specs_notes, other). Contents:
  category definitions + common confusions (finish_plan vs floor_plan; RCP vs
  plan), hybrid-sheet rule (keep the flooring category, flag it), per-page fields
  (category, confidence, sheet_title, scale/finish-code/table/room-label/dimension
  booleans, flag_reason, evidence), and mechanics: judge the IMAGE, label BLIND
  (never read existing labels), append-only INSERT via `scripts/db.sh`, keep is
  DERIVED (1 iff category ∈ floor/finish/finish_schedule/demo; site plans never
  keep), page-identity guard, batches of 10, hard stop 80 pages.
- **orchestrate-pipeline** — the conductor's manual. Contents: worker routing
  (Sonnet workers / Opus adjudication / scripts / GPU only for embeds-fine-tunes),
  labeling-wave drip system (80-page assignment files ordered by PROJECT VALUE,
  throttle 2=drip/8=burst, respawn on completion), reviewer/adjudicator gates,
  the rung ladder for model work, keep-list-change protocol, budget rules,
  commit discipline (never commit data/.env).
- **sf-extraction** — the Route-A geometry pipeline manual: extract vector lines
  → wall candidates → suppress hatches → snap/close → polygonize → per-room SF via
  scale; known failure modes + counters; verification standard (grade vs printed
  dimensions; scale self-audit; reject legend-box fabrications).
- **review-labels** — blind second-opinion protocol (judge image first, THEN
  compare to first-pass; never anchor). **diagnose-model** — first-principles
  post-sweep diagnosis (decompose inputs/outputs, measure, name the binding
  constraint, order the cheapest fix).

### Agents (`.claude/agents/<name>.md`) — model · tools · job

- **schedule-reader** — *Sonnet · Read, Bash*. Reads a rendered schedule
  page image and decides `is_schedule` (a real room-finish table with area) vs
  occupant-load/egress callouts on a plan vs door/window schedule vs noise; when
  true, extracts `rooms:[{num,name,floor,base,area}]` + `has_area_column` +
  `total_sf`. Returns strict JSON. Exists specifically to stop the regex
  false-positives that promote permits to TRUTH/GOLD wrongly (verified on
  23-05848's occupant-load callouts). Judges the image, never the filename;
  honest `is_schedule=false` when it's not a table. Its `has_area_column` output
  is also the direct input to the MATERIAL_ONLY confirmation rule (§3).
- **doc-selector** — *Sonnet · Read, Bash, Glob, Grep*. Reads a permit's full
  document list, downloads plausible plan documents liberally, and decides which
  actually contain the architectural floor plans / finish schedule (step B).
- **page-labeler** — *Sonnet · Read, Bash, Glob, Grep*. Reads label-pages skill,
  labels ONLY assigned pages, blind, source='claude-code', hard stop 80,
  append-only. Feeds Model 1 (keep + non-keep) and flags flooring pages.
- **label-reviewer** — *Sonnet*. Reads review-labels + label-pages; blind
  re-judge then compare; writes source='claude-code-review' rows; reports
  agree/disagree page_ids. Rides on confidence<0.8 ∪ flagged ∪ 10% audit.
- **label-adjudicator** — *Opus*. Settles labeler↔reviewer disagreements with a
  fresh look; append-only source='claude-code-adjudicate'; 'needs human' when
  undecidable. Also used for triage tier disputes.
- **sf-prober** — *Sonnet · +Write, Edit*. Builds/runs SF geometry probes per the
  sf-extraction skill; never derives geometry from PNGs; every result has per-room
  SF JSON + dimension grading table + overlay PNGs; outputs nothing if scale fails.

### How they compose in one triage pass
`triage.py` (script) pre-sorts → `page-labeler` (Sonnet) labels pages (Model-1
data + flooring flags) → `schedule-reader` (Sonnet vision) confirms/extracts the
finish schedule → orchestrator confirms wall-centerlines-on-floor-plan AND the
`scan_closeability.py` gate → sets the tier → `label-adjudicator` (Opus) only on
disputes. Mechanical where possible, Sonnet for the bulk agentic reads, Opus only
for judgment.

## 9. File map for the reviewer
- Process: `.claude/skills/triage-permits/SKILL.md`, `.claude/agents/schedule-reader.md`,
  `scripts/triage.py`, `scripts/scan_closeability.py`
- SF arc: `experiments/probe7_layer_walls.md` (layers), `probe8_semantic_layers.md`
  (free labels), `probe11_merge_diagnosis.md` (open-plan), `probe14_vision_errorcheck.md`
  (vision), `probe17` (gap tracer), `probe18_groundtruth.md` (ground truth found),
  `probe19_validation.md` + `probe22_bank_validated.md` (validation),
  `probe24_two_permit_takeoff.md` (closeability gate finding),
  `ML_ARC_layers_to_product.md` (ML plan)
- Rules/state: `CLAUDE.md`, `STATE.md`
11