# ML Roadmap & Demo Screen Map — v1.1 (R1 verdicts appended; body amended by §7)

*Fable, 2026-07-11 (final Fable window). Purpose: the successor-proof ML
plan + the screen inventory for the demo. Process: Nick runs this through
the consultation loop with GPT (rounds, per-component verdicts, terse
final-lock); once LOCKED, GPT produces mockup images for the unmocked
screens, and a Claude driver builds per design-loop + spec-driven-dev
skills. Codex is available as an execution driver for well-specced builds.*

## FOR THE REVIEWING MODEL (GPT/Codex) — read this first

You are the outside reviewer in this project's consultation loop. This
file is the position doc. Before responding, READ (in this order):

1. `CLAUDE.md` — standing rules and data layers.
2. `STATE.md` — project history; at minimum the sections from
   "Rung-2c results" onward, especially "PROBE 30 / 30b" (current model
   honest state) and "CATCH-UP: the V2 design sprint".
3. `SCHEMA_V2.md` — the locked V2 constitution (identities, append-only
   decisions, datasets). The roadmap must not contradict it.
4. `togal_teardown/TEARDOWN_DECISIONS.md` — competitor conclusions this
   roadmap absorbed (deeper: CLAUDE_INDEPENDENT_ANALYSIS.md,
   GPT_ANALYSIS.md).
5. `.claude/skills/improvement-loop/SKILL.md` — the standing machine,
   gates, honesty rules. Also `.claude/skills/design-loop/SKILL.md`
   (locked UI rules) and `V2_CLARIFICATIONS.md` items 11–14.
6. Skim `experiments/probe30b_dataset_audit.md` and
   `experiments/probe30_wall_model_v2.md` — the evidence behind
   station 3's "architecture must change" claim.
7. `design_specs/*_APPROVED.png` — the four approved screens (images).

**How to respond — write your response as a NEW file,
`ML_ROADMAP_REVIEW_R1.md`, do not edit this one.** Structure it as:
(a) CLARIFYING QUESTIONS — anything ambiguous or under-specified;
(b) SUGGESTIONS — additions/changes, each with the reason and what it
costs; (c) STRONG AGREEMENTS — where you'd defend this plan as-is;
(d) STRONG DISAGREEMENTS — where you think this is wrong, with your
counter-proposal and the evidence or reasoning; (e) ANSWERS to §6's six
questions; (f) anything else worth discussing. Judge components on
merits — do not defer to this doc's authority or soften disagreements.
Numbered points throughout so the reply round can reference them.
Founder (Nick) arbitrates disagreements; rounds continue until locked.

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

## 7. ROUND-1 VERDICTS (Claude, 2026-07-11 — these deltas amend the body; R2 folds them in)

Reviewer: Codex (ML_ROADMAP_REVIEW_R1.md). Per-component verdicts per the
consultation loop. Honest headline: the review corrected four genuine
overclaims in v1.0 (D1 schedule≠area, D4 zero-clicks wording, D7
perimeter≠base, D8 "permanently"), and nearly everything else is adopted.

**ADOPTED — all eight disagreements D1–D8:**
- D1: the near-term path is the **area-schedule path**, gated on a
  verified area source; non-area finish schedules yield material
  assignment only, SF stays honestly unmeasured. (v1.0 overclaimed.)
- D2: "architecture must change" downgraded to **leading hypothesis**,
  tested only after the clean cluster-disjoint rebaseline.
- D3: Station-3 gates are paired-improvement AND absolute thresholds on
  a sealed benchmark; beating rules-v4 alone never ships.
- D4: zero clicks = zero clicks **to a complete proposal**; binding
  truth always requires the human decision. LLM output = candidate
  ranking/explanation, never "adjudication" (word reserved for the
  human decision graph, per F2).
- D5: coverage = two orthogonal axes (quantity source × disposition),
  disjoint buckets, displayed denominator with evidence.
- D6: canonical routes are `/v2/b/[buildingId]`; permit URLs become
  redirecting aliases. Slice-1 `[permit]` routes are logged route debt.
- D7: geometry emits `gross_perimeter_lf` + opening lengths;
  `net_base_lf` is a separately derived quantity with named scope rules.
- D8: Station 4 = "do not train now; reconsider on measured triggers
  (cost/latency/correction-rate over 3 snapshots)" — not "permanently."

**ADOPTED — suggestions B1, B2, B4–B12, B14 and F1–F3:** Station 0
(intake/identity/plan-set assembly — confirmation of the active plan set
gates all joins); Station 2b (scale resolver/verifier, abstains on
disagreement — v1.0's biggest omission, probe-30 history supports it);
Station 3 split into 3a boundary / 3b space semantics (rules+LLM first,
model only after corrections accumulate) / 3c derived quantities;
four-gate ladder (research → shadow → bounded demo → bid/export);
split_v1 demoted to historical regression set, new leakage-group +
firm-cluster snapshot with sealed founder-audited test; field-level
schedule metrics + constrained bipartite join with uniqueness rules;
complete screen map incl. Pipeline, Source Files/plan-set, scale
confirm, material setup, export (adopt reviewer's E1 route table as the
inventory to lock); schedule/join track decoupled from probe 31;
diversity-unit acquisition (clusters/format-families, never nominal
rows); signed audit artifacts per gate; model contracts (schema,
abstention states, idempotency, budgets) added to each station card;
risk register with owners and stop conditions in the locked version.

**MODIFIED (2):**
- B3 (jobs-DAG refactor): adopt the contract-and-jobs target, but
  SEQUENCE it — takeoff.py stays the research crank through probe 31;
  the job-handler refactor lands with the pilot slices that need async.
  Refactoring before the architecture experiment is premature.
- B6 (sealed geometry truth set): adopt, phased — ~15–20 fully corrected
  cluster-new regions unlock the BOUNDED-demo gate on narrow categories;
  the full 40–60 before any market-facing claim. (Founder-time is the
  scarce input; see decisions below.)

**ADOPTED — answers E1–E6** as working positions: U-Net-first prior with
both arms still run in probe 31; E3's volume table enters the doc as
PLANNING PRIORS explicitly subordinate to measured learning curves (the
numbers are priors, not gates); coverage page/region-first with building
rollup as strict aggregation; the five schedule-break cases become the
pilot's required mix; E6 becomes the verification protocol (blind-audit
queue separate from production confirms; 100% consequential review on
pilot buildings 1–2; then 5% stratified floor + 100%-trigger list;
critical silent error resets the stage to 100%).

**REJECTED: none.** (Recorded so R2 knows this was judged on merits, not
deference: the review's positions survived because they cite this
repo's own evidence — TRUTH_AREA tier, probe 30 scale failures, 30b
leak/contamination — not because they came from outside.)

**FOUNDER DECISIONS NEEDED (Nick — these are resource/priority calls,
not technical disputes):**
1. The sealed geometry truth set is YOUR correction time (~15–20 regions
   near-term, 40–60 eventually). Commit to it phased, or narrow the
   station-3 demo claim further?
2. The verification tax: ~15–20 min per work session of stratified blind
   audit after the 100%-review pilot buildings. Sustainable?
3. Route rename to buildingId (small build task, do during next UI
   slice): approve?

## 8. FOUNDER PROCESS DECISIONS (Nick, 2026-07-11 — binding; R2 must reflect)

1. **No rush to lock.** Rounds continue until right, not until Fable's
   window ends.
2. **PILOT RESET:** all V2 pilot-building work done so far (a prior
   badly-orchestrated agent ran labeling with awful results) is
   DISTRUSTED. Reset = constitution-compliant quarantine, never
   deletion: mark that run's machine_observations defective / its
   decisions superseded-non-binding via NEW rows, then re-run the 10
   pilot buildings fresh under the protocol below. First executing
   driver: identify that run's source/actor ids before writing the
   quarantine rows. ROOT CAUSE (Nick, diagnosed 2026-07-11): the bad
   orchestrator switched labelers to TEXT-ONLY extraction — labeling
   from page text without viewing the page image. This violates the
   standing CLAUDE.md rule ("labelers judge the page IMAGE; title block
   is a hint, not a verdict") and cannot work: plan content is visual.
   HARD GUARD for the re-run and forever: every labeling worker (Claude
   AND Codex) must Read the rendered page image; text-only labeling
   rows are auto-quarantine. (Text remains a fine FEATURE for training
   Model 1 — the trained model may use text; agent labelers may not
   label blind of the image.)
3. **CROSS-VENDOR DUAL LABELING (standing practice):** two INDEPENDENT
   workers from different vendors — one Claude (Sonnet) + one Codex —
   blind-label the same pages (categories + flags).
   - AGREE → the claim becomes machine CROSS-VERIFIED (SCHEMA_V2 §14
     trust tier: grey solid + evidence icon) — eligible for Nick's
     bulk-accept, NOT auto-confirmed: only a human decision resolves as
     truth, and two models can agree and both be wrong (correlated
     errors), so a 5–10% stratified blind audit of the AGREE pile is
     mandatory.
   - DISAGREE → review queue: Opus arbitrates (Claude tokens are the
     cheaper pool) with Nick as final authority on anything
     Opus flags uncertain; during the verification-debt era Nick
     personally reviews the disagree pile.
4. **General engineering practice:** same pattern for important
   builds/analyses — two independent agents (cross-vendor when
   possible), attention spent on the disagreements. Single-agent
   default = Claude (Max plan headroom).

**R2 instruction to the reviewer:** produce ML_ROADMAP_REVIEW_R2.md —
confirm/contest these verdicts, then draft the LOCK version structure
(final station cards incl. Stations 0 and 2b, gate ladder, risk
register, screen inventory from your E1 table). Terse numbered deltas
only; end with LOCKED / STILL OPEN lists per the consultation-loop
skill.
