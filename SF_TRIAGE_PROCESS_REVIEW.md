# Flooring Estimator — SF/Takeoff Process & Plan (for external review)

**Date:** 2026-07-08. **Branch:** `web`. **Purpose:** hand an outside reviewer
(ChatGPT) the full picture — the goal, what we've learned, the triage process we
just built, the ML plan, the data situation, and the specific decisions we want
critiqued. Please push back hard; we value disagreement over agreement.

**This is v2 — revised after a first GPT + Codex review.** All counts are
**snapshots** (2026-07-08, from our inventory scripts) and shift as we scan more.

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
   geometry-confirmed wall-layer permits.)
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

**Honest meta-note:** we revised the picture in the optimistic direction several
times in one day (−62%→−15%, "5 merges"→1, "3 fragments"→1, "4 golden"→0-aligned)
— every time from lacking ground truth. Treat any un-validated accuracy claim with
suspicion. Ground truth is the gate.

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
`.claude/agents/schedule-reader.md`. Scanner: `scripts/triage.py`.

**Principle:** decide *what the product should do with each permit* (a tier), not
"did geometry solve every room." Auto-triage everything cheaply; hand-invest only
where it pays.

**Tiers (v2):**
| tier | requires | use |
|---|---|---|
| GOLD_ALIGNED | centerline layers on the floor plan **+** per-room area schedule **+** room#s that map to that plan **+** same scope/floor/revision | full validation (rare) |
| TRAIN_LAYERED | wall centerline layers on a floor plan (not hatch/demo/legend) | boundary-model training (weak labels, QA'd) |
| TRUTH_AREA | schedule with a per-room area column, rows mapping to the plan | grade geometry *area* (not final bid) |
| MATERIAL_ONLY | finish schedule with materials but no area column | validate material assignment only |
| MODEL_TARGET | floor plans, no layers, no per-room SF | PARK — future flattened-plan inference |
| DISMISS | no floor plans / no flooring scope | mark & move on |

**Key relaxation (the fix for GOLD being rare):** TRAIN_LAYERED (layers) and
TRUTH_AREA (schedules) are collected as **separate piles** — layers teach the
model on one set, schedules grade it on another. We do NOT need both in one permit.
GOLD_ALIGNED requires *alignment*, not just co-presence, or a schedule can grade
the wrong floor/phase. (Bid-quantity truth comes only from a flooring company.)

**Per-permit pipeline (mechanical vs agentic):**
- A. Metadata gate — MECHANICAL (description/class/code/sqft/doc list).
- B. Doc-selection — **AGENTIC** (read messy doc names, pick which to download).
- C/D. Download + render (existing scripts).
- D2. Signal scan — MECHANICAL (`triage.py`): wall segs, floor-plan density,
  finish-schedule text, CANDIDATE per-room SF → **provisional** tier + rendered
  candidate schedule pages. Nothing trusted as final.
- E. Confirm + label — **AGENTIC**: `schedule-reader` (Sonnet vision) confirms/
  rejects each candidate schedule and extracts room→(material, area);
  `page-labeler` agents label the plan-set pages (feeds Model 1 good+bad AND flags
  flooring pages); confirm wall segs are centerlines on a floor plan;
  `label-adjudicator` (Opus) on disputes.
- F. Record tier + evidence → `data/triage/results.jsonl` (our file).

**Hard rules:** never trust a mechanical GOLD/TRUTH (vision confirms); schedule
reading is vision not regex; layers must be centerlines on the floor plan (not a
demo/legend/hatch sheet); page labels append-only; don't trust sparse labels to
judge flooring content (big docs are under-labeled — saw 8 of 109 pages labeled).

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
  (QA'd/sampled). ~27 layered permits now; grows as we download more. Split by
  permit. The real risk is firm-diversity (drafting/export style), orthogonal to
  model choice.
- **Model — VECTOR-FIRST (the v2 change).** Our corpus is **~98% vector** even
  when flattened (only 1 of 51 scanned) — the flattened files are vector linework
  with layer *names* stripped, not images. So the primary approach is a
  **vector/graph segment classifier**: each line/curve → features (length, angle,
  width, dash, connectivity, parallel-twin, near-room-label, near-door-arc, local
  crop) → wall/door/finish/clutter score. Layer labels map directly onto segments;
  more data-efficient than pixels (matters at 27 permits); output feeds geometry
  directly. **Raster segmentation (U-Net; prior art CubiCasa5K, Raster-to-Vector)
  is the fallback for genuinely scanned pages.** Benchmark both on the same
  by-permit split; likely hybrid (vector for vector PDFs, raster for scans).
- **Use:** flat plan → segment/pixel boundary scores → existing snap/polygonize →
  inside-face offset → rooms → × scale → SF.
- **Grade:** against TRUTH_AREA permits and the HAND_CALIBRATION set; green
  precision first (§4a).

**What it WILL do:** extend decent wall-finding from ~18% (layered) to most files;
learn to ignore furniture/clutter (the thing that blobbed rules).
**What it WON'T do (honest):** (a) make room-*closing* work — predicted walls are
messier than CAD lines, so closure is still hard; (b) split open-plan areas (no
walls there — needs a separate finish-boundary signal); (c) be *exact* like the
layer path (raster → approximate); (d) generalize from 27 permits (needs more).
**It's a bet** — thin-line floor-plan boundary classification is genuinely hard
(more so for raster than vector), and 27 permits under-covers firm diversity; even
a win yields *assisted* takeoff (model proposes, human confirms), not full
automation. Minimum viable bar: a boundary-model quality metric (per-class
segment F1 / IoU on held-out permits) before it's allowed near the geometry step.

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
        has CAD layers? → grab wall layer          (exact, ~18%)
        flattened?      → wall-segmentation model   (approx, ~82%) [ML, the bet]
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

**North-star for acquisition:** maximize the TRAIN_LAYERED and TRUTH_AREA piles.
Prioritize NEWC + has-sqft, and building-type diversity (restaurant/office/medical/
retail/warehouse — everything validated so far is one bank, so generalization is
untested).

---

## 7. Specific decisions we want critiqued

*(v2 note: the first review resolved several of these — we committed to
**vector-first ML** (Q1/Q4), split TRUTH (Q2), and adopted green-precision +
frozen-eval discipline (Q7). The still-open ones are marked ⬚.)*

1. **Is "vision reads, geometry measures, ML finds walls" the right division?**
   Or should we attempt a vector/graph model over the line segments instead of
   raster U-Net?
2. **The tier system** — are GOLD/TRAIN/TRUTH/FLATTENED/DISMISS the right cuts?
   Is the "separate piles" relaxation sound, or do we actually need aligned GOLD
   permits to trust anything?
3. **Ground-truth strategy** — lean on found finish-schedules (~36 permits, quality
   varies), hand-measure a calibration set, or bank everything on the flooring
   company's historical takeoffs? How much to invest before the meeting?
4. **The ML bet** — is thin-line commercial floor-plan wall segmentation likely to
   work well enough at ~27→few-hundred permits, or is that too little data? Better
   to buy/adapt a pretrained floor-plan parser?
5. **Model 1 pause** — right call to defer the page classifier and let the
   triage/labeling pass regenerate its data as a byproduct?
6. **Open-area splitting** — is "finish-boundary detection" realistic, or should
   open areas just be quoted as one material zone + human split?
7. **Over-optimism risk** — given we re-revised accuracy optimistically several
   times, what validation discipline would you impose before any "accuracy" claim?

## 8. Agents & skills used (what's in each)

The pipeline runs via **skills** (instruction manuals read by a model) and
**agents** (spawned sub-models that read a skill and do one scoped job). Quality
tiers: Sonnet does bulk/worker jobs; Opus adjudicates/judges; scripts do all
mechanical work.

### Skills (`.claude/skills/<name>/SKILL.md`)

- **triage-permits** (NEW, the thing under review) — the per-permit tiering
  process. Contents: the 5 tiers + what each is for; the "separate TRAIN/TRUTH
  piles" relaxation; the A→F pipeline marking mechanical vs agentic; the hard
  rules (never trust mechanical GOLD/TRUTH, schedule-reading is vision not regex,
  layers must be centerlines on the floor plan, labels append-only, don't trust
  sparse labels); worker routing; the `data/triage/results.jsonl` schema. (Full
  text is essentially Section 3 above.)
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

- **schedule-reader** (NEW) — *Sonnet · Read, Bash*. Reads a rendered schedule
  page image and decides `is_schedule` (a real room-finish table with area) vs
  occupant-load/egress callouts on a plan vs door/window schedule vs noise; when
  true, extracts `rooms:[{num,name,floor,base,area}]` + `has_area_column` +
  `total_sf`. Returns strict JSON. Exists specifically to stop the regex
  false-positives that promote permits to TRUTH/GOLD wrongly (verified on
  23-05848's occupant-load callouts). Judges the image, never the filename;
  honest `is_schedule=false` when it's not a table.
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
finish schedule → orchestrator confirms wall-centerlines-on-floor-plan → sets the
tier → `label-adjudicator` (Opus) only on disputes. Mechanical where possible,
Sonnet for the bulk agentic reads, Opus only for judgment.

## 9. File map for the reviewer
- Process: `.claude/skills/triage-permits/SKILL.md`, `.claude/agents/schedule-reader.md`, `scripts/triage.py`
- SF arc: `experiments/probe7_layer_walls.md` (layers), `probe8_semantic_layers.md`
  (free labels), `probe11_merge_diagnosis.md` (open-plan), `probe14_vision_errorcheck.md`
  (vision), `probe17` (gap tracer), `probe18_groundtruth.md` (ground truth found),
  `probe19_validation.md` + `probe22_bank_validated.md` (validation), `ML_ARC_layers_to_product.md` (ML plan)
- Rules/state: `CLAUDE.md`, `STATE.md`
