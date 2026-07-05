# Label Audit Agent Findings

Scope: 68-page risk-weighted audit packet from frozen split_v1 eval permits.
The packet included all 15 eval finish pages plus likely false-negative
candidates, low-confidence/flagged pages, floor/demo samples, and adjacent
non-keep categories.

## Result Counts

- Audited pages: 68
- Category recommendations matching current label: 67
- Clear category disagreement: 1
- Same-category but uncertain/needs policy clarification: 2
- Potential finish false negatives found: 0 in the sampled high-risk set
- Current finish labels challenged: 1 of 15 eval finish pages

## Clear Disagreement

| audit_id | page_id | current | recommended | issue |
|---:|---:|---|---|---|
| 15 | 4489 | finish_schedule | floor_plan | Dominant content is a descriptive first-floor retail plan; the finish schedule is small/secondary and mostly blank. |

This matters because the frozen eval split has only 15 finish pages. One bad
finish label is a material metric issue.

## Uncertain / Policy Clarification

| audit_id | page_id | current | recommendation | issue |
|---:|---:|---|---|---|
| 36 | 1480 | finish_plan | finish_plan, uncertain | Enlarged bathroom plans are finish-heavy but also resemble details/enlarged plans. Keep as finish_plan is defensible under over-keep policy. |
| 47 | 4041 | floor_plan | floor_plan, uncertain | Hybrid sheet includes roof/demo, RCP, and floor plan. Floor_plan is acceptable, but hybrid policy should be explicit. |

## Systemic Findings

1. Category labels are better than expected.

   The sampled current-truth categories were mostly defensible. The taxonomy is
   not the bottleneck right now.

2. Observation booleans are weaker than category labels.

   Repeated false negatives appeared for:
   - `scale_visible`
   - `dimensions_visible`
   - `table_present`
   - `room_labels_visible`
   - `finish_codes_visible` in at least one finish schedule

   These fields are useful but should not be trusted as hard ground truth for
   Stage 2/3 without additional parsing or review.

3. Sheet titles are uneven.

   Some are missing, incomplete, or capture an embedded detail title instead of
   the main sheet title. Use page text parsing as a backup for grouping.

4. Finish-coded elevations are not finish plans.

   Several interior elevation sheets show finish/material tags, but the agents
   agreed they should remain `elevation_section` when elevations dominate.

5. Hybrid policy needs one refinement.

   A sheet should be `finish_schedule` only when a meaningful room/material
   finish table dominates or is important enough to recover. A mostly blank or
   secondary schedule on a floor-plan sheet should not force `finish_schedule`.

## Recommended Labeling Changes

1. Review/adjudicate all eval finish pages before trusting finish recall.
2. Tighten the skill rule for `finish_schedule` vs hybrid floor/plan sheets.
3. Add explicit guidance that finish tags on interior elevations do not make a
   sheet `finish_plan` unless the plan/finish layout is the main content.
4. Treat the observation fields as lower confidence than category labels.
5. Add automated text/PDF-derived checks for `sheet_title`, scale strings,
   dimensions, and finish-code presence where possible.
