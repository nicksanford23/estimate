# ML Roadmap & Demo Screen Map — v1.0 draft for consultation

*Fable, 2026-07-11 (final Fable window). Purpose: the successor-proof ML
plan + the screen inventory for the demo. Process: Nick runs this through
the consultation loop with GPT (rounds, per-component verdicts, terse
final-lock); once LOCKED, GPT produces mockup images for the unmocked
screens, and a Claude driver builds per design-loop + spec-driven-dev
skills. Codex is available as an execution driver for well-specced builds.*

## 0. STATUS OF TRUTH (read first)

**Founder verification debt: Nick has not personally verified ANY model
output or metric to date.** Every number below (recalls, PR-AUCs, error
rates, answer-key agreements) is machine-graded or Claude-judged, not
founder-confirmed. Treat them as honest measurements with unverified
provenance, not ground truth. THE STANDING ADJUSTMENT for the next era:
Nick's verification becomes a first-class pipeline stage — the pilot
protocol's blind audits (SCHEMA_V2 §11) plus spot-verification of every
metric that gates a decision (see §6 gates: each now requires a founder
spot-check line). A number no human verified cannot justify a promote.

## 1. Architecture principle

The product is an assembly line: PDF → pages → regions → geometry →
schedule → join → review → corrections → retrain. Each station gets the
cheapest adequate engine, upgraded only when measurement says so:

> rules/script → rented LLM call → trained model

Building a trained model where a script or LLM suffices is the main
failure mode to avoid. `takeoff.py` stays the single orchestrator with
swappable per-stage engines (it already supports `--engine`); models
ship as versioned components (SCHEMA_V2 model_version + dataset
snapshots); the jobs queue (§8) runs stages async for the UI.

## 2. The five stations (spec cards)

### Station 1 — Page classifier (Model 1)
- **Job:** which pages matter. Input: render + extracted text. Output:
  category (15-tax) + flags (contains_area_table on EVERY page).
- **Engine:** trained model (text TF-IDF + image router). Exists; weak.
- **Honest state:** finish-recall 0.267 @0.5 on frozen split_v1 —
  cross-firm generalization is the binding constraint, not architecture.
- **Data source:** labels accrue free from pilot + triage byproduct
  (machine_observations confirmed by Nick's decisions in Page Review).
- **Eval:** frozen by-permit split (split_v1 rules; whales forced train).
- **Gate:** retrain at ~2x firm diversity; ship when full-recall
  frac_kept ≤ ~15% on a founder-spot-checked eval.
- **Sufficiency:** data path exists (2.3k+ downloaded docs, 85k
  discovered). No blocker — label and retrain.
- **Code:** scripts/train_sweep*, rung2c.py, make_split.py.
- **UI:** Page Review (BUILT) — dashed suggestion chips are this model;
  every confirm is a training row.

### Station 2 — Region/viewport finder
- **Job:** where the drawing(s) sit on the sheet; multiple viewports.
- **Engine:** heuristics (page_select.py lineage) + human confirm
  (Approve/Redraw/Full-page in Page Review). NO ML yet.
- **Flywheel:** every redraw decision = future training example
  (region_geometry claims). Revisit as a model only if redraw rate stays
  painful after the pilot.

### Station 3 — Boundary model (rooms + SF) — THE RESEARCH RISK
- **Job:** room polygons + SF + (NEW, from Togal teardown) room TYPE,
  junk classes (shaft/core/sliver — excluded by default), perimeter LF
  (wall base), door openings kept explicit.
- **Engine today:** rules-v4 + wall_model_v2 dual-run. Honest state:
  model memorizes DESIGNS not firm styles (probe 30b; pooled holdout
  PR-AUC 0.214 after leak removal), learning curve FLAT at 49 firm
  clusters → more same-vocabulary data will NOT fix it; the architecture
  must change. Label hygiene (MEP sheets, stair/trim contamination) is
  the second binding constraint.
- **Next experiment (probe 31):** raster U-Net over renders vs graph
  network over vector segments, trained on CAD-layer labels AFTER
  hygiene filters; cluster-disjoint holdout (probe30b/clusters.csv).
  Learning curve BY FIRM-CLUSTER is the deliverable — it answers the
  data-sufficiency question with a number.
- **Gate (unchanged from improvement-loop):** promote only if held-out
  downstream rooms-vs-truth beats rules-v4 on flattened permits, graded
  by takeoff.py against founder-spot-checked answer keys; canaries hold.
- **Sufficiency: UNKNOWN — say so.** 80 verified layered permits / 49
  clusters is enough to RUN probe 31, not known-enough to ship. The §5b
  consultation sets the credible-demo threshold; if probe 31's curve is
  still climbing at 49 clusters, the acquisition path is cluster-NEW
  layered permits from the 85k discovered docs (downloader running).
- **Code:** takeoff.py, geometry_v4.py, geometry_model.py, probe25/30
  harness, truth_area answer keys.
- **UI:** Geometry Review (BUILT) — verdicts + traced corrections
  (geometry_annotation) are the correction flywheel.

### Station 4 — Schedule reader
- **Job:** finish-schedule page → structured rows (room, name, floor
  material, base, area).
- **Engine decision: rented vision LLM, PERMANENTLY until volume says
  otherwise.** Few pages per building, cents per call, already works
  (schedule-reader agent). Do NOT train a table model now.
- **Eval:** answer keys (4 TRUTH_AREA permits ±0.02%; target ≥10) +
  "accept N clean rows" confirmations in Rooms & Finishes (BUILT).

### Station 5 — The JOIN (schedule row ↔ room) — THE WEDGE
- **Job:** what Togal doesn't have: finish code → room polygons → SF per
  material, zero clicks.
- **Engine:** deterministic + fuzzy room-name/code matching + LLM
  adjudication on conflicts. Not a trained model. Instrument the failure
  mode (names/numbers that don't align) from day one — GPT's skepticism
  point, adopted.
- **Data:** confirmed space_source_link decisions = the eval set.
- **UI:** Rooms & Finishes →space links (BUILT) + coverage
  reconciliation panel (NEEDS MOCKUP).

## 3. Two demo paths (strategy)

- **Schedule path (stations 1+4+5): demoable SOON.** Buildings with
  finish schedules get a full traceable takeoff with no geometry.
- **Geometry path (station 3): the moonshot**, gated on probe 31.
- The coverage reconciliation panel is what lets one product honestly
  hold both: measured / from-schedule / awaiting review / excluded /
  unmeasured, with a coverage %. Never Togal's uniform success-green.

## 4. Build order (post-Fable, executable by Codex/Opus + Claude driver)

1. Pilot 2–3 buildings through V2 (validates machinery; starts label
   flywheel; NICK VERIFIES outputs — the new discipline).
2. Boundary prep, cheap: label-hygiene filters + cluster-disjoint
   re-baseline of wall_model_v2 (probe 30b list; eval-only, no GPU).
3. Probe 31 (architecture experiment) with the learning curve as the
   headline output. GPU ~$2–5.
4. Join rules + schedule-path demo (Codex-friendly; specs exist in
   triage/truth_area work).
5. UI: Work Queue build (image approved), Datasets/Models simple tables
   (no images needed per §14), then design rounds for teardown items.
6. Model 1 retrain at ~2x firm diversity (labels from pilot/triage).

## 5. UI state + SCREEN MAP (to agree with GPT, then image, then build)

**Process:** this map is the deliverable to LOCK with GPT — screen list,
purpose, route, data deps. GPT then produces mockups ONLY for rows
marked needs-mockup; approved images become the spec (design-loop hard
rule); a Claude driver builds. Do not design layouts in this round —
inventory and boundaries only.

**Built (per approved images, slice 1–3):**
| Screen | Route | Feeds/fed by |
|---|---|---|
| V2 index (project cards) | web/app/v2/page.tsx | permits/buildings |
| Page Review | web/app/v2/b/[permit] (tab) | Station 1+2 flywheel |
| Rooms & Finishes | same, tab | Station 4+5 flywheel |
| Geometry Review | same, tab | Station 3 flywheel |

**Approved image exists, NOT built:**
| Work Queue (lanes, deep links) | web/app/v2/page or /v2/queue | blocking-stage lanes |

**No image needed (simple tables per SCHEMA_V2 §14):**
| Datasets | /v2/datasets | snapshot → ingredients trace |
| Models | /v2/models | model → scores → snapshot links |

**NEEDS MOCKUP (the GPT image round while Fable is gone):**
| Screen/component | Why |
|---|---|
| Coverage reconciliation panel (building + page level) | teardown B1 — the honest-numbers centerpiece |
| Building Summary tab (rollup: floors, plans, schedule, coverage) | pilot navigation hub |
| Source Files + Activity tabs | §10 IA, thin |
| DEMO: upload → processing narration (page filmstrip, live classification) | customer-facing station-1 showcase |
| DEMO: customer takeoff review (V2 product version of the v0.5 /review prototype; trust states, evidence card, class-level bulk verbs, exclusion states) | the sales demo core |
| DEMO: bid sheet / export (verified vs pending vs estimated $ split, assumptions/exclusions block) | teardown B3 |
| Evidence card component (schedule-row crop / printed-dim / scale source) | shared across review screens |

**Locked context for the image round:** global nav (Work Queue ·
Buildings · Datasets · Models · Pipeline), chip color law, trust states,
canonical 8 flags, design-loop rules 1–10, teardown DO-NOT-COPY list
(no uniform green, no naked confidence %, no pricing without
verification state).

## 6. Questions for the GPT round

1. Screen map completeness: what's missing for a credible pilot + demo?
2. Station 3: U-Net vs graph-over-vectors — prior? (Both run in probe
   31 regardless; asking for arguments, not authority.)
3. §5b: what per-model data volume makes a demo credible vs Togal's
   scale story? Numbers, per station.
4. Coverage reconciliation: page-level, building-level, or both first?
5. Where would the schedule-path demo break first in the field
   (name-join failures, schedule formats)?
6. Verification protocol: cheapest founder-verification design that
   makes §0's debt shrink every session (blind-audit rate, which
   stages).
