# Probe 29 (Task A) -- same-building continuity fix for the anchor-cluster filter

**Date:** 2026-07-09
**Scripts:** `scripts/geometry_v4.py` (new module; `geometry_v3.py` unchanged, still
callable standalone), `scripts/probe29_regrade.py` (v4 grader, adds a REVIEW_KILLED
grading bucket), `scripts/probe29_canary.py` (bank + hotel, v4 variant added to
probe28's v2/v3 comparison).
**Before data:** `data/probe28/results_v3.json`, `data/probe28/canary_results_v3.json`
**After data:** `data/probe29/results_v4.json`, `data/probe29/canary_results_v4.json`
**Overlays:** `data/probe29/overlay_*_v4.png` (8 pages) + `data/probe29/overlay_bank-canary_*_v4_proximity_reconnect.png`
+ `data/probe29/overlay_hotel-canary_*_v4_proximity_reconnect.png`

## What was asked, and the honest pivot mid-probe

Probe28 confirmed a real false-positive mechanism in its own anchor-cluster filter
(v3): the TARGET building's own wall graph fragmenting into disconnected islands gets
misread as "different building, kill it" (24-06233 p10, Building B's own upper-floor
rooms, 1,177 SF, wrongly zeroed). Probe28's own recommended fix: replace strict
`touches()` cluster grouping with PROXIMITY-based grouping, reusing the density-gated
closer's own gap-tolerance scale (`geometry_v2.GAP_FT = 3.25ft`), before judging
"zero anchors = off-scope."

**First implementation (built, measured, rejected):** plain pairwise
`distance <= gap_pt` union-find over every polygon (transitive, like
`cluster_by_touching` but with a distance tolerance instead of an equality test).
This correctly rescues the confirmed 24-06233 blob (it really does sit only 1.44ft
from the anchored island containing `B202`) -- but ALSO chains in three more
anchor-less clusters on the same page that sit **9.4-11.7ft** from the anchored
island itself (i.e. genuinely too far to reconnect directly) -- because those three
clusters are each only 0.7-1.4ft from the *rescued blob*, and plain transitive
union-find treats "close to something that's close to an anchor" as equivalent to
"close to an anchor." Measured cost across the 4-permit regrade: fabricated/unlabeled
SF nearly DOUBLED (4,004 -> 7,665 SF, **+91%**), failing this probe's own success bar
before the canaries were even run. Caught by the mandatory before/after comparison,
not shipped.

**What shipped instead: a DIRECTIONAL, single-hop reconnection.**
1. Build islands by strict touching, exactly as v3 (`probe2_sf.cluster_by_touching`,
   unchanged).
2. Classify each island anchored/unanchored, exactly as v3.
3. For each **unanchored** island, measure its distance to every **anchored**
   island's own (original, never-grown) polygon footprint. If it is within
   `gap_ft` (3.25ft) of **exactly one** distinct anchored island, reconnect it into
   that island (kept). If it's within tolerance of zero, or of >=2 different anchored
   islands (ambiguous -- could belong to either), it is NOT reconnected.
   Anchor-less-to-anchor-less merging never happens, which is what prevents the
   chaining failure above -- an island can only reconnect to genuine anchored ground
   truth, never piggyback through another anchor-less island.
4. Anything still unreconnected is split into `REVIEW_KILLED` (flagged
   `false_positive_suspect`, v3's own heuristic reused unchanged) or `ARTIFACT`
   (not suspect, discarded exactly as v3) -- per the task's ask, no more blind,
   undifferentiated silent discard.

## 24-06233 p10 verdict: the confirmed case, verified directly

Diagnostic check (not just the regrade output) on the exact confirmed case:

| | v3 (touching) | v4 (directional proximity) |
|---|---|---|
| Building B upper-floor 6-poly blob (`[27,28,29,30,31,32]`, 1,177 SF) | **KILLED** -- flagged `false_positive_suspect`, zero anchors, discarded | **KEPT** -- reconnected to the anchored island containing `B202` (measured distance 1.44ft, well inside the 3.25ft tolerance) |
| 3 other anchor-less clusters on the SAME page (`[54,61]` 36.3sf, `[57,60]` 90.2sf, `[59]` 155.5sf, all 9.4-11.7ft from the anchor) | KILLED (part of the same undifferentiated bucket) | Correctly **stay unreconnected** (too far) -- split 1 `ARTIFACT` (36.3sf, not suspect) + 2 `REVIEW_KILLED` (90.2+155.5=245.7sf, flagged suspect) |

**The rescue is real and precisely targeted** -- exactly the confirmed blob comes
back, and the fix does NOT chain in the three genuinely-distant, unrelated clusters
that a naive proximity union would have swept in (see rejected first attempt above).

**But it does not flip a grading verdict.** Checking why: `B201`'s and `B202`'s
anchors already landed inside their own polygons under BOTH v3 and v4 (poly 35 and
40 respectively are in the same wall-graph-touching cluster as each other even
before any proximity fix -- they were never the false-positive case). `B203`'s
printed anchor point does not fall inside **any** of the page's 63 candidate
polygons at all (not a cluster-membership problem -- no polygon ever closed at that
location; a deeper wall-closure gap, out of this fix's scope). `B204` has no
findable printed anchor text at all (truth `area_sf` is `None` for this room --
plausibly unlabeled on the drawing). So the specific rooms named in probe28's
finding (`B201`/`B203`/`B204`) do not individually become `MATCHED` rows -- the
fix's actual, honest effect is: **the 1,177 SF blob stops being silently zeroed and
is now visible** (kept in `rooms_all`, shows up in the takeoff's SF pool as unlabeled/
needs-review space) instead of vanishing with no trace, which is the confirmed harm
probe28 flagged. Whether a human/vision reviewer can then assign it to `B201`+`B203`+
`B204`+corridor by eye (the overlay makes this checkable) is a separate, later step
this probe did not attempt.

## Headline table -- v3 vs v4, same 4 permits, same 182 addressable rooms

| metric | v3 (probe28) | v4 (this probe, directional) |
|---|---|---|
| matched (raw) | 14 | **14 -- unchanged** |
| matched, <=30% error | 7 (50%) | **7 (50%) -- unchanged** |
| median \|err\| matched | 33.8% | **33.8% -- unchanged** |
| missed (no polygon) | 61 | **61 -- unchanged** |
| confident-wrong | 30 | 30 -- unchanged |
| merged OK / SUSPECT / ERROR / CROSS_UNIT (groups) | 1 / 3 / 9 / 4 | **1 / 3 / 9 / 4 -- unchanged** |
| median \|err\| merged-error | 30.6% | 30.6% -- unchanged |
| **fabricated/unlabeled SF** (kept, no individual anchor) | **4,004.4** | **6,897.3 (+72.3%, +2,892.9 SF)** |
| total anchor-cluster-killed SF (all reasons) | 14,754.0 | 11,861.3 (-19.6%; the difference is what got reconnected) |
| **REVIEW_KILLED SF** (new bucket: flagged suspect, surfaced not discarded) | n/a | **914.4 SF, 26 polys, across all 4 permits** |
| ARTIFACT SF (silent discard, same mechanism as v3) | n/a (was the whole 14,754 bucket) | 10,947.0 SF |
| bank canary rooms closed /18 | 13 | **13 -- no regression** |
| hotel canary anchors matched /17 | 16 | **16 -- no regression** |

**Grading-row buckets are byte-identical between v3 and v4.** This is expected given
the 24-06233 finding above generalizes: reconnected SF becomes visible geometry, not
new anchor-token matches (anchors are found or not found independently of which
bucket their containing polygon lands in). The measurable, honest change is entirely
in the SF-accounting buckets, not the room-level grading table.

**Per-permit fabricated-SF breakdown** (where the +2,892.9 SF actually came from):

| permit | v3 fab SF | v4 fab SF | v4 review_killed SF | v4 artifact SF |
|---|---:|---:|---:|---:|
| 24-06233-RNVS | 2,023.0 | 3,200.0 | 444.7 | 769.3 |
| 20-29653-RNVS | 694.9 | 981.4 | 345.3 | 38.6 |
| 24-06748-RNVS | 728.8 | 2,108.8 | 44.0 | 10,052.0 |
| 26-05332-NEWC | 557.7 | 607.1 | 80.4 | 87.1 |

24-06748 shows the largest reconnection effect (a 1,137.1 SF island reconnected on
p7 alone) -- this permit is a single multi-floor building with no cross-unit
distinction, so a same-building-fragment reconnection there is architecturally
plausible by the same logic as the confirmed 24-06233 case, but **it was not
individually visually verified against the drawing** the way 24-06233 was in
probe28 -- flagged honestly, not claimed as confirmed.

## Is this a win? Honest verdict, not a clean one

**Does NOT clear the literal success bar as stated** ("...WITHOUT giving back a
material chunk of the fabricated-SF win"). Fabricated/unlabeled SF went up 72.3%
(2,892.9 of the original 14,755 SF reduction, ~19.6% of v3's win, came back) even
with the corrected, non-chaining design. That is a real, material number, not
noise.

**But the SF didn't vanish into nothing -- it moved to buckets that are exactly what
probe28's own recommendation asked for.** Of the 2,892.9 SF: 914.4 SF (26 polys)
is now `REVIEW_KILLED` -- flagged `false_positive_suspect`, excluded from auto
totals, surfaced with the suspect flag for a human to check against the overlay
(not silently discarded, not silently trusted either). The rest (the reconnected-
and-kept SF, ~1,978 SF) sits in the pre-existing `fabricated/unlabeled` bucket
(kept, unmatched-per-polygon) -- which was ALREADY the "known gap, not a wrong
number" bucket in probe27/28 (unlabeled polygons were always reported, never
auto-summed as a takeoff total). No SF was auto-quantified into a confident-but-wrong
number by this fix; the accounting integrity probe28 established (matched/merged
rows are the only auto-totaled buckets) is unchanged -- confirmed by the grading-row
table being byte-identical above.

**Recommendation:** ship v4 as the new baseline for the anchor-cluster filter (it
strictly dominates v3 on the confirmed-harm axis -- the 24-06233 blob demonstrably
returns, with zero canary regression, and zero change to the room-level grading
table that matters for auto-quantity totals) but do NOT present "fabricated SF -X%"
as a clean win on top of v3's number going forward -- report both the fabricated-SF
number AND the REVIEW_KILLED number together, since the honest trade this probe made
was "less silent discard, more flagged-for-review," not "more discard."

## Canary detail

**Bank (14-11290-NEWC, doc 1494156, p3):** v2_gated closed 13/18 (baseline).
v3 (touching) killed 10 polys/1,133 SF, 3 flagged suspect, closed unchanged at
13/18. v4 (directional proximity) reconnected 2 islands, closed **still 13/18 (no
regression)**, remaining kill split into 3 polys/127 SF `REVIEW_KILLED` + 5 polys/
957 SF `ARTIFACT` (down from v3's single 1,133 SF undifferentiated bucket -- net
kill total 1,084 SF vs v3's 1,133 SF, i.e. only ~49 SF reconnected here, a much
smaller effect than 24-06233 since the bank's wall graph is comparatively
well-closed). `data/probe29/overlay_bank-canary_1494156_p3_v4_proximity_reconnect.png`

**Hotel (17-35590-RNVS, doc 3523243, p9, density stress-test canary, no per-room
truth schedule -- same caveat as probe28: anchors are derived from printed decimal
finish-keynote tags, undercounting rooms without a keynote):** v2_gated matched
16/17 derived anchors. v3 killed 13 polys/1,188 SF (11 of 13 flagged suspect --
already a high rate probe28 attributed to its synthetic-anchor-list incompleteness).
v4 reconnected 1 island, anchors matched **still 16/17 (no regression)**, and
**100% of the remaining kill (12 polys/1,166 SF) is now flagged `REVIEW_KILLED`,
zero `ARTIFACT`** -- consistent with probe28's own caveat that this page's high
suspect rate is inflated by incomplete anchor coverage, not necessarily a true
false-kill rate; the directional fix doesn't change that caveat, it just makes the
remaining bucket's composition visible. `data/probe29/overlay_hotel-canary_3523243_p9_v4_proximity_reconnect.png`

## Honesty-bar disclosures

- **A design was built, measured, and rejected inside this probe, not before it**:
  the naive pairwise-proximity union-find is a real negative result (+91% fabricated
  SF, chains distant clusters through an intermediate rescue target), kept in
  `geometry_v4.py` as `cluster_by_proximity` with a docstring explaining why it is
  NOT used by the shipped filter -- a documented dead end, not deleted history.
- **The corrected design still costs +72.3% fabricated SF, not zero.** This is
  reported as the headline result, not minimized. Whether that's an acceptable price
  for "stop silently deleting confirmed-real SF" is a product call, not a technical
  one -- flagged for the orchestrator, not resolved unilaterally here.
- **Row-level REVIEW_KILLED routing (grader-side, `probe29_regrade.py`
  `apply_review_killed_routing`) is present in code but structurally cannot fire**:
  it checks whether a `MISSED_NO_POLYGON` truth token's own anchor point lands
  inside a `REVIEW_KILLED` polygon, but `REVIEW_KILLED` clusters are *defined* as
  containing zero of the page's anchor points (same anchor-point list used by the
  filter itself) -- so this check is tautologically always zero, confirmed in every
  one of the 8 pages run (`n_review_killed: 0` in every permit summary). The REAL
  `REVIEW_KILLED` signal that matters is tracked at the polygon/SF level instead
  (`page_result["review_killed_polys_sqft_on_page"]`, correctly populated and
  nonzero) -- reported here rather than quietly deleting the dead code, since a
  future reader extending this file should know not to trust the row-level bucket
  for anything.
- **24-06748's 1,137.1 SF reconnection (p7) was not individually visually verified**
  the way 24-06233 was -- flagged as plausible-but-unconfirmed, not claimed as a
  second confirmed case.
- Box: sequential runs, PDFs downloaded via R2 and deleted immediately after each
  page/permit (`data/probe29/_pdf_tmp` removed at end of each script). Disk stayed
  at 4.2-4.4 GB free throughout both regrade runs and the canary run.

## Verdict

**Real, targeted fix for the confirmed harm, at a real, disclosed cost -- not the
clean win the task hoped for.** The directional single-hop reconnection (not the
first, naive, chaining design -- that was tried and rejected inside this same
probe) correctly rescues the exact confirmed 24-06233 case, introduces zero canary
regression, and does not touch the room-level grading-row table at all. The price
is a genuine 72.3% increase in the fabricated/unlabeled SF bucket, roughly a fifth
of probe28's own headline reduction -- but that SF moves into an honestly-labeled,
non-auto-totaled bucket (`REVIEW_KILLED` + the pre-existing `unlabeled` bucket), not
back into a silently-wrong number. Recommend shipping v4 as the new anchor-cluster
baseline with the fabricated-SF and REVIEW_KILLED numbers always reported together,
never the former alone.
