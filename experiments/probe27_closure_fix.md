# Probe 27 — implementing probe 26's two fixes, re-graded against the same 4 truth-area permits

**Date:** 2026-07-09
**Scripts:** `scripts/geometry_v2.py` (new module, `probe2_sf.py`/`probe2b_sf.py` untouched),
`scripts/probe27_regrade.py` (v2 grader), `scripts/probe27_canary.py` (regression canary)
**Before data:** `data/probe26/results.json` (unchanged) · **After data:** `data/probe27/results_v2.json`
**Overlays:** `data/probe27/overlay_*_v2.png` (8 pages) + `data/probe27/overlay_bank-canary_*.png` (4 variants)

## What was built

1. **Bounded, density-gated gap closer** (`geometry_v2.snap_and_close_v2`). Reinstates the
   generic "close any two endpoints within a door-width gap" step that probe2b/probe26
   had fully disabled (`feet_per_pt=None` into `snap_and_close`) after it was found to
   explode candidate-connector counts at the two-tier engine's higher segment density.
   Tighter gap (3.25ft vs the old, never-shipped 4.5ft) **and** gated: a candidate
   connector is skipped if the local wall-candidate density (segments within 5ft of its
   midpoint) exceeds a **page-relative** percentile (default 80th) of that same page's
   own density distribution. Arc-chord door-swing closing (already proven safe) is
   unconditional and unchanged.
2. **Cavity/hatch polygon filter** (`geometry_v2.filter_cavity_hatch`). Kills polygons
   whose minimum-rotated-rectangle is elongated + narrow (wall-cavity/double-line-band
   shape) or that belong to a repeating-parallel-strip family (hatch), applied inside the
   engine before rooms are handed to the grader.
3. **Confident-wrong guard** (grader-side, `probe27_regrade.apply_confident_wrong_guard`).
   A MATCHED polygon (single room-code token, single polygon) computed at <40% of the
   truth area, or <60 SF for a non-utility room name, is demoted to `CONFIDENT_WRONG` —
   reported separately, never as an auto-quantity success.
4. **Merge-scoring fix** (grader-side, `probe27_regrade.apply_merge_scoring_fix`). A
   MERGED_OK blob (passes the ±15% sum tolerance) is downgraded to `MERGE_SUSPECT` if its
   interior still contains ≥6 unresolved wall-candidate segment midpoints — a whole-area
   collapse that nets out numerically is not the same as correctly resolved sub-rooms.

Only #1/#2 touch geometry; #3/#4 are new grading-time rules layered on `probe26_truth_grading.py`'s
config/anchoring/overlay code (imported, not copied).

## Regression canary: bank page (14-11290-NEWC, doc 1494156, p3) — NO REGRESSION, in fact improved

This is the exact page where a naive ungated closer was originally found to misbehave
(STATE.md 07-08 sprint / probe2b's docstring). Ran 4 variants of the two-tier engine
through the same 18-room anchor grading used in probes 4/6, plus an explicit
`naive_ungated` control (density gate forced off) to prove the gate is doing real work,
not just cosmetic:

| variant | gap_ft | density gate | added closers | skipped (dense) | rooms closed /18 | polygon faces |
|---|---|---|---|---|---|---|
| v1 (shipped, arcs-only) | — | — | 0 | — | **6** | 181 |
| v2 gated (this probe) | 3.25 | p80, page-relative | 4,435 | **1,196** | **13** | 16,198 |
| naive ungated, same gap | 3.25 | off | 5,629 | 2 | 13 | 23,579 |
| naive ungated, OLD 4.5ft | 4.5 | off | 9,756 | 9 | 11 (+2 fragment) | 117,137 |

The gate skips a real, large fraction of candidate closures (1,196 of the ~5,631 that
would otherwise fire) — it is not a no-op. On this specific page even the fully-ungated
variants didn't collapse the room graph (this page's minor-tier candidate count is tiny,
only 5 segments, unlike the hotel page below), but the OLD 4.5ft setting does show the
documented failure signature in miniature (2 rooms drop to `fragment`, matching probe6's
finding that widening the door gap breaks restrooms). Cross-checked against the *other*
page probe2b's docstring actually measured the "thousands of spurious connectors"
explosion on (17-35590-RNVS hotel, doc 3523243, p9, minor tier ~940 segments):

| variant | added closers | skipped (dense) | rooms (15-5000sf) | total SF |
|---|---|---|---|---|
| v1 (shipped, arcs-only) | 0 | — | 20 | 5,249 |
| v2 gated | 2,848 | **1,639** | 52 pre / 38 post-filter | 5,191 / 4,563 |
| naive ungated, same gap | 4,381 | 106 | 51 / 37 | 5,092 / 4,469 |
| naive ungated, OLD 4.5ft | 8,010 | 148 | 53 / 38 | 4,821 / 4,189 |

No collapse in either page under the gated closer; the gate materially reduces closures
in the two known-dense pages (1,196 and 1,639 skipped respectively) relative to the
ungated controls. **Verdict: the old failure does not return.** Bank-page overlay
before/after: `data/probe27/overlay_bank-canary_1494156_p3_v1_arcs_only.png` (6 rooms) vs
`data/probe27/overlay_bank-canary_1494156_p3_v2_gated.png` (13 rooms, including Tellers,
Women, Men, Self-Service, Offices 106/107 that v1 never closed) — visually confirmed, not
just numerically.

## Scorecard: before (probe26, v1 engine) vs after (probe27, v2 engine + all 4 fixes)

Same 4 permits, same pages, same room-code anchoring, same truth-area answer keys.

| metric | BEFORE (probe26) | AFTER (probe27) |
|---|---|---|
| addressable truth rooms | 182 | 182 (unchanged — same truth keys) |
| **matched, ≤30% error** | **0** (0%) | **7** (44% of 16 matched) |
| matched (raw count, any error) | 14 | 16 |
| median \|err\| on matched | 73.3% | **30.6%** |
| **missed (no polygon at all)** | **129 (70.9%)** | **61 (33.5%)** |
| not-on-page (no room-label text found) | 6 | 6 (unchanged, expected — text extraction unaffected) |
| merged OK | 20 rooms / 1 group | 2 rooms / 1 group |
| merged SUSPECT (new category) | n/a | **10 rooms / 2 groups** |
| merged ERROR | 5 rooms / 1 group | **59 rooms / 13 groups** |
| median \|err\| merged-error | 809.4% | 29.2% |
| **confident-wrong (new category)** | **0 counted** (but see below) | **30** |
| cavity/hatch killed | 0 (didn't exist) | 139 polys / 5,898.5 SF |
| unlabeled ("fabricated-candidate") polys | 100 / 7,607.7 SF | 158 / 18,758.7 SF |

### Headline reads

- **Miss rate: 70.9% → 33.5%.** This is the real, substantive win — the density-gated
  closer recovers a page that used to fail the self-audit entirely (24-06748 p5, "1ST
  FLOOR": v1 got largest_room=23sqft/total=55sqft and was thrown out as
  `scale_unverified`; v2 closes it to largest=738.5/total=2865 and it grades normally),
  plus roughly halves the miss rate on every other page.
- **Confident-wrong guard earns its keep on day one.** Every single one of probe26's 14
  "MATCHED" results was actually a small sliver polygon sitting under the room-number
  text, not the room itself (median error 73.3%, and literally 0 of 14 were within 30%).
  Retroactively applying just the guard's numeric rule to the *v1* data catches 12 of
  those 14 (86%) — this fix alone would have prevented the pipeline from silently
  reporting wrong numbers as successes even with zero geometry changes. With v2 geometry,
  16 rows try to MATCH and the guard demotes 30 total (across both engines' different
  candidate pools) to CONFIDENT_WRONG instead of letting them through.
- **Merge-scoring fix reveals the geometry didn't actually get much better at
  *separating* rooms — it got better at *closing* them.** `merged_ok` collapsed from 20 to
  2 rooms while `merged_err` exploded from 5 to 59. The extra closing power very
  frequently bridges gaps that should NOT have closed (hallway-to-room, unit-to-unit),
  producing big multi-room blobs that fail the ±15% sum tolerance. The 10-room
  `MERGE_SUSPECT` bucket (blobs that pass the tolerance by coincidence but still contain
  ≥6 unresolved wall-candidate segments inside them) shows this isn't hypothetical — it's
  the exact "whole-floor collapse that nets out" pattern the task asked to guard against,
  and it's already showing up at n=10 even before counting the errors.
- **Cavity/hatch filter: real but well short of the 80% target — reported honestly, not
  forced.** Tuned via an isolated sweep directly against probe26's own named 100-polygon
  / 7,608 SF population (decoupled from the gap-closer's effect, so this is a clean
  read on fix #2 alone): at the **zero-false-positive** operating point
  (`max_width_ft=6.0, min_aspect=3.0` — no MATCHED/MERGED truth-room polygon ever killed),
  the filter kills **28.3%** of that SF (2,151 of 7,608). Loosening further
  (`max_width_ft` up to 8, `min_aspect` down to 2.5) plateaus around 31% and starts
  costing false positives (2 real room polygons wrongly killed) — not worth it.
  **Diagnosis:** roughly 70% of that flagged SF was never elongated/hatch-shaped to begin
  with. Visual inspection (`overlay_24-06748-RNVS_7372349_p7_v2.png`) shows the biggest
  offenders are large, blob-shaped, room-scale polygons from a *different* cause — a
  same-sheet roof plan and an adjacent building's whole footprint closing as one big
  legitimate-looking (but off-scope) polygon that simply contains no addressable room-code
  token. That's a real closed shape, not a cavity or a hatch; this filter's shape test
  correctly leaves it alone, and a different filter (something like "must not be a
  same-sheet cluster disconnected from every addressable room's cluster") would be needed
  to touch it — out of scope for this probe, noted as the actual next lever.
- **Fabricated/unlabeled SF grew, not shrank, in absolute terms (7,608 → 18,759 SF) —
  the honest bad-news number.** This is the direct consequence of the point above: the
  gap closer creates far more room-sized candidate polygons overall (the cavity filter
  kills 5,898.5 SF of them, more in absolute terms than before, but the *pool* it's
  drawing from grew even faster because of new closures). Critically, **none of this
  growth reaches the reported/graded output** — the pipeline's anchoring discipline
  (a polygon must contain a target room-code token to be reported at all) means these
  stay in the "unlabeled, never reported" bucket, not the auto-quantity path. But it is a
  real product-quality regression in *overlay noise* / wasted geometry, and would be
  dangerous if a future integration step ever summed "all closed polygons" instead of
  "labeled ones only" — flagged for whoever builds that step next.

## Verdict: partial rescue, with a real and specific residual failure

Miss rate roughly halved (70.9% → 33.5%), median error on genuine matches roughly halved
(73.3% → 30.6%), and two previously-invisible silent-error classes (confident-wrong,
merge-suspect) are now caught by name instead of passing as clean successes. That is a
genuine, meaningful improvement and matches the "partial rescue" expectation set going
in — it is NOT full rescue: `merged_err` rooms went UP 10x (5 → 59) because the same gap
closer that recovers real doors also over-bridges rooms that shouldn't merge, and the
cavity/hatch filter reaches only ~28% of its target (not >80%) because most of the
flagged SF isn't actually a cavity/hatch problem.

**The density gate did NOT have to choose between stopping the explosion and allowing
door closure — it does both on the tested pages** (canary confirmed no regression, and
door-driven miss-rate dropped by half). But it does not, and structurally cannot, stop a
different problem: legitimate-looking over-merging across corridors/units on
already-dense multi-tenant sheets, which is a room-vs-room disambiguation problem, not a
density problem. Rules geometry on these multi-unit/multi-building sheets is still
**not shippable as auto_quantity** — it needs to route through `merged_err`/
`merge_suspect`/`confident_wrong`/`missed` to a human for the majority of rooms — but it
is now catching its own failures by name (the actual point of this probe) rather than
reporting silently-wrong numbers as clean successes.

## What I'd try next

1. **Attack over-merging directly**, not more closing: a "does this blob's interior
   contain a different-unit's room-code text" check (cheap, reuses the anchor infra
   already built) would let `merge_suspect`/`merged_err` blobs that span two named units
   get auto-split at the unit boundary rather than reported as one failed blob.
2. **A same-sheet-cluster-membership filter** for the fabricated-SF problem: any closed
   polygon whose wall-graph connected-component contains ZERO addressable room-code
   anchors anywhere in the component (not just itself) is provably off-scope for this
   permit's takeoff and can be dropped before it ever reaches "unlabeled" — this is the
   lever that would actually move the 28%→80%+ cavity-filter target, because it targets
   the real dominant cause (other-plan clusters), not hatches.
3. **Tighten the density gate further where `merged_err` is worst** (24-06233, 20-29653 —
   the multi-building/multi-unit sheets) — try a lower page-relative percentile (e.g. 65)
   specifically gated on whether the candidate connector bridges two DIFFERENT wall-graph
   components that each already contain a distinct room-code anchor (a much more direct
   "don't merge two already-identified rooms" signal than density alone).
4. Re-run this exact scorecard after (1)+(2) before spending more on (3) — (1)/(2) are
   cheap, reuse existing anchor/cluster infra, and address the two biggest residual
   numbers (`merged_err`=59, fabricated=18,759 SF) directly, whereas (3) is a slower
   parameter hunt.
