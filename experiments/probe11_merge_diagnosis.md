# Probe 11 — Why do the 5 rooms MERGE? (the metric was wrong, not the tool)

**Date:** 2026-07-08
**Sheet:** 14-11290-NEWC, A-1.1 Branch floor plan (doc 1494156 p3), 1/4"=1'-0"
**Script:** `scripts/probe11_merge_diagnosis.py`
**Crops:** `data/probe11/merge_poly0_102_103_105.jpg`, `merge_poly8_110_111.jpg`
**Follows:** Probe 7 (layer walls → 12 closed, 1 fragment, 5 merged).

**Superseded current read:** Probe 22/23 is the scorecard to carry forward:
10 auto-quantity rooms, 2 geometry-review rooms (109, 114), 1
vision-correct/redraw room (101), and 5 open-zone split labels. This probe's
main durable finding is still that open-plan merges should not be scored as wall
failures.

## Method (intervention-as-diagnosis)
Reproduce Probe 7's exact layer-wall extraction + polygonization, find the merged
blobs, then for each merged room-pair check **what layer the dividing lines live
on** (STRtree over ALL segments; test which cross the line between the two room
labels). Three possible causes, each with a *different* fix:
- **A** partition on a NON-wall layer we didn't grab → broaden capture
- **B** partition IS on a wall layer but didn't close → fix snap/close
- **C** nothing drawn between them → the merge is CORRECT (one open space)

## Result — 2 merged blobs holding the 5 rooms
`poly0: {102 Lobby, 103 Tellers, 105 Self-Service}` · `poly8: {110 Copy/Fax, 111 Mortgage}`

| Pair | crosses on | cause |
|---|---|---|
| Lobby ↔ Tellers | `i-millwork`, `01-Tags`, `Queue Line` | teller counter + queue rope — **not a wall** |
| Lobby ↔ Self-Service | `01-Tags`, column lines | **nothing** — open space |
| Copy/Fax ↔ Mortgage | `01-Dimension`, column lines, notes | **nothing** — annotation only |
| Tellers ↔ Self-Service | **5 wall-layer segs** | the ONE real closure gap |

The crops make it visual: `poly0` is the **entire open front-of-house banking
floor** (Self-Service + Lobby + Tellers as one continuous space; the walled
offices 106/107 beside it close perfectly). `poly8` is the **open circulation /
waiting area** (the service core beside it is properly separated).

## Finding — 4 of the 5 "merges" are CORRECT
There is no wall between these rooms because the architect drew none — they are
open-plan. **You cannot fix them with better wall detection; there is nothing to
detect.** Only Tellers↔Self-Service is a genuine closure gap. So the merge count
was mostly our *metric* being wrong (penalizing correct grouping of open space),
not the tool failing.

Honest remaining defects on this sheet: **two** — the 108 Conference *fragment*
(interior clutter, Probe 5) and the one Tellers↔Self-Service closure gap. Not five.

## What to build (the pivot this forces)
1. **Change the metric.** Not "every labeled room = its own polygon." Instead:
   total SF accuracy + enclosed-room correctness + material-zone accuracy.
2. **ML target = walls + FINISH boundaries**, not walls alone. Open commercial
   space is divided by finish transitions (carpet→tile), not walls — a different
   signal the layers already carry.
3. **Two-stage takeoff:** walls → enclosed rooms (works today); finish boundaries
   → subdivide the open areas into material zones. Mirrors how an estimator works
   (they follow the carpet edge in a lobby, not a wall).
4. **For total SF the merges are harmless** — Lobby+Tellers as one polygon sums to
   the same area. A near-term "total flooring SF + material from finish tags" MVP
   doesn't need the ML.
5. **Finish coverage is now first-class** — verify it when widening the corpus.

Caveat: "open space needs finish, not walls" is **building-type dependent** (banks
have big lobbies; cellular offices/warehouses are mostly enclosed). The pivot
matters more for open-plan work — measure which building types dominate the corpus.
