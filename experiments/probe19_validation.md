# Probe 19 — First accuracy measurement vs ground truth + the GOLDEN SET

**Date:** 2026-07-08
**Script:** `scripts/probe19_validate.py`

## First real number (26-05332 townhouse)
Parsed the finish schedule (p19) cleanly: **68 rooms, 5,279 SF** (sheet: 5,278).
Ran rules geometry on floor plans p8/p9: **13,787 SF, 212 room-size polygons →
+161% vs truth.** Garbage — but EXPECTED: 26-05332 is a FLATTENED PDF (no wall
layers) + a repeated-unit townhouse (Probe 3's hard case). This tested the WEAK
rules path, not the layer path. Still valuable: our first honest error number, and
it confirms rules geometry is unusable on hard cases.

## The GOLDEN SET (Nick's insight): layers ∩ SF-answers
Permits with BOTH confirmed CAD wall layers AND a per-room SF answer table let us
(a) run the EXACT layer geometry and (b) grade it against real per-room SF — and
they double as the seed ML training set (layers=features, SF=labels, no labeling).

Current golden set (from the labeled subset only): **4 permits**
- 16-17098-NEWC
- 18-13316-RNVS
- 24-22310-RNVN
- 24-26713-RNVS

## North-star metric for data collection
MAXIMIZE THE GOLDEN SET. Every download/scrape choice: "does this add a permit with
layers AND an SF answer table?" 4 from a tiny slice → widening the layer scan
(all downloaded) + the ground-truth hunt (all schedule pages) will grow it a lot.

## Next
Run the FAIR validation — layer geometry vs SF answers — on the 4 golden permits.
THAT is the real measurement of the good path (the 26-05332 rules test was
path-mismatched).

---

## Probe 20 — the fair test didn't land; the golden set is rarer than it looked
Tried the layer-geometry-vs-SF validation on the golden 4. **None qualifies** under
the REAL (page-aligned, usable) requirement:
- 16-17098, 18-13316, 24-26713: confirmed wall layers are on NON-floor-plan pages
  (demo/enlarged sheets); the labeled floor plans have 0 wall-layer segments.
- 24-22310: wall layer is `8_Wall_Hatch` (hatching, not centerlines) -> 3 polygons
  for a 5-room space; and its schedule SF didn't parse.

**Honest finding: in our current ~150-permit slice, clean wall-CENTERLINE layers
and clean per-room SF answers DO NOT co-occur.** We have layers-without-SF (the
bank 14-11290) and SF-without-layers (26-05332's 68-room finish schedule). The true
golden set (both, same floor plan, usable, parseable) is ~0 today.

Requirements compound (each cuts the set): (1) wall CENTERLINES not hatch, (2) on
the floor-plan page, (3) whose rooms appear in a schedule, (4) with parseable
per-room SF. The naive permit-level intersection (=4) collapses to 0 under these.

IMPLICATION: to measure the GOOD (layer) path against per-room truth we must WIDEN
the corpus to find genuinely-aligned golden permits (data-plan north star, now
known to be rarer), OR validate layer geometry against DIMENSIONS/vision instead of
a schedule (partially done: bank room 106 geom 119 = dims 119). Script:
scripts/probe20_validate_golden.py.
