# Probe 25 — first vector wall-segment classifier baseline (NEGATIVE RESULT)

**Date:** 2026-07-09
**Script:** `scripts/probe25_wall_classifier.py`
**Artifacts:** `data/probe25/` (7 overlay JPGs, `results.json`, `_features_cache/*.npz`
— cached per-page feature matrices so re-runs don't re-download PDFs)

**Hypothesis under test:** a classifier using only layer-free geometric features
can identify wall segments in vector floor plans well enough that the existing
snap_and_close → polygonize pipeline still closes rooms on the *predicted*
walls — i.e., ML could replace named CAD layers on the ~82% of PDFs that are
layerless.

**Verdict: NO, on this data.** Segment-level PR-AUC on held-out permits is
0.11–0.13 — at or below the base wall-rate (0.03–0.18), i.e. **no better than
chance** across firms. Downstream, the polygonizer does not survive predicted
walls on 4 of 7 test pages (zero rooms close at all) and produces badly wrong
geometry on the other 3 (0–2 of the true rooms recovered, SF delta -84% to
+94%). The in-sample fit is excellent (PR-AUC 0.999 within-permit) — so this
is not a bug in the features or pipeline, it's a **generalization failure**:
the features that discriminate walls are firm-specific drawing conventions,
not universal wall geometry.

---

## Setup

**Labels (free, from CAD layers):** `page.get_drawings()["layer"]` →
`probe8_layer_classes.classify_layer()` → 1 if `"wall"` else 0. Layer info was
used ONLY to build labels/truth polygons, never as a model feature.

**Candidate pages, screened by eyeball + a closure test** (not just segment
count — see probe24's "layered ≠ geometry-usable" finding):

| permit | doc | page(s) | layers | verdict |
|---|---|---|---|---|
| 14-11290-NEWC | 1494156 | 3 | 03-CMU, 05-METAL STUD WALLS | **KEEP** — clean centerlines, known-good (probe7) |
| 26-10321-RNVN | 9058456 | 14,15,16,17,18 | NEW WALL / EXIST WALL (2D) | **KEEP** — clean 2D, known-good (probe24); 5 sibling floors of ONE permit, kept in a single LOPO fold |
| 23-05848-RNVS | 7888241 | 0 | A-WALL, A-WALL-EXT, STUD | **KEEP** — eyeballed clean; closure test: 258 long segs → largest_frac 0.239, coverage 0.31 (best of the untested candidates) |
| 20-21673-RNVS | 4511408 | 8 | layers literally named `*_HATCH*` (`BASE_WALL_INT_HATCH_NEW`) | **EXCLUDED** — hatch representation per its own layer name; closure test confirms: 168 long segs → largest_frac 0.018 |
| 19-00670-RNVS | 5101148 | 5 | A-Wall | **EXCLUDED** — looks like clean centerlines at a glance (rendered overlay is visually gorgeous, dense apartment-grid linework), but closure test exposes the same failure signature as the excluded 25-33341 `.3D` solid: 15,049 raw segments on ONE wall layer → 7,022 polygon fragments, largest single room only 67 sqft on a ~7,100 sqft footprint. Corners/junctions don't share vertices — bad wall *representation*, not bad tolerance. This is a genuinely useful negative catch: **segment-count and even a quick visual are not enough; the closure test is load-bearing.** |
| 25-33341-NEWC, 24-22310-RNVN | — | — | `.3D` solid / hatch | excluded per task spec (already known-bad from probe24) |

Net training data: **3 permits, 7 pages, 427,150 total vector segments**
(2.7%–25% wall-labeled depending on page — heavily imbalanced).

**Extraction:** ALL `"l"` (line) items from `page.get_drawings()` on the
ORIGINAL PDF, plus thin filled-rect centerlines (walls-as-fill convention,
same as probe2/probe7). Curves (mostly door-swing arcs) excluded — not wall
candidates.

**Features (9, geometric only, no layer leak):**
`norm_length` (÷ page width), `angle_rel_dom_deg` (deviation from the page's
dominant wall-axis pair, 0–45°), `stroke_width`, `fill_flag`, `dash_flag`,
`nearest_parallel_dist_norm` (KDTree in rotated normal/tangent coords per
dominant-axis frame — proxy for the double-line wall-pair offset),
`local_density` (segment count within 2% page-width via `cKDTree` radius
query), `dist_from_margin_norm`, `collinear_chain_len_norm` (union of
segments sharing a near-identical offset line, merged along the tangent with
a gap tolerance — proxy for "is this part of a long wall run").

**Model:** `sklearn.HistGradientBoostingClassifier` (`class_weight="balanced"`,
200 iters, depth 6). **Eval:** leave-one-**permit**-out (never by page, per
CLAUDE.md) — 3 folds. Threshold chosen by best-F1 on the training fold only
("canonical"); a 9-point sweep (0.1–0.9) is reported for the held-out fold.

---

## Segment-level results (leave-one-permit-out)

| held-out permit | train segs (wall%) | test segs (wall%) | canonical t | precision@t | recall@t | **PR-AUC** | base rate |
|---|---|---|---|---|---|---|---|
| 14-11290-NEWC | 296,270 (17.9%) | 130,880 (2.7%) | 0.65 | 0.121 | 0.077 | **0.133** | 0.027 |
| 23-05848-RNVS | 422,929 (13.3%) | 4,221 (9.5%) | 0.75 | 0.000 | 0.000 | **0.113** | 0.095 |
| 26-10321-RNVN | 135,101 (2.9%) | 292,049 (18.0%) | 0.90 | 0.215 | 0.010 | **0.117** | 0.180 |

PR-AUC of 0.11–0.13 is barely above (23-05848: *below*) the naive base rate —
**the model is not meaningfully separating wall from non-wall segments on an
unseen firm's drawings.** Full threshold sweeps are in `data/probe25/results.json`
(`threshold_sweeps`); none reach usable precision/recall jointly (e.g. 14-11290's
best point is ~13% precision at 26–33% recall).

**Sanity check (not a claim of correctness, a bug check):** pooling all 3
permits and testing in-sample (train==test) gives PR-AUC **0.999** — the
model fits fine; the features clearly *can* separate wall from clutter within
a firm's own drawing conventions. Permutation importance on the pooled model:
`stroke_width` (+0.178) and `nearest_parallel_dist_norm` (+0.101) dominate;
everything else contributes <0.03. That is the mechanism of the failure:
**stroke_width is close to a per-firm constant** (each office draws walls at
one or two specific point-widths), so the model partly learns "walls in THIS
office's PDF are exactly 0.24pt wide" — a shibboleth, not a wall detector.

**Ablation ruled out:** re-normalized the scale-dependent features
(`norm_length`, `nearest_parallel_dist`, `local_density` radius,
`dist_from_margin`, `collinear_chain_len`) from page-width fractions to real
feet using each page's actual printed scale (0.0556 ft/pt for the 1/4" pages,
0.1111 ft/pt for 26-10321's 1/8" pages, vision-verified in probe24). **This
did not help** — held-out PR-AUC stayed at 0.07–0.13. So the failure is not
simply "different sheets have different point-per-foot scales confusing a
page-width-normalized feature"; the underlying geometric conventions
(stroke widths, parallel-offset drafting habits) genuinely differ firm to
firm in a way 3 permits' worth of examples can't average out.

---

## Downstream: does the polygonizer survive predicted walls?

Ground truth here = polygonize on the TRUE wall-class segments only (not
probe7/24's broader WALL_RE which also folds in door/window/glazing layers to
help closure — that's a deliberate difference: per the task spec, "wall"
label = `classify_layer()=='wall'` strictly, so these true-room numbers are
lower coverage than probe7/24's own published figures for the same buildings.
That's an artifact of the strict label definition, not a new geometry
finding — flagged here so it isn't misread as a regression.)

| test page (permit) | scale | true rooms | pred rooms | **recovered** | true SF | pred SF | **SF delta** |
|---|---|---|---|---|---|---|---|
| 14-11290-NEWC p3 | 1/4"=1'-0" (regex) | 7 | 8 | **2/7** | 548 | 1,065 | **+94.3%** |
| 23-05848-RNVS p0 | 1/4"=1'-0" (regex) | 15 | **0** | **0/15** | 1,421 | 0 | **-100%** |
| 26-10321-RNVN p14 | 1/8"=1'-0" (probe24, vision) | 45 | 9 | **0/45** | 3,094 | 502 | **-83.8%** |
| 26-10321-RNVN p15 | 1/8"=1'-0" (probe24, vision) | 44 | **0** | **0/44** | 4,585 | 0 | **-100%** |
| 26-10321-RNVN p16 | 1/8"=1'-0" (probe24, vision) | 40 | **0** | **0/40** | 3,027 | 0 | **-100%** |
| 26-10321-RNVN p17 | 1/8"=1'-0" (probe24, vision) | 35 | **0** | **0/35** | 3,026 | 0 | **-100%** |
| 26-10321-RNVN p18 | 1/8"=1'-0" (probe24, vision) | 47 | **0** | **0/47** | 4,334 | 0 | **-100%** |

Matching rule: centroid containment + area within ±20% (per task spec). On 4
of 7 pages the predicted-wall graph doesn't close *anything* room-sized at
all. On the 3 pages that do close something, the closures are wrong shape —
either one giant merged blob spanning several real rooms (14-11290: predicted
polygon covers Office 107 + Conference 108 + Office 109 as one 1,065 sqft
blob against 7 much smaller true rooms, +94% oversized) or a scatter of tiny
disconnected fragments (26-10321 p14: 9 fragments averaging 56 sqft vs true
rooms averaging 69 sqft, but in the wrong places — 0 matched).

**Overlay images** (green outline = true room from the wall-class layer,
red fill = polygon from predicted walls at the canonical threshold):
- `data/probe25/overlay_14-11290-NEWC_1494156_p3.jpg` — the merged-blob failure mode, visually obvious
- `data/probe25/overlay_23-05848-RNVS_7888241_p0.jpg` — zero predicted closure
- `data/probe25/overlay_26-10321-RNVN_9058456_p14.jpg` through `_p18.jpg` — zero-to-near-zero closure across all 5 sibling floors

**Binding failure:** the segment classifier itself. Even a perfect
downstream polygonizer can't rescue a wall mask that's ~10-20% precision and
~1-8% recall on an unseen firm — too many false positives (random clutter
picked up as "wall") corrupt the graph into either over-merged blobs or
under-connected fragments, and too much recall is missing to trace full wall
runs. This is exactly the risk flagged (but not yet measured) in
`experiments/ML_ARC_layers_to_product.md` risk #2: *"Firms draw differently"*
— now with a number: **3 permits is not enough for the model to learn a
firm-invariant wall signal**, and the two features doing most of the work
(stroke width, parallel-offset habits) are precisely the ones most likely to
be firm-specific conventions rather than universal wall geometry.

---

## Honest limits

- **This is a 3-permit feasibility smoke test, not a generalization claim.**
  With only 2 training permits per fold, the model has no chance to average
  out firm-specific stroke-width/offset conventions — this result says
  "3 permits failed to generalize," not "geometric wall classification is
  impossible."
- The closure/eyeball screening that dropped 19-00670 and 20-21673 leaves a
  very small, non-random training pool (both survivors happen to be smaller
  commercial buildings; 26-10321's 5 pages are all one office-reno firm's
  style, so the "3 permits" is really closer to "2 independent drawing
  styles" for the purposes of the double cross-check on generalization).
- Ground-truth room counts here undercount real building coverage because
  `classify_layer()`'s strict `"wall"` class excludes door/window layers that
  probe7/24 folded in to help closure — a deliberate, documented choice per
  the task spec, not a new finding about these buildings.
- 26-10321's scale note isn't regex-parseable from `pagetext` (probe24 already
  found this — the note lives on a trimmed sheet edge); reused probe24's
  vision-verified value here rather than re-deriving it, so those 5 rows'
  SF numbers are trustworthy even though the regex path is a known gap.
- Collinear-chain and nearest-parallel features are two hand-rolled
  approximations (grid-bucket + gap-tolerance heuristics), not an exact
  reimplementation of the spec's prose — documented in the script's
  docstring; a v2 of this probe should validate them independently before
  trusting the importances.

## What I'd do next

1. **Don't scale this approach up yet.** Downloading more layered permits to
   get from 3 to 10+ training permits is the obvious next step *before*
   concluding the method is dead — the in-sample PR-AUC of 0.999 says the
   features are informative, just not (yet) firm-invariant with this little
   data. This directly matches probe24's "go-wider" recommendation for an
   unrelated reason (geometry-usable supply) — now there's a second reason to
   go wider: **training-permit diversity for the wall classifier**.
   Sub-$5 spend estimate: this is compute-cheap (single CPU HistGB fit is
   seconds); the cost is in enumerate+download+closure-gate labor, already
   the plan.
2. **Try firm-invariance-friendly features before adding more data**: drop or
   heavily discretize `stroke_width` (bucket into "thin/medium/thick" tercile
   *within the page* rather than raw point value) and drop the raw
   `nearest_parallel_dist` in favor of a ratio (offset ÷ page's own dominant
   wall-width estimate) — both changes aimed squarely at removing the
   per-firm absolute-scale shibboleth the importance analysis flagged.
3. **Segment classification may be the wrong ML target.** Given walls in
   these files are usually drawn with a small number of distinct stroke
   widths *per page*, a per-page unsupervised width/spacing clustering
   (no ML, just k-means on stroke width + local density) might already beat
   this supervised cross-firm model — worth a quick baseline comparison
   before investing further in the classifier route.
4. If go-wider produces ~10 permits, rerun this exact script (feature cache
   keys are per-page, so only new pages need extraction) and watch whether
   held-out PR-AUC climbs meaningfully; if it plateaus below ~0.5, that's a
   stronger signal the geometric-feature vocabulary itself (not just data
   volume) needs rethinking (e.g. add small local image patches / a light
   CNN over the flattened raster, closer to the U-Net idea already scoped in
   `ML_ARC_layers_to_product.md`, rather than pure hand-engineered geometry).
