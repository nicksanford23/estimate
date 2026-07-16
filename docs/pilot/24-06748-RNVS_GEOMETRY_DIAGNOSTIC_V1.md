# 24-06748-RNVS whole-project geometry diagnostic v1

Run date: 2026-07-14

## Outcome

The system now executes all four required primary floor-plan sheets, but the
geometry is not accurate enough for quantities, training truth, evaluation,
demo truth, or bid use.

The unchanged v4 baseline found 20 of 36 scheduled room identities, produced
only 2 exact numbered rooms within +/-10% of the printed schedule area, missed
16 scheduled identities, and returned 18 unidentified polygons. This is a
complete-project failure measurement, not a failed attempt hidden behind one
good page.

The schedule reference remains a legacy agent transcription. It is useful for
this diagnosis but is not eligible truth until a human confirms the A100 table
region and its rows.

## Required coverage

| Level | Sheet | Expected rooms / SF | Identified | Exact rooms +/-10% | Missing | Unidentified | Candidate SF error |
|---|---|---:|---:|---:|---:|---:|---:|
| 01 | A101 p5 | 8 / 1,410 | 8 | 0 | 0 | 1 | +3.3% |
| 02 | A102 p6 | 13 / 1,322 | 5 | 0 | 8 | 6 | -53.4% |
| 03 | A103 p7 | 10 / 1,242 | 3 | 2 | 7 | 5 | +4.6% |
| 04 | A104 p8 | 5 / 1,081 | 4 | 0 | 1 | 6 | -33.4% |

The first- and third-level total area being close does not mean their room
geometry is correct. Large merged or leaked polygons cancel missing and partial
rooms at the level total.

## Failure diagnosis

- Level 01 anchors all eight scheduled identities, but three multi-room
  polygons do not respect the scheduled room divisions. Two groups are roughly
  double the expected member totals, and garage 107 is only a partial polygon.
- Level 02 is the clearest wall-geometry failure: eight scheduled spaces are
  missing, six polygons are unidentified, and every numbered polygon is
  outside +/-10%.
- Level 03 has two correctly sized small rooms, but seven scheduled spaces are
  missing. The 1,093.8 SF unidentified polygon overlaps the chosen quantity
  view and is classified as exterior/adjacent-space leakage, not merely a
  wrong-sheet selection.
- Level 04 is dominated by deck/exterior finish zones and partial room
  closures. These zones are not fully represented by room walls, so a
  wall-only engine cannot recover the schedule geometry reliably.

Machine-readable per-room and per-group classifications are in
`data/project_runs/full_sheet_v4/24-06748-RNVS/project_geometry_diagnostic.json`.

## Deterministic fixes and tests

1. The default takeoff resolver no longer selects the single line-richest page
   when a document has multiple labeled floor plans. It returns every labeled
   floor-plan page in the selected document. Explicit project-packet execution
   remains the stronger path because it also accounts for levels, schedules,
   supporting views, and quantity viewports.
2. The project runner executes A101-A104 together and writes one project run.
3. Polygon outputs now retain PDF bounding boxes and centroids for auditable
   viewport and leakage diagnosis.
4. An opt-in project-packet viewport constraint was run with v4. It removed no
   candidate polygons and changed no quality metric. Therefore viewport
   selection is not the dominant residual problem.
5. A project grader now reports every required level, missing schedule room,
   unidentified polygon, open group, and measured-vs-scheduled error.

## Rules versus current ML model

All engines used the same four pages, schedule roster, scale path, and proposed
viewports.

| Engine | Scheduled identities found | Exact rooms +/-10% | Missing | Unidentified |
|---|---:|---:|---:|---:|
| v4 rules | 20 | 2 | 16 | 18 |
| existing wall model | 11 | 0 | 25 | 25 |
| dual v4 + model | 21 | 2 | 15 | 15 |

Decision:

- Keep v4 as the default engine for now.
- Do not promote the existing wall model; on this complete project it is
  materially worse than v4.
- Keep dual as a diagnostic/review proposal source only. It finds one extra
  identity and suppresses some unidentified output, but it does not improve the
  number of accurate room quantities and shifts which rooms happen to pass.
- Do not tune page-specific thresholds. The residual is a boundary-semantics
  problem: distinguishing room walls, open-zone divisions, finish boundaries,
  exterior/deck limits, and annotation/adjacent-space linework.

## Forward implementation contract

The next learning artifact must be a complete human-corrected project, not the
36 schedule areas alone. For every scheduled space it must record the correct
polygon or an explicit open-zone/finish-zone outcome, the boundary source
(`wall`, `finish`, `exterior`, `open_split`, or `unresolved`), and source links
to both the plan viewport and schedule row.

Implementation order:

1. Human-confirm the active plan set, A100 schedule region/rows, and four
   proposed-plan viewports. This creates source links but does not retroactively
   make legacy model output truth.
2. Correct or draw outcomes for all 36 spaces in the review surface. Missing
   rooms are required work items, not absent records.
3. Add a separate finish/exterior boundary signal. The current wall segment
   classifier cannot solve deck and finish-zone divisions by itself.
4. Train a revised boundary-semantic model only after those complete-project
   corrections exist. Deterministic snapping, polygonization, scale, area math,
   and audit gates remain outside the model.
5. Freeze the resulting pipeline and run it unchanged on a different complete
   project. Split training and evaluation by project/plan set, never by random
   pages from the same building.

Until steps 1-5 clear their gates, the honest product action for this project is
geometry review/redraw, not automatic quantity export.
