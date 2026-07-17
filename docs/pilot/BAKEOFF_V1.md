# Room-outline bake-off v1 — 24-06748-RNVS (2026-07-16/17)

Three proposal engines, same 35 prompted rooms (36th = 210, a 7 SF closet
with no findable label, explicit gap in all arms). All outputs are machine
proposals; nothing here is truth. Schedule areas are a legacy
agent-transcribed reference used DIAGNOSTICALLY, after prediction, never
for selection in any product path.

## Scoreboard

| Arm | Selection needed? | ≤10% of schedule | ≤25% | Shape quality (visual) |
|---|---|---|---|---|
| 1. SAM 2.1 full sheets (Small+Large) | best-of-9 needs answer key | 15/35* | 26/35* | confetti; cleanup salvages some |
| 2. SAM 2.1 Small, per-room crops | best-of-9 needs answer key | 20/35* | 27/35* | real wall-following regions; window/door leaks |
| 3. Claude vision (Opus), per-room crops | **none — one shot** | 15/35 | 29/35 | crisp 4–7-corner polygons on wall faces |

*Arms 1–2 numbers are an EXISTENCE diagnostic (closest of 9 candidates
per room after deterministic cleanup: binary closing, hole fill, largest
component). The product cannot select that way. SAM's own best-score
selection picks the room-label tag or an over-mask (1/35 within 10%).
Arm 3's number is its real one-shot performance.

## Verdicts

- **Arm 3 is the primary proposal engine candidate**: no selection
  problem, editable low-vertex polygons, per-edge reasoning, calibrated
  confidence (its ≥0.7 rooms: 0.4–12% error; its ≤0.35 rooms are exactly
  its failures: open-plan 305/306/307, 209A). Cost ≈ free (subscription).
- **Arm 2 survives as an independent cross-check**: different failure
  modes than vision. Vision-proposes + SAM-agrees is a candidate
  high-confidence gate for the approval loop. SAM Small beat Large on
  crops; full-sheet feeding is retired.
- Known arm-3 failure modes: crops clipped open-plan zones (305/306/307
  each got only the visible slice of one continuous great room — needs
  level-viewport context or bigger crops for open zones); tight
  compartment clusters (209A hall); circulation rooms without clean walls
  (104). All were self-flagged with low confidence.
- Label-book gaps surfaced by agents: elevator shafts (schedule lists SF;
  flooring scope?), scheduled-but-undrawn deck splits (404/405), stairs
  wrapping shafts. Added to founder question list.

## Artifacts

- Arm 1: results_gpu_g1_full/, results_gpu_g1_full_large/, review_small/, review_large/
- Arm 2: results_gpu/, results_gpu_large/ (crops), g1b_cleaned_best.json, qa_g1b/cleaned_*.png
- Arm 3: claude_vision/level_0{1..4}.json, claude_vision/overlay_*.png
- Editor preload: results/proposals_for_editor.json (claude_vision_v1, 35 rooms,
  PDF coords validated to 0.001 pt against anchors)
- Bundles: bundle/ (G0 full-strip), bundle_g1b/ (per-room crops)

## Caveats

One building, one architect. Nothing generalizes yet; the dev-portfolio
ladder (3–4 diverse projects, 2 sealed) still governs any training or
production claim. Next human gates: Nick's label-book answers, editor
sign-off, and per-room review of arm-3 proposals in the editor.
