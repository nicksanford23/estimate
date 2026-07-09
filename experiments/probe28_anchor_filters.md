# Probe 28 -- implementing probe 27's two recommended counters, re-graded

**Date:** 2026-07-09
**Scripts:** `scripts/geometry_v3.py` (new module; `geometry_v2.py` unchanged, still
callable standalone), `scripts/probe28_regrade.py` (v3 grader), `scripts/probe28_canary.py`
(bank + hotel regression canaries, v3 variant added to probe27's).
**Before data:** `data/probe26/results.json` (v1), `data/probe27/results_v2.json` (v2)
**After data:** `data/probe28/results_v3.json` (v3) · `data/probe28/canary_results_v3.json`
**Overlays:** `data/probe28/overlay_*_v3.png` (8 pages) + `data/probe28/overlay_bank-canary_*.png`
+ `data/probe28/overlay_hotel-canary_*.png`

## What was built

1. **ANCHOR-CLUSTER MEMBERSHIP FILTER** (`geometry_v3.filter_anchor_clusters` /
   `run_geometry_engine_v3`). After v2's polygonize + cavity/hatch kill, group the
   surviving room-sized polygons into connected wall-graph components
   (`probe2_sf.cluster_by_touching` -- polygons that touch/share an edge). Any
   component containing **zero** of the page's addressable room-code anchors
   (anywhere in the component) is demoted to `ARTIFACT`: removed before grading,
   never a matching candidate, never summed as "unlabeled/fabricated" SF. A
   **false-positive detector** runs alongside it: a killed component is flagged
   `false_positive_suspect` if it contains a polygon in the 30-2000 sf room-size
   band **and** materially overlaps the "principal drawing region" (convex hull
   of every ANCHORED component, buffered 10%) -- the operational proxy for "this
   might be vectorized-label / same-building space, not a different building."
2. **UNIT/CORRIDOR MERGE GUARD** (`probe28_regrade.py`, grader-side, same
   architectural split as probe27's fixes 3/4). For every `MERGED_ERROR` row:
   - **(b) cheap re-split, tried FIRST**: recompute the page's room polygons with
     the v2 generic gap closer disabled (arcs-chords only -- `geometry_v3.
     build_arcs_only_rooms`, run once per page, not literally bbox-cropped --
     documented shortcut, see honesty section). If, inside the merged blob's
     footprint, this weaker graph produces one distinct closed sub-polygon **per
     anchor** (a true bijection), the merge is resolved into individual graded
     rows.
   - **(a) cross-unit flag, fallback**: if re-split fails, check whether the
     row's tokens span >=2 distinct unit/building families (truth schedule's own
     `building`/`unit` field, or the token's hyphen-prefix family, e.g. "A-101"
     -> "A"). If so: `MERGE_CROSS_UNIT`, excluded from auto totals (guaranteed
     wrong). Otherwise: unchanged `MERGED_ERROR`.
3. Fix 3 (confident-wrong guard) and fix 4 (merge-scoring fix) are **imported
   unchanged** from `probe27_regrade.py` per the task instruction.

## Three-way headline table (v1/probe26 -> v2/probe27 -> v3/probe28)

Same 4 permits, same 8 pages, same room-code anchoring, same truth-area answer keys
(182 addressable rooms total).

| metric | v1 (probe26) | v2 (probe27) | v3 (probe28, this probe) |
|---|---|---|---|
| missed (no polygon) | 129 (70.9%) | 61 (33.5%) | **61 (33.5%) -- unchanged** |
| matched (raw), any error | 14 | 14 | 14 -- unchanged |
| **matched, <=30% error** | 0 (0%) | 7 (50% of 14) | **7 (50%) -- unchanged** |
| median \|err\| matched | 73.3% | 30.6% | 30.6% -- unchanged |
| confident-wrong | 0 counted | 30 | 30 -- unchanged |
| merged OK (groups/rooms) | 1 / 20\* | 1 / 2 | 1 / 2 -- unchanged |
| merge SUSPECT (groups/rooms) | n/a | 3 / 10 | 3 / 10 -- unchanged |
| **merge ERROR (groups/rooms)** | 1 / 5 | 13 / 59 | **9 / 22** |
| **merge CROSS_UNIT (groups/rooms)** | n/a | n/a | **4 / 37** (NEW category) |
| merge re-split resolved (groups/rooms) | n/a | n/a | **0 / 0** (attempted on all 13, 0 succeeded) |
| median \|err\| merged-error | 809.4% | 29.2% | 30.6%\*\* |
| **fabricated/unlabeled SF** | 7,608 (100 polys) | 18,759 (158 polys) | **4,004 (65 polys)** |
| bank canary rooms closed /18 | 6 (v1 arcs-only) | 13 | **13 -- no regression** |
| hotel canary anchors matched /17\*\*\* | 16 | 16 | **16 -- no regression** |

\* v1's `merged_ok` of "20 rooms/1 group" was a different accounting quirk of the
pre-guard grader (probe27 already noted this); not directly comparable cell-for-cell,
included for continuity only.
\*\* v3's remaining 9 merge-error groups are a strict subset of v2's 13 (the 4 that
became CROSS_UNIT are removed from this population, which is why the median shifts
slightly rather than improving -- the *easiest* wrong ones (the giant cross-unit sums,
which is why they were flagged in the first place) left the population, not the hardest).
\*\*\* hotel canary anchors are NOT a truth schedule (none exists for this page) --
derived from the page's own printed decimal finish-keynote tags (e.g. "201.1"->room
"201"); a structural regression check, not a truth-area grading exercise. See caveat below.

## Fix 1 (anchor-cluster filter): the fabricated-SF lever worked -- with a real, confirmed false-positive cost

**Headline win:** fabricated/unlabeled SF dropped from 18,759 -> 4,004 SF (**-78.7%**,
158 -> 65 polygons), essentially hitting probe27's own ">80%" aspiration for the
cavity/hatch filter that fell short (28%) -- this is the lever probe27 predicted would
actually move that number, and it did, on the very mechanism probe27 diagnosed
(same-sheet other-building/other-plan blobs, e.g. the 24-06748 p7 roof-plan-shaped
polygons: 3,592.9 of that page's 3,639.2 SF of "unlabeled" polys were killed in one shot).
Zero pages regressed on self-audit (all 8 still `GRADED`), and the two canaries show
**zero loss of previously-matched rooms** (bank still closes 13/18, hotel still matches
16/17 anchors) after the filter runs.

**But the false-positive check the task demanded found a real, confirmed cost, not a
theoretical one.** My own heuristic flags 8 of 58 killed clusters across the 4 permits
(13% by SF -- 1,912 of 14,754 SF killed) as `false_positive_suspect`. I visually graded
three of these against the actual drawing (skill's verification standard: humans grade
pictures):

- **24-06233-RNVS p10, Building B's own upper-floor rooms (6-poly cluster, 1,177 SF,
  plus 3 more smaller clusters on the same page, 1,453.8 SF total on this ONE page) --
  CONFIRMED false positive.** The overlay (`overlay_24-06233-RNVS_6799291_p10_v3.png`)
  shows this cluster is plainly the rest of Building B's attic/2nd floor (Bride Lounge,
  a toilet, several other rooms) -- structurally continuous with the matched `B202`
  polygon in the SAME building's SAME drawing, just wall-graph-**disconnected** from it
  because closure is imperfect (a real partition failed to close, splitting one
  legitimate drawing into 2+ wall-graph "islands"). The filter's core assumption --
  "zero anchors anywhere in a connected component means off-scope" -- is **false**
  whenever the target building's own graph fragments, which this pipeline's entire
  premise (imperfect closure is the norm, not the exception) makes common, not rare.
- **26-05332-NEWC p8, two ~33 sf bedroom-sized rooms in units A and D (65.4 SF) --
  LIKELY false positive**, same mechanism at smaller scale (single-polygon islands
  disconnected from their own unit's anchored cluster).
- **20-29653-RNVS p3, one 345 SF area near unit boundary -- AMBIGUOUS**, plausibly a
  genuinely off-scope third area on the same sheet (not clearly part of either
  addressable unit) -- could be a correct kill.

**Diagnosis: this is a broader failure mode than the task's "vectorized labels" hypothesis.**
The task asked to watch for a legit component whose labels are vectorized (no text) being
wrongly killed. That specific mechanism may also occur, but the CONFIRMED failure here is
structural: **the same building/unit's wall graph splitting into multiple disconnected
islands is the normal failure mode of this whole pipeline** (it's why rooms get missed and
merged in the first place), so "connected component with zero anchors" is not a safe proxy
for "different building" -- it also catches "same building, badly closed."

**Trade-off I'd take:** ship the filter, but NOT as blind auto-discard. Re-route its output
from "artifact, never counted" to a **third bucket** -- `ARTIFACT_CANDIDATE` -- that is
excluded from auto-quantity sums (same practical effect on the fabricated-SF number) but
IS surfaced to a human reviewer with the false-positive-suspect flag already computed
(13% of SF, growing to near-100% on pages where the target building's rooms are numerous
and closure is bad, like 24-06233). That keeps the honest 78.7% fabricated-SF win without
silently discarding confirmed-real square footage. The alternative -- tightening the
false-positive heuristic further -- doesn't fix the root cause (fragmentation), just hides
it; the real fix is a same-building continuity check (proximity/envelope-based, not literal
`touches()`), noted as next lever below.

## Fix 2 (unit/corridor merge guard): cross-unit flagging works cleanly; the cheap re-split resolves nothing

**Cross-unit flagging (path a): clean, unambiguous win where it applies.** 4 of 13
merge-error groups (37 of 59 rooms) span >=2 distinct unit/building families and are now
labeled `MERGE_CROSS_UNIT` -- e.g. 26-05332's two 13-room and 9-room blobs that sum
buildings A+B and C+D together (previously silent `MERGED_ERROR` at 29% and 93% error);
20-29653's blob spanning units 1510B+1514. These are now excluded from auto totals with an
explicit, checkable reason instead of a bare "error" label -- real progress on
disambiguation, matching the probe27-recommended lever almost exactly as specified.
Only 9 of 13 groups (22 of 59 rooms) had NO cross-unit signal available at all -- either
truly same-unit merges (24-06233's C101+C103 sub-room splits) or single-building permits
where no unit distinction exists (24-06748, all merges are same-level sub-room splits).

**Cheap re-split (path b): 0 of 13 groups, 0 of 59 rooms resolved -- a clean negative
result, and a diagnostic one.** Every single attempt failed with `no_candidates`/
`too_few_candidates`: the arcs-only ("generic gap closer disabled") graph produces **zero**
closed sub-polygons materially overlapping the merged blob's footprint, not two-or-more
badly-assigned ones. I spot-checked this directly (`C101`+`C103`, 24-06233): 0 arcs-only
candidate polygons overlap that blob at all. **Diagnosis:** the density-gated closer isn't
just bridging two ALREADY-correctly-closed rooms into one (which disabling it would
cleanly undo); in every tested case it's the closer that makes the region close **at
all**. Disabling it doesn't reveal a pre-existing correct split -- it reverts the region to
"missed" entirely. The task's literal design ("re-run polygonize on just that blob's bbox
with the gap-closer disabled locally") is sound in principle but, as specified, structurally
cannot succeed on any merge where the merge and the closure are the SAME mechanism, which
appears to be all 13 tested cases. A surgical, per-connector ablation (remove only the ONE
specific added connector that bridges the two anchor regions, keep every other connector
in the blob) is a fundamentally different and more expensive design that might actually
work -- noted as a candidate next lever, not attempted here (out of this probe's cheap-fix
budget).

## Canary detail

**Bank (14-11290-NEWC, doc 1494156, p3):** v3 = v2_gated geometry + anchor-cluster filter.
21 wall-graph components found; 9 killed (10 polys / 1,133 SF), 3 flagged false-positive
suspect. Rooms closed unchanged at 13/18 (same as v2) -- the filter did not touch any of
the previously-matched branch rooms. `data/probe28/overlay_bank-canary_1494156_p3_v3_anchor_filtered.png`

**Hotel (17-35590-RNVS, doc 3523243, p9):** no per-room truth schedule has ever existed for
this page (it is probe2b/probe27's DENSITY stress-test canary, not a truth-graded permit).
For probe28 I derived 17 real anchors from the page's own printed decimal finish-keynote
tags ("201.1"/"201.2"/"201.3" -> room "201", genuinely printed text, not invented) to test
the filter honestly on the specific page the task named for false-positive risk. Result:
26 components, 13 killed (13 polys / 1,188 SF), **11 of 13 flagged false-positive suspect**
-- a much higher suspect rate than the 4 real-truth permits. **Caveat, stated plainly:**
this high rate is likely inflated by my synthetic anchor list's incompleteness (only rooms
with a finish keynote get an anchor; rooms without one look identical to a false-kill to my
detector even if the geometry engine is behaving correctly), not necessarily a true measure
of the filter's failure rate on this specific page. Anchors-matched held at 16/17 (no
regression). Overlays: `overlay_hotel-canary_3523243_p9_v2_gated.png` /
`overlay_hotel-canary_3523243_p9_v3_anchor_filtered.png`.

## Honesty-bar disclosures

- **Fabricated SF (-78.7%) came with a confirmed false-positive cost (>=1,453.8 SF on one
  page alone, visually verified against the drawing).** I would take this trade **only**
  if the killed-artifact bucket is routed to human review (flagged, not silently dropped)
  -- see recommendation above. Shipping it as blind auto-discard, as literally specified,
  is not something I'd sign off on given what the overlay shows.
- **The cheap re-split path is a validated negative result, not a bug**: 0/13 groups, 100%
  failure reason `no_candidates`, confirmed via direct inspection of one case. Reported
  honestly rather than papered over.
- **Design shortcut, disclosed:** the "local" re-split re-runs the arcs-only closer once
  per PAGE (not truly bbox-cropped per blob) and tests candidate overlap by spatial
  containment. Cheaper, and produces an identical verdict for a bijection test, but is
  worth knowing if the concept is revisited with a real per-connector ablation.
- **Merge-error median \|err\| went UP slightly (29.2% -> 30.6%, v2->v3)**, not down --
  expected and fine: removing 4 cross-unit groups (37 rooms) from the population changes
  its composition; this is not evidence the remaining errors got worse.
- Box: 2 workers, PDFs downloaded via R2 and deleted immediately after each page/permit
  (verified: `data/probe28/_pdf_tmp` does not exist after each run). Disk stayed at 4.3-4.4
  GB free throughout (started at 4.2 GB free).

## Verdict

**Partial rescue, same shape as probe27's own verdict, one rung further.** Fix 1 (anchor-
cluster filter) is a real, large win on the metric it targeted (fabricated SF -78.7%,
hitting probe27's own >80% aspiration) but should NOT ship as blind auto-discard -- route
its kills to human review, not silent deletion, given the confirmed false-positive
instance. Fix 2's cross-unit path is a clean, unambiguous win (37 of 59 merge-error rooms
now correctly and specifically flagged `MERGE_CROSS_UNIT` instead of generic `MERGED_ERROR`)
and I'd ship it as-is. Fix 2's re-split path is a validated dead end as literally specified
(0/59) and should not be pursued further in this form.

## The single next lever

**Same-building continuity check for the anchor-cluster filter** (not more merge-fixing):
replace strict polygon-`touches()` component grouping with a PROXIMITY-based one (e.g.
union components within some small gap tolerance -- reusing the exact same door/gap-width
scale already established for wall-closing -- before judging "zero anchors"). This directly
attacks the CONFIRMED false-positive mechanism (fragmented same-building wall graphs, not
just different-building blobs) without giving back the 78.7% fabricated-SF win, and reuses
infrastructure that already exists (the density-gated closer's own gap-tolerance logic).
This is cheaper than building a real per-connector-ablation re-split (Fix 2's actual next
lever) and fixes the more consequential, already-confirmed problem first.
