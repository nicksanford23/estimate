# Findings — 2026-07-05 (Claude side, written for Codex review)

Cross-team note: read alongside STATE.md. Raw data in Neon (estimate.*),
probe artifacts in data/probe1/. Questions for Codex at the bottom.

## 1. Dataset composition was badly skewed (now corrected)
Labels were 36.3% ONE permit (26-12298-NEWC hotel, 1,059 pages) and 48%
top-5 permits, out of 44 permits touched / 146 rendered. Root cause:
day-1 rendering picked largest docs first; waves labeled whatever was
rendered. POLICY NOW: per-permit thinking, smallest-viable first, gold
band = 10-80-page permits (product-matched tenant build-outs/renos),
1-9 page permits allowed cheap but never eval packets, >150-page whales
deferred/train-only. Encoded in .claude/skills/orchestrate-pipeline.

## 2. Waves 7-8 (per-permit policy, 1 agent each, 80 pages/run)
- Wave 7 (smallest-first): 19 permits COMPLETED in one run; 7
  finish_schedules, 11 floor_plans, 3 demo_plans. Small interior-reno
  permits are keep-dense and match the product's real customers.
- Wave 8 (gold band): 8 permits completed; 20 keeps (11 floor_plan,
  8 demo_plan, 1 finish_schedule hybrid).
- 27 projects total completed across the two waves for ~160 labeled pages
  — vs. earlier waves that completed 0-2 projects per 80 pages.

## 3. Label quality (blind review + Opus adjudication each wave)
- Wave 7 hardest-25 slice: keep/hide agreement 96%, category 88%.
- Wave 8 hardest-20 slice: keep/hide 80%, category 75% — dip is real.
- Recurring error #1: first pass UNDER-KEEPS hybrid sheets (finish
  schedule tables hiding on cover/elevation sheets). BUT adjudication
  showed the reviewer over-corrects too: of wave-8's 4 keep-flips the
  Opus judge upheld only 1 (page 7385, real finish schedule on an
  elevation sheet) and overturned 2 back to hide (a stamped rendering
  the reviewer mistook via sheet title; a ROOF demo plan that carries no
  flooring content). Three-tier disagreement is doing real work in BOTH
  directions — neither pass alone is trustworthy on hybrids.
- Recurring error #2 (DATA INTEGRITY): page-identity swaps — a label row
  carrying the sheet_title of a DIFFERENT page. Seen twice (page 6624
  triple-row; pages 5041<->7385 swapped pair). Cause: labelers building
  id->image lookup files and crossing wires mid-batch. Mitigation added
  to label-pages skill (mandatory per-batch identity spot-check at
  INSERT). Codex: if you label anything, same guard applies.
- All disputes settled by Opus adjudicator with append-only rows; source
  priority human > adjudicate > review > first-pass resolves truth.

## 4. Domain finding: permits without finish docs are NORMAL
Sibling-doc check on completed permits with floor plans but zero finish
pages found no unfetched interior/finish packages — those permits simply
never filed finish docs. Real-world bidding handles this via spec books
(not in permit portals), allowances, or qualified bids. Implications:
(a) our permit-set corpus UNDERSTATES finish-page availability vs the
bid sets real users will upload — we train on hard mode; (b) the product
must support quantities-first workflow (SF without materials).

## 5. SF feasibility probe 1 (Route A, vector geometry) — VIABLE
6 labeled floor_plan pages from 6 permits, original PDFs, fitz
get_drawings(): 5/6 have real vector geometry (1/6 flattened raster,
a 2013 scan). Scale notation parsed from text on 4/6. Kill criterion
NOT triggered. BUT the naive wall filter (axis-aligned ±2°, thick
strokes, length>2% width) works cleanly on only 2/6. Two concrete,
fixable failure modes (verified by overlay-image inspection, not stats):
- ROTATION: buildings drawn 8-10° (or 45°) off page axes are invisible
  to an axis-aligned filter. Fix: detect dominant wall angle per page,
  filter relative to it.
- HATCH NOISE: "existing wall" cross-hatch tick-marks pass a thin-fill-
  rect filter as hundreds of fake walls. Fix: suppress repeating
  parallel collinear rects at fixed spacing (hatches repeat; walls
  don't).
Artifacts: scripts/probe_vector_walls.py, data/probe1/overlay_*.png,
data/probe1/results.json. Next (probe 2, pending Nick's go): rotation-
aware filter + hatch dedup + polygonize the clean hotel page -> first
actual SF numbers vs hand-measure.

## 6. Model status (unchanged since rung-2c)
First trustworthy leaderboard on frozen split_v1: text_only full-recall
operating point = 100% finish recall @ 24% pages kept — promising, thin
eval (15 finish pages). Pending: 3-way split for threshold selection
(Codex's critique, adopted), retrain once completed-permit count grows.

## Questions for Codex
1. Your 150-doc queue: consider adding the gold-band size prior (prefer
   docs whose page counts land 10-80) and the interior/reno description
   boost — agree/disagree?
2. Any cheap metadata signal you can compute for ROTATED plans or
   raster-only (flattened) PDFs at queue time, so Route A pages get
   prioritized for download?
3. Sanity-check our per-permit label concentration numbers against your
   own reading of estimate.page_label (query in STATE.md context).
4. The page-swap integrity bug: propose an automated detector (e.g.,
   sheet_title text vs pagetext of that page_index mismatch scan) we can
   run over ALL existing labels to find undiscovered swaps.
