# Probe 30b -- dataset audit: how many distinct firms does the roster really have?

**Date:** 2026-07-10
**Trigger:** Nick challenged probe 30's "flat learning curve => features are the
ceiling" read: if the 69 train permits are dominated by near-duplicate permit
families, the flat curve could mean "duplicates add nothing," not "features hit
their ceiling."
**Scripts:** `scripts/probe30b_fetch_pagetext.py`, `probe30b_architects.py`,
`probe30b_cluster.py`, `probe30b_labelcheck.py`
**Artifacts:** `data/probe30b/{clusters.csv, architects.csv, firm_signals.csv,
pagetext_cache/, labelcheck_*.png}`
**Method note:** all 79 roster PDFs re-fetched from R2 (GET only), title-block
text extracted from the exact roster page, PDFs deleted per-doc (disk stayed
~3.2GB free). Firm identity adjudicated from: shared phone numbers in title
blocks (best fingerprint), firm names, shared address blocks, shared drawing
boilerplate, wall-layer dialect, and identical closeability geometry. City
plan-review stamp "Jay P. Dufour, AIA -- Chief Plans Examiner" appears on 9
permits and was explicitly EXCLUDED (it is the reviewer, not the architect --
a trap for anyone repeating this).

---

## 1. Firm clustering: 79 permits -> 49 distinct clusters

Union-find over three evidence types: (a) normalized wall-layer signature
(floor prefixes stripped; hyper-generic sigs like bare `A-WALL` excluded, and
sig merges blocked when title-block architects were proven different),
(b) adjudicated architect identity, (c) near-identical closeability geometry
(n_mid / cov_mid / largest_frac / n_wall_segs within 2-5%).

**49 clusters. Histogram: 42 singletons, 2 pairs, 1x4, 1x4, 1x5, 1x6, 1x14.**
37 of 79 permits (47%) sit inside a multi-permit family.

| cluster | n | firm (evidence) | members |
|---|---|---|---|
| C00 | **14** | C. Spencer Smith "Architects, LLC", 1018 Bienville St (phone 504.566.0585 on all 14) | 16-03038/39/41/48/50/51/56/57/59, 21-13581, 23-07246, 24-07484, 24-10183, 25-15704 |
| C01 | 6 | LKHarmon Architects (LKH job#, (c) notice, shared boilerplate, A-WALLS-EXIST/NEW/FILL dialect) | 17-09557, 21-03616, 21-12939, 23-01467, 24-34189, 26-01742 |
| C02 | 5 | unknown firm(s) -- Chief Architect software dialect (WALLS-HIDDEN default layers); title blocks are logo images | 20-40972, 24-03784, 24-17669, 26-01103, 26-16782 |
| C03 | 4 | unnamed firm, phones 504.234.3005/504.865.8746 -- Prytania St rowhouses, all four docs geometry-IDENTICAL | 13-44115/21/24/26 |
| C04 | 4 | metrostudio (6501 Spanish Fort Blvd, 504.283.3685) | 17-09477, 22-34220, 24-19337, 24-16471 |
| C05 | 2 | terrell-fabacher architects llc (504.566.1320) | 19-37598, 23-14416 |
| C06 | 2 | LACHIN Architects, apc | 23-27953, 24-31588 |

Named singletons include: WB Architects, Foil Wyatt, MZ Architecture, Studio
BKA, John C Williams, Spec Designs, KKJohnson, Farouki Farouki, ADB Design,
Chicago Building Design, Angela Morton, Julien Engineering, Dammon Engineering.

**Near-duplicate geometry (same design refiled):** 3 refile families found.
Spencer Smith's Villages-of-Versailles townhouse series is TWO designs filed
as 10 permits: design A (n_mid=20, 592 wall segs, IDENTICAL to 4 decimals) =
16-03048/50/51/56/57/59 + 21-13581 (7 permits, refiled again 5 years later);
design B (n_mid=17, 241 segs) = 16-03038/39/41. The Prytania rowhouses (C03)
are ONE design filed 4x. **Unique-design count: 68 of 79 nominal (train: 60
of 69).**

**Effective dataset size: nominal 79 permits = 49 firm-clusters = 68 unique
designs. Train 69 permits = 46 clusters = 60 designs.**
(Range note: treating C02 as up to 5 separate firms and re-splitting the two
demoted ambiguous sig-pairs would put the ceiling at ~55 clusters; 49 is the
best-evidence figure.)

## 2. Learning curve re-read in distinct-firm units

Recovered the trainer's exact seed-42 subsets from
`segment_results.json.learning_curve[].permits`:

| N permits | distinct clusters | pooled PR-AUC | median PR-AUC |
|---|---|---|---|
| 15 | 13 | 0.380 | 0.408 |
| 30 | 24 | 0.393 | 0.406 |
| 45 | 33 | 0.387 | 0.356 |
| 60 | 41 | 0.315 | 0.379 |
| 69 | 46 | 0.338 | 0.382 |

**Firm diversity DID grow, steadily and ~linearly (13 -> 46 clusters, 3.5x),
while the curve stayed flat.** Nick's specific alternative hypothesis --
"the flat curve just means firm diversity never actually increased between
N=15 and N=69" -- is NOT supported by the measurement. The curve points are
nearly as diverse (clusters/permits ~0.87 at N=15, ~0.67 at N=69) as the
roster allows. Adding 33 NEW distinct firm-clusters between N=15 and N=69
bought ~nothing on the holdout metric. That *reinforces* probe 30's
"engineer, don't just add data" conclusion -- with one big caveat, below.

## 3. Holdout audit: the split leaked -- 7/10 holdouts have train siblings

Probe 30 chose holdouts for signature *variety within the holdout*, not for
cluster-disjointness from train. Result:

| holdout | PR-AUC | cluster | train siblings | sibling type |
|---|---|---|---|---|
| 16-03048-NEWC | 0.978 | C00 | 9 | **SAME DESIGN refiled** (6 geometry-identical train copies incl. 21-13581) |
| 16-03038-NEWC | 0.922 | C00 | 9 | **SAME DESIGN refiled** (2 identical train copies) |
| 22-07153-RNVS | 0.529 | -- | 0 | none |
| 23-07246-NEWC | 0.406 | C00 | 9 | same firm, different building |
| 24-16471-RNVS | 0.378 | C04 | 3 | same firm (metrostudio), ArchiCAD variant |
| 25-15704-NEWC | 0.364 | C00 | 9 | same firm, different building |
| 19-37598-RNVS | 0.270 | C05 | 1 | same firm (terrell-fabacher) |
| 19-27788-NEWC | 0.229 | -- | 0 | none (out-of-state chain design) |
| 24-07484-NEWC | 0.126 | C00 | 9 | same firm, different building |
| 23-17834-RNVS | 0.100 | -- | 0 | none |

- 5 of 10 holdout permits are ONE firm (Spencer Smith), the same firm as 9
  train permits. 2 of those 5 are literally the same townhouse design that
  sits in train in triplicate/sextuplicate.
- **Three-way split quantifies what memorization is happening:**
  same-design refile (n=2): 0.92-0.98; same-firm-different-building (n=5):
  median 0.364 (0.126-0.406... 0.378 incl. C04/C05); no sibling (n=3): median
  0.229 (0.100-0.529). Same-FIRM siblings barely beat no-sibling permits
  (0.36 vs 0.23 median, overlapping ranges -- 24-07484 scores 0.126 *despite
  9 same-firm train permits*). **The model memorizes DESIGNS (documents), not
  firm dialects.** "Dialect memorization" is real but shallower than probe 25
  claimed: it transfers almost nothing even within a firm when the building
  changes.
- **Honest pooled number: dropping just the 2 refile holdouts (29% of pooled
  segments) cuts pooled holdout PR-AUC from 0.340 to 0.214.** The published
  "3x better than probe25's 0.11-0.13" is really ~1.8x on uncontaminated
  permits.
- The flat curve is also partly a saturation artifact: both refile holdouts
  already had same-design siblings in train at N=15 (2 copies of the
  16-03048 design, incl. 21-13581). The easy 29% of the pooled metric was
  "solved" at the first curve point; nothing later could move it.

## 4. Label-quality spot check (6 permits, 6 clusters)

Rendered each roster page raster with the y=1 (wall-layer) training segments
overlaid in red: `data/probe30b/labelcheck_<permit>_{full,crop}.png`.

| permit | cluster | page actually is | wall-label quality |
|---|---|---|---|
| 13-44124-NEWC | C03 | real floor plan (A1.2 rowhouses) | **CLEAN** -- walls only, good coverage; best of the six |
| 22-34220-RNVS | C04 metrostudio | real floor plan (cafe) | new partitions labeled; **existing masonry walls (thick gray poche) NOT labeled** -> wall-looking segments carry y=0 |
| 16-03050-NEWC | C00 SpencerSmith | **ELECTRICAL sheet E7** carrying the wall xref | wall geometry itself accurate; negative class is circuit wiring/homerun arcs, not architectural annotation; party-wall poche very thick |
| 17-09557-NEWC | C01 LKHarmon | **REFLECTED CEILING PLAN A11** | large blocks of wall-layer geometry sit OFFSET in blank space (hidden/clipped xref vectors extracted by fitz) -- red partitions floating where the raster shows nothing |
| 24-03784-RNVS | C02 ChiefArch | **POWER PLAN E6** (church) | worst of six: an offset duplicate wall-plan drawn over the notes block, long-dash WALLS-HIDDEN lines, stage/platform + spiral geometry labeled wall, while most of the sanctuary's real walls are unlabeled |
| 20-50455-RNVS | singleton | structural DEMO/STABILIZATION sheet S1.1 | `existwallfinsh` layer sweeps in door/window trim and the **spiral stair**; engineer-drawn, not architect CAD |

Cross-check against `eyeball_verdicts.csv`: these are not re-gate escapes in
the gate's own terms -- the eyeballer KNOWINGLY confirmed the RCP ("not a
floor_plan sheet but traces real wall footprint") and the power plan. The
gate criterion was "wall layer closes plausible rooms," not "architectural
floor plan." Consequence for the classifier: **3 of 6 sampled training pages
are MEP/RCP/structural sheets**, so the negative-class distribution the model
learns (wiring arcs, ceiling grids) is not the distribution it faces on real
architectural pages; and two firms' wall layers carry non-wall geometry
(stairs, platform, trim, offset hidden vectors) while two others leave real
walls unlabeled (existing-wall layers, whole existing buildings).
Contamination is firm-patterned: Spencer Smith = MEP-sheet context;
LKHarmon = offset/hidden xref vectors; ChiefArch dialect = hidden-line +
furniture-on-wall-layer; metrostudio = existing-walls-unlabeled.

## 5. Verdict

**"Engineer, don't blindly add data" SURVIVES the audit -- Nick's specific
duplicate-driven alternative is measured and rejected (clusters grew 13->46
across the curve; the curve stayed flat). But the audit sharpens WHAT to
engineer, and it is not (only) features:**

1. **The eval is measuring the wrong thing (binding constraint #1:
   evaluation contamination).** 7/10 holdouts share a firm with train, 2 are
   verbatim design refiles worth 29% of pooled segments; honest pooled
   PR-AUC on non-refile permits is 0.214, not 0.340. Any future
   feature/architecture work graded on this holdout will chase noise.
   **Fix first, costs ~an hour: rebuild the holdout cluster-disjoint using
   `data/probe30b/clusters.csv`** (keep 22-07153, 19-27788, 23-17834; swap
   the seven sibling-holdouts for singleton-cluster permits) and re-report
   the v2 baseline on it. Labels are append-only; the split file is not --
   this touches only probe machinery.
2. **Label hygiene is a real, newly-quantified constraint (#2: label noise
   in y itself).** 4/6 sampled pages have contaminated wall layers (offset
   hidden vectors, stairs/platforms/trim as walls, existing walls as
   non-walls) and 3/6 train pages are MEP/RCP context. Cheap counters before
   any v3 training: drop hidden/clipped vectors at extraction time (fitz
   exposes clip state), exclude wall-layer segments that fall outside the
   page's ink bounding box, and add existing-wall layer tokens (EXIST/EXST)
   review. This is "new features/cleaning from data we already have" -- hours,
   not agent-fleets.
3. **"Add more distinct firms" comes back only in a targeted form.** The
   cluster-resolved curve says generic new-firm volume does not move the
   metric at this feature vocabulary. What the holdout table DOES show is
   that transfer to genuinely unseen dialects is the failure mode
   (no-sibling median 0.229). More data helps only if it is (a) cluster-new
   AND (b) paired with the label-hygiene fixes -- otherwise it feeds more
   contaminated y. Effective dataset today: **49 clusters (68 unique
   designs), not 79 permits.**
4. Probe 30's promotion decision (conditional, dual-engine, don't retire
   rules-v4) is unaffected -- the TRUTH_AREA gate result did not use this
   holdout. But probe 30's headline "pooled 0.340 ~ 3x probe25" should be
   read as ~0.21 / ~1.8x on uncontaminated permits.

**Cost of this audit:** ~$0 compute (local), ~80 R2 GETs (~1.7GB transfer),
disk flat, no retraining, no label rows touched.
