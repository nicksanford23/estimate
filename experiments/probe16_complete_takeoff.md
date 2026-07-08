# Probe 16 — The complete end-to-end takeoff (14-11290 branch)

**Date:** 2026-07-08
**Method:** CAD-layer geometry (Probe 7) + Claude vision dimension read (4 Sonnet
workers, Opus adjudication) → three-unit takeoff, validated vs sheet A-0.1.
**Scripts:** `probe15_render_all.py` (crops), `probe16_takeoff_final.py` (assembly).

## The takeoff
| material | area | order unit |
|---|---|---|
| Carpet (CP-1/CP-2) | 2,058 SF | **229 SY** |
| Ceramic tile (CT-1) | 455 SF | |
| Resilient (RF-1) | 242 SF | |
| **Total floor** | **2,755 SF net** | |
| Rubber cove base RB-1 | 691 LF | |
| Wood base WB-1 | 129 LF | |
| Transitions TS-1/TS-2 | ~7 locations | |

**Validation:** 2,755 SF net vs **3,190 SF branch GROSS** (sheet A-0.1) = **−14%**,
the normal net-vs-gross gap. (NOT vs 7,090 = whole building incl 3,900 retail.)

## How each room's number was derived (adjudication)
- **agree** (geom+vision within ~5%) → trusted: 104,106,107,108,112,113,115,116,117,118
- **vision-corrected** → 101 Vestibule (geom 31 fragment → ~78; rotated 4-door diamond)
- **geometry blob, split by material** → the OPEN areas 102/103/105 (front) and
  110/111 (circulation); vision undercounts these (crops too tight), so geometry
  blob area is kept and split by finish.
- **geom, low-conf** → 109,114 (geom/vision disagree; flagged)

## Honesty
- **2 high / 8 med / 8 low** confidence. The lows are the open areas (need finish
  boundaries to split cleanly) and the fragment-corrected room.
- Per-room dimensions on this plan are often ambiguous (grid-to-grid, shared) —
  so neither geometry nor vision alone is enough; the **cross-check** is the value.
- The total lands ~right; per-room still carries real uncertainty. This is our
  best *complete* takeoff, with confidence flagged — not a verified-correct one.

## What made it work (the whole arc, one permit)
geometry finds clean rooms + total → merges shown to be mostly correct open plan →
finish schedule gives material → 7,090 traced to whole-building scope (branch=3,190)
→ vision reads dimensions to catch/fix the rooms geometry gets wrong. End to end.
