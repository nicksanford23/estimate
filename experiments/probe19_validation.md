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
