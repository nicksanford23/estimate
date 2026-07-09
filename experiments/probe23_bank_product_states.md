# Probe 23 — Bank product-state diagnostic

**Date:** 2026-07-08
**Script:** `scripts/probe23_bank_product_states.py`
**Outputs:** `data/probe23/bank_product_states.json`,
`data/probe23/bank_product_states.md`

## Why this probe exists

The wrong question was: **did every room label produce a separate closed
polygon?**

That penalizes correct open-plan grouping and makes the bank sound worse than it
is. The product question is: **what should the app do with this room or zone?**

## Result

| Product action | Count | Rooms |
|---|---:|---|
| auto_quantity | 10 | 104, 106, 107, 108, 112, 113, 115, 116, 117, 118 |
| geometry_review | 2 | 109, 114 |
| vision_correct_or_redraw | 1 | 101 |
| open_zone_split | 5 | 102, 103, 105, 110, 111 |

So the bank is not "8 failures." It is:

- 10 enclosed rooms the system can quantity automatically.
- 5 open-plan labels that need finish/material-zone splitting, not more wall
  closure.
- 2 review cases.
- 1 true redraw/correction case.

## Targeted debug of the three problem rooms

- **101 Vestibule:** true fragment. The room is a rotated storefront/glass
  vestibule with multiple door leaves. Geometry caught a central fragment
  (`30.9 SF`) but the dimension read says about `78 SF`. Probe 17 found no nearby
  missing-wall gap, so the likely cause is storefront/glass/door semantics, not
  endpoint closure.
- **109 Office:** review, not a model-wide wall failure. Geometry is `124.9 SF`
  vs `100 SF` from dimensions (`+24.9%`). The crop shows a doorway/opening edge
  and the gap trace sees only hairline gaps plus a small door/opening.
- **114 Corridor:** service-core/corridor zoning issue. Geometry is `46.9 SF`
  vs `37 SF` from dimensions (`+26.8%`). The label sits inside a hatched
  restroom/service-core region, so the polygon is measuring a broader service
  zone instead of the narrow corridor path. Probe 17 sees only hairline gaps.

## Product implication

The scoring metric should become:

1. auto-quantity correctness for enclosed rooms,
2. review/low-confidence recall for rooms likely to be wrong,
3. finish/material-zone accuracy for open areas,
4. total net SF sanity against gross or schedule.

That keeps agents in the right role: diagnose, validate, and label failure
modes. The quantity engine should still be deterministic after walls, finish
boundaries, room labels, and scale are known.
