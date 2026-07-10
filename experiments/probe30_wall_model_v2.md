# Probe 30 -- wall_model_v2, the first real wall-classifier training run

**Date:** 2026-07-10
**Scripts:** `scripts/probe30_roster.py`, `probe30_extract_worker.py`,
`probe30_train.py`, `geometry_model.py`, `probe30_downstream.py`,
`probe30_product_test.py`, `probe30_canary.py`
**Artifacts:** `models/wall_model_v2.joblib` (+ `wall_model_v2_ablation_raw.joblib`,
`data/probe30/learning_curve/model_N{15,30,45,60,all}.joblib`),
`data/probe30/{roster.csv, all_pages.csv, segment_results.json,
downstream/, product_test/, canary/, overlays/, features/}`

**Verdict up front: CONDITIONAL PROMOTE, staged not wholesale.** The model
beats rules-v4 on the exact promotion-gate test (TRUTH_AREA, same grader,
same 182-room denominator) on all three published columns. But segment
PR-AUC is still weak/highly firm-variable, the learning curve is FLAT (not
climbing), and a stricter downstream check against permits' own layer-truth
rooms (the 10 held-out LAYERED permits, not TRUTH_AREA) shows the model
recovers only ~2.6% of real rooms. Recommend shipping the model as an
ADDITIONAL candidate engine (run both, prefer whichever engine matches more
rooms / flag disagreement for review) rather than replacing rules-v4 as the
default, and prioritizing feature/architecture work over more data before a
second promotion attempt. See "Promote/park reasoning" at the end.

---

## Roster and holdout split

Training set = `verdict=CONFIRMED` rows in `data/triage/eyeball_verdicts.csv`.
Started at 73 permits, reconciled to **79** mid-run when a sibling re-gate
agent recovered 6 more CONFIRMED permits (coordinator-directed course
correction) -- the split was rebuilt from scratch since it had not yet been
used to train anything, so no contamination risk. Final: **69 train / 10
holdout permits, 1 page each (79 pages total)**.

**Sibling floor-plan pages of the same doc were deliberately EXCLUDED**, a
documented scope-limiting choice: `layered_plans.csv` lists 451 candidate
pages across these 79 docs, but the 2026-07-09 audit's dominant false-pass
mode was exactly MEP/RCP/site sheets reusing the architectural wall xref
without being real floor plans -- only the primary page per permit has an
eyeball verdict, so admitting un-eyeballed siblings would reintroduce
exactly the contamination the re-gate was built to remove.

**Holdout list** (chosen for firm diversity -- one permit per distinct
wall-layer-naming signature, from `probe8_layer_classes.classify_layer`'s
own wall-token regex):

| permit | doc | page | wall-layer signature |
|---|---|---|---|
| 19-27788-NEWC | 4237450 | 7 | (no wall-token match -- e.g. STUD/PARTITION-only naming) |
| 22-07153-RNVS | 5404106 | 1 | 02_NEW_INTERIOR_WALLS, A-WALL, A-WALL-COMP |
| 16-03048-NEWC | 2265638 | 36 | 1-A-WALL |
| 24-07484-NEWC | 6783427 | 5 | 1-A-WALL-NEW, 2-A-WALL, 3-A-WALL |
| 16-03038-NEWC | 2285400 | 36 | 1-A-WALL, 1-A-WALL-NEW |
| 23-17834-RNVS | 6217680 | 10 | 1-EXIST-WALL, 1-EXST-WALL |
| 25-15704-NEWC | 8188952 | 3 | 2-5-A-WALL, 2-A-WALL, 2-A-WALL-NEW, 4-A-WALL |
| 23-07246-NEWC | 6115189 | 10 | 2-A-WALL, A-WALL |
| 24-16471-RNVS | 7286266 | 29 | A - WALLS - EXTERIOR.3D, A - WALLS - INTERIOR.3D |
| 19-37598-RNVS | 4712453 | 16 | A-2 HOUR WALL, A-EXTERIOR WALL, A-NEW WALL |

Plus 8 TRUTH_AREA pages (4 permits, flattened/no layers) and 2 canary pages
(bank 14-11290-NEWC doc 1494156 p3, hotel 17-35590-RNVS doc 3523243 p9) --
89 pages extracted total.

## Phase 1 -- feature extraction

**Ops note (honest, part of the record):** the task directed moving
extraction to a RunPod CPU pod (16 vCPU, $0.48/hr) for speed. That pod
(`oaotz1jcd6d5nl`) booted to `desiredStatus=RUNNING` but its container never
actually came up (SSH returned `container not found` after 5+ minutes,
`claude-repo/probe30_features/` had zero objects) -- exactly the "pod
created != pod working" failure mode in the improvement-loop skill. Per the
skill's own rule ("demand output within 15 minutes or terminate") and a
mid-task coordinator correction that independently caught the same idle-pod
symptom, the pod was **terminated and verified gone**, and extraction ran
locally instead (2 vCPU) -- slower (~13 min for 89 pages) but correctness-
and cost-verified (no idle billing).

Per-page features (probe25 lineage + the two directed fixes), cached as
`data/probe30/features/<tag>.npz` and synced from R2
`claude-repo/probe30_features/`:

- **RAW** (probe25's exact 9, unchanged -- the ablation baseline
  reproduction): `norm_length, angle_rel_dom_deg, stroke_width, fill_flag,
  dash_flag, nearest_parallel_dist_norm, local_density,
  dist_from_margin_norm, collinear_chain_len_norm` -- all page-width-relative,
  raw point stroke width.
- **FIXED** (probe30, both directed fixes applied): stroke width ->
  **per-page percentile rank** (not raw points); length / nearest-parallel-
  dist / local-density-radius / margin-dist / collinear-chain-len -> **real
  feet** via the page's own fpp (parsed directly off the downloaded PDF's
  text, vision skipped per spec) where derivable, else the same page-width
  fallback probe25 used; plus one new `has_scale` flag (1 if a real scale
  regex matched, 0 if fallback) so the model can condition on units regime.

**Budget guard**: pages >150k segments have non-wall segments downsampled
to keep total <=150k (wall segments always kept in full) -- hit on
24-07484-NEWC (only page needing it). **Disk**: feature cache totals **190MB**
(well under the ~1.5GB ceiling); PDFs (up to 39MB each, avg ~21MB) were
downloaded and deleted per-page throughout, disk stayed flat at ~3.2-3.4GB
free system-wide the entire run. One race bug found and fixed (documented
in the script, not re-run since all 89 pages already banked): two worker
*processes* sharing a doc-id-keyed tmp path for a 4-page doc
(24-06748-RNVS/7372349) -- one process deleted the PDF while a sibling
process for a different page was still reading it. Fixed by keying the tmp
path with the PID too.

## Phase 2 -- training, segment-level PR-AUC

`HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_depth=6,
class_weight="balanced")`, trained on all 69 train permits' segments
(3,918,461 segments, 8.3% wall-labeled), threshold chosen by best-F1 on
train only (canonical = **0.80**).

### FIXED-features model vs probe25 baseline (0.11-0.13)

| holdout permit | PR-AUC | n_segs | wall% |
|---|---|---|---|
| 16-03048-NEWC | 0.978 | 106,730 | 5.2% |
| 16-03038-NEWC | 0.922 | 87,726 | 2.9% |
| 22-07153-RNVS | 0.529 | 22,399 | 7.4% |
| 25-15704-NEWC | 0.364 | 49,622 | 9.3% |
| 24-16471-RNVS | 0.378 | 130,253 | 30.4% |
| 23-07246-NEWC | 0.406 | 17,659 | 27.8% |
| 19-37598-RNVS | 0.270 | 24,449 | 4.1% |
| 19-27788-NEWC | 0.229 | 17,197 | 12.8% |
| 24-07484-NEWC | 0.126 | 150,000 (sampled) | 1.1% |
| 23-17834-RNVS | 0.100 | 64,881 | 4.0% |

**Pooled holdout PR-AUC = 0.340, median per-permit = 0.371, spread
0.100-0.978.** This is a real, meaningful jump over probe25's 0.11-0.13
(roughly 3x on the pooled number) -- 79 permits of firm diversity clearly
helps vs probe25's 3. But the spread is enormous: two permits (both in the
"1-A-WALL" naming family, which has 7 OTHER members in train) score
>0.92, while permits with rarer/unique conventions score at or barely above
random (0.10-0.27) -- the same firm-specific-shibboleth failure mode probe25
diagnosed, just averaged out better with more data, not eliminated.

### Ablation: fixes vs raw (probe25) features

| | pooled holdout PR-AUC | median per-permit |
|---|---|---|
| FIXED (bucketed stroke width + feet distances) | 0.340 | 0.371 |
| RAW (probe25 exact, unbucketed width, width-normalized dist) | **0.359** | **0.423** |

**The directed fixes do NOT help on this larger dataset -- if anything, raw
features score slightly HIGHER.** This is a genuine negative sub-result,
reported honestly rather than suppressed: probe25's hypothesis (raw stroke
width is a per-firm shibboleth; bucketing/feet-normalizing should generalize
better) does not hold up once training sees enough firms for the model to
partially average out the raw-width shibboleth on its own. `wall_model_v2.joblib`
(shipped model) still uses the FIXED features per the task spec, but this
ablation result should inform any v3 feature work -- percentile-bucketing
stroke width may be *removing* signal (exact width DOES correlate with wall
class within a firm, and generalizes somewhat via ensembling across enough
firms) rather than adding firm-invariance.

### Learning curve (15/30/45/60/69 train permits, same holdout, same seed=42 shuffle)

| N train permits | pooled PR-AUC | median PR-AUC | downstream matched_frac (of 575 true rooms, 4 gradable holdout permits) |
|---|---|---|---|
| 15 | 0.380 | 0.408 | 0.3% (2/575) |
| 30 | 0.393 | 0.406 | 3.7% (21/575) |
| 45 | 0.387 | 0.356 | 9.7% (56/575) |
| 60 | 0.315 | 0.379 | 2.3% (13/575) |
| 69 (all) | 0.338 | 0.382 | 3.8% (22/575) |

**FLAT, not climbing** -- both the segment PR-AUC and the downstream
matched-room fraction bounce around noisily with no monotonic trend (in
fact N=60 is the worst point on both metrics, then N=69 partially recovers).
Per the improvement-loop skill's own decision rule ("still climbing -> get
more data; flat -> engineer"), **this result says ENGINEER, not "download
more permits."** More permits of the same feature vocabulary are not
reliably buying accuracy at this scale.

## Phase 3.1/3.2 -- downstream vs the permits' OWN layer-truth (10 holdout permits)

Model wall mask (train-chosen threshold=0.80) -> `geometry_model.py`'s
model-as-engine (v2 gap-closer/cavity-filter + v4 anchor-cluster proximity
reconnection, REUSED UNCHANGED from the rules engine, only wall-candidate
selection differs) -> rooms compared to polygonizing the TRUE wall-LAYER
segments directly (same page, same scale).

**6 of 10 holdout permits could not be graded at all: `scale_unverified`**
(no scale note found by direct-PDF-text regex on that specific page --
these permits' scale strings likely live in a title-block image or a format
variant the regex misses, matching probe25's own 26-10321 finding). Per the
sf-extraction skill's hard rule, **no output was produced for those 6
pages** rather than guessing a scale.

Of the **4 gradable** holdout permits (25-15704, 24-16471, 23-07246,
19-27788 -- 575 true rooms combined):

| permit | true rooms | pred rooms | matched | missed | merged_ok | merged_err | true SF | pred SF | extra/fabricated SF |
|---|---|---|---|---|---|---|---|---|---|
| 25-15704-NEWC | 150 | 18 | 12 | 132 | 1 | 1 | 13,138 | 2,959 | 1,954 |
| 24-16471-RNVS | 98 | 5 | 0 | 98 | 0 | 0 | 8,583 | 1,840 | 1,840 |
| 23-07246-NEWC | 52 | 14 | 1 | 40 | 0 | 3 | 3,606 | 6,797 | 3,148 |
| 19-27788-NEWC | 275 | 17 | 2 | 185 | 10 | 1 | 32,839 | 9,723 | 170 |
| **TOTAL** | **575** | **54** | **15** | **455** | **11** | **5** | **58,166** | **21,320** | **7,112** |

**Matched fraction = 15/575 = 2.6%; missed = 79.1%; total predicted SF is
-63% vs true.** This is a stark negative result, consistent with probe25's
original diagnosis: even a 3x segment-PR-AUC improvement does not survive
snap/close/polygonize against unseen firms' real building geometry -- most
of the model's precision comes from a handful of firms with lots of train
representation, and the polygonizer needs high, consistent recall across an
ENTIRE building's wall run to close real rooms, not just a locally-decent
classifier.

## Phase 3.3 -- THE PROMOTION GATE: TRUTH_AREA product test vs rules-v4

Same 4 TRUTH_AREA answer-key permits/pages/anchoring/grader fixes (3-6) as
probes 26-29, imported verbatim -- only geometry engine swapped
(`geometry_model.run_geometry_engine_model`, same threshold=0.80).

| | rules-v4 (published) | **model (this probe)** |
|---|---|---|
| % addressable rooms missed | 33.5% | **26.4%** |
| # matched rooms with <=30% error | 7 | **29** |
| median abs %% error, matched rooms | 30.6% | **24.6%** |

(n_addressable_total = 182, matching the skill's own published denominator
-- confirms this is the same population, valid comparison.)

Per-permit breakdown (model engine):

| permit | addressable | matched | matched<=30%err | missed | median err% |
|---|---|---|---|---|---|
| 24-06233-RNVS | 34 | 6 | 5 | 8 (23.5%) | 24.4 |
| 20-29653-RNVS | 44 | 20 | 11 | 8 (18.2%) | 26.6 |
| 24-06748-RNVS | 36 | 2 | 1 | 18 (50.0%) | 47.8 |
| 26-05332-NEWC | 68 | 22 | 12 | 14 (20.6%) | 22.6 |

**The model beats rules-v4 on all three published columns, on the identical
grader.** But it is NOT uniformly better: 24-06748-RNVS is markedly WORSE
under the model (2/36 matched vs rules-v4's own published 5/36 on this same
permit) while 20-29653-RNVS and 26-05332-NEWC are dramatically better (20/44
and 22/68 matched vs single digits under rules). The aggregate win is real
but driven by 2 of 4 permits, not a uniform improvement -- worth knowing
before treating "beats rules-v4" as settled across all building types.
Dimension-string grading tables (per-room bbox vs printed dimension
strings, confirming scale) and overlay PNGs for every page are in
`data/probe30/product_test/results_model.json` /
`data/probe30/product_test/overlay_*_model.png`.

## Phase 3.4/3.5 -- learning curve read (repeated from above) + canaries

**Canaries (smoke test only, no truth key for hotel):**
- **Bank** (14-11290-NEWC doc 1494156 p3): ran, no crash, sane bounds --
  but only **1 room closed** (48 sf) and 1/18 known room anchors matched.
  The model badly under-recovers this page (dense CMU/stud bank branch);
  most anchor-less islands got killed by the anchor-cluster filter.
- **Hotel** (17-35590-RNVS doc 3523243 p9): ran, no crash, sane bounds --
  **18 rooms closed, 4,054 sf, 15/17 keynote-derived anchors matched.**
  Plausible recovery on this dense stress-test page.

Both canaries are technically "PASS" as a smoke test (no crash, sane
numbers) but the bank result underscores the same firm-variance problem
seen in the segment PR-AUC table -- this exact permit is architecturally
similar to some training permits in stroke convention but the model still
collapses to near-zero recall on it.

## Promote/park reasoning

The improvement-loop skill's decision gate is literal: *"model beats
rules-v4 on flattened/held-out permits -> promote into takeoff.py as the
layerless path."* That condition is met, on the exact required test
(TRUTH_AREA, same grader, same denominator as the published rules-v4 numbers).

But three other honest signals argue against an unconditional, wholesale
swap the way v1->v4 was for the rules engine:

1. **Thin sample, high variance.** The promotion-gate win is 4 permits/182
   rooms, and per-permit it is a 2-of-4 story (2 permits much better, 1
   permit clearly worse, 1 roughly a wash) -- not evidence the model
   generalizes uniformly across building types yet.
2. **The stricter downstream check (permits' own layer-truth, 10 unseen
   firms) is a near-total miss** -- 2.6% of real rooms recovered. The
   TRUTH_AREA win and this result are not contradictory (different grader
   strictness, different permits, and TRUTH_AREA's grader carries five
   rounds of accumulated forgiveness fixes -- confident-wrong guard, merge-
   scoring fix, unit-merge guard, review-killed routing -- tuned ON these
   same 4 permits across probes 26-29), but both are real and the second
   one is the more architecture-agnostic test of "does this recover real
   building geometry."
3. **Flat learning curve + the ablation wash.** Neither more data (at this
   feature vocabulary) nor the directed feature fixes reliably move the
   needle. Promoting now and declaring victory would remove the pressure to
   do the feature/architecture work the flat curve says is actually needed.

**Recommendation: CONDITIONAL PROMOTE.** Ship `wall_model_v2` behind a flag
as a SECOND candidate engine alongside rules-v4, not a replacement:
- Run both engines on layerless permits; where they agree (or the model's
  own per-page diagnostics -- `pred_wall_frac`, island/anchor counts -- look
  healthy), prefer whichever closes MORE matched rooms; where they disagree
  sharply, route to review rather than silently trusting either.
- Do NOT retire rules-v4 as the default given the 24-06748 regression and
  the 2.6%-matched holdout number.
- Before a second promotion attempt: prioritize the "engineer, not more
  data" branch -- try firm-invariant feature ideas the flat curve rules out
  simple scaling for (e.g. per-page unsupervised width/spacing clustering as
  probe25 itself suggested as a cheaper baseline never yet tried; small
  local image-patch features; or an explicit per-firm-normalization step
  instead of the percentile bucketing that this probe's ablation showed
  doesn't help).

## Known limits / honest gaps

- Sibling floor-plan pages were excluded from training (documented above) --
  a real, deliberate scope cut for contamination-safety, not an oversight.
- 6 of 10 holdout permits could not be downstream-graded (`scale_unverified`)
  -- the 4-permit downstream table is real but a smaller sample than hoped;
  page-text scale-regex coverage is the binding constraint, same gap probe25
  flagged for 26-10321.
- No apples-to-apples rules-v4 number exists yet on the SAME 10 holdout
  permits using the SAME simple overlap-match grader used for the layer-
  truth downstream check (only the TRUTH_AREA comparison is apples-to-apples
  with rules-v4, since that reuses the identical grader). A follow-up that
  runs rules-v4 through `probe30_downstream.py`'s match_rooms on the same 10
  permits would sharpen the "model vs rules on held-out layered permits"
  comparison -- flagged as a gap, not fabricated here.
- `data/probe30/features/` (190MB) and PDFs are NOT deleted from R2
  (`claude-repo/probe30_features/`) -- they are the resumable cache the task
  spec asked for; local copies stay under the ~1.5GB ceiling this session,
  but a future extractor run appending more permits should re-check that
  budget.
