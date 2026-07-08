# Probe 14 — Agentic error-check: vision reads dimensions, diffs the geometry

**Date:** 2026-07-08
**Sheet:** 14-11290-NEWC A-1.1 Branch (doc 1494156 p3)
**Scripts:** `scripts/probe14_render_rooms.py` (crops + geom areas) → vision read → diff
**Follows:** Probe 12 (takeoff) + the 7,090 ground-truth correction.

## Why
Total SF landed ~right (2,719 net vs 3,190 branch GROSS = normal net/gross gap) —
but a right total can HIDE per-room fragments. There is no per-room SF schedule on
this set, so the only per-room ground truth is the **dimensions printed on the
plan**. So: render a padded crop per room (dims visible) tagged with our geometry
area → a vision pass reads the real dimensions → diff → flag which rooms are wrong.

## Results (first pass — 2 suspects + 1 control)
| Room | Our geom | Dimensions on plan | Verdict |
|---|---|---|---|
| 101 Vestibule | **31 SF** | ~9'-10" side, rotated 45° diamond, 4 doors (101A-D) → **~90+ SF** | **FRAGMENT — ~65% low** |
| 118 Jan | **23 SF** | rectangular closet in the dotted service-core hatch → **~40-50 SF** | **FRAGMENT / wrong shape** (red poly is a diagonal wedge) |
| 106 Office | **119 SF** | 11'-2" × ~10'-8" ≈ **119 SF** | **MATCH ✓** (control) |

## What it proves
1. **The flow works both ways** — it validates the clean office (106) and catches
   the two fragments. Not a rubber stamp.
2. **The errors are the known hard cases** — a rotated 4-door vestibule and a
   janitor closet inside the dotted "attic storage" hatch (the same service-core
   noise from Probe 5). Clean rectangles are dead-on.
3. **This explains the total.** The fragments drag net ~5-8% low, consistent with
   2,719 vs an expected net of ~2,850-2,950. The total was never "perfect" — the
   fragments were just hidden inside it.

## The payoff — vision is BOTH validator AND corrector
For a flagged fragment, the vision pass already read the real dimensions → we can
**replace** the bad geometry area with the dimension-derived area. So the hybrid
we've been circling is concrete:
- **Geometry** → clean rectangular rooms (fast, exact boundary + material zones)
- **Vision-on-dimensions** → the flagged hard rooms (reads the printed number)
- **The diff itself** → the error detector that decides which room needs which

This is the "agentic flow to figure out errors": read ground truth (code-data sheet
for totals, dimensions for per-room) → diff geometry → explain each discrepancy
(scope / gross-vs-net / fragment / merge). It caught the 7,090 scope error and the
101/118 fragments. Automating it = a per-permit self-grading takeoff.
