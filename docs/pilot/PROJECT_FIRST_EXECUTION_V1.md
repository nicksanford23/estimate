# Project-First Pilot Execution v1

> **2026-07-21 addendum:** Project-first denominators and packet completeness
> remain locked. Geometry within each project now follows
> `GEOMETRY_RESET_V2_FIRST_PRINCIPLES.md`: boundary meaning and agentic evidence
> investigation precede PDF-line measurement. July 17 colored proofs are
> retained diagnostics, not reviewed labels.

Locked 2026-07-14 after the `24-06748-RNVS` and `14-11290-NEWC`
walkthroughs.

## Operating decision

The unit of ingestion, review, geometry execution, and scoring is a complete
plan set for one project. A page may be a worker task, but a single successful
page is never a project result.

Project-first does not mean page-specific tuning. We learn from complete
projects while keeping the pipeline and thresholds fixed when we move to the
next project.

Before geometry runs, each project packet must identify:

1. the active document revision / plan set;
2. every primary level or area plan that contributes quantity;
3. supporting enlarged plans without double-counting them;
4. every room-finish, room-area, or combined schedule;
5. the proposed-plan viewport on each mixed sheet;
6. the level/area represented by each viewport; and
7. the expected room roster from schedule evidence when one exists.

Missing or unconfirmed packet members are visible blockers. They are not
silently omitted.

## What “agent-transcribed” means

`data/triage/truth_area/*.json` was produced by an agent reading a rendered
schedule and transcribing rows into structured JSON. This is useful reference
evidence and can become a reviewed answer key, but it is not proof that the
product has an automatic schedule parser.

Until a fresh human qualification event says otherwise:

- describe this data as `agent_transcribed_reference`;
- do not describe it as an automatic machine extraction;
- preserve its raw source page and transcription notes;
- keep it ineligible for training, sealed evaluation, demo truth, or bid truth;
- use it diagnostically to build and test the reusable parser.

A reusable schedule extraction must preserve table-region geometry, cell
coordinates, raw cell text, normalized values, extractor version, and row-level
source evidence.

## Schedule capabilities

Do not require every useful schedule to contain an area column.

- `room_finish`: room -> floor/base/material; geometry supplies area.
- `room_area`: room -> printed area; useful for geometry cross-checking.
- `room_finish_area`: both of the above.

`14-11290-NEWC` is the `room_finish` development case. Its IW-2.1 hybrid
finish-plan/schedule sheet identifies rooms 101-118 and material codes but no
per-room area.

`24-06748-RNVS` is the `room_finish_area` development case. Its A100 room
schedule lists 36 rooms across four levels, floor finishes, and printed areas.

## Geometry architecture decision

Use the cheapest adequate route per confirmed viewport:

1. deterministic scale, text, room-anchor, and viewport extraction;
2. deterministic geometry from clean named CAD layers when available;
3. ML segment classification for flattened vector plans where walls cannot be
   separated reliably from fixtures, annotations, and other linework;
4. raster segmentation for scanned pages; and
5. confidence gates and human review for unresolved output.

ML predicts boundary semantics; deterministic code remains responsible for
snapping, polygonization, transforms, area arithmetic, provenance, and audits.
Finish boundaries are a separate signal from walls and may come from a finish
plan even when rooms are open.

## Whole-project geometry report

Every primary viewport receives an outcome, including failures. The project
report contains at least:

- required primary viewports vs processed viewports;
- scheduled rooms vs anchored rooms vs valid polygons, by level;
- missing scheduled rooms and unidentified polygons;
- merged, split, fake, wrong-label, and open-zone counts;
- measured-vs-printed area error when an eligible area schedule exists;
- measured area coverage by level;
- wrong-viewport and wrong-scale failures; and
- engine route/version and runtime per viewport.

No run may be recommended for training, evaluation, demo, or export because a
single page looked good. Evidence eligibility and the appropriate human
verdicts remain separate required gates.

## `24-06748-RNVS` development sequence

1. Confirm the A100 schedule region and the A101-A104 proposed-plan viewports.
2. Create levels 01-04 and canonical spaces from the 36 schedule rows.
3. Link plan labels to the schedule-derived room roster; reject unrelated
   numeric text as room anchors.
4. Run the existing engine unchanged on all four primary viewports.
5. Record the whole-project baseline; do not tune during baseline collection.
6. Classify every failure as packet/viewport, scale, anchor, rules geometry,
   ambiguous boundary requiring ML, open zone, or finish-boundary failure.
7. Fix deterministic failures first, then train or revise the boundary model
   only for the measured residual class.
8. Freeze the pipeline and run it unchanged on a separate complete canary
   project before making a generalization claim.

## First execution result (2026-07-14)

Steps 2-6 have been executed as machine/diagnostic work. V2 now has four
levels, 36 candidate space identities, four proposed viewport observations,
and geometry outcomes for A101-A104. Human confirmation and schedule-row source
links remain open gates.

The unchanged v4 whole-project baseline found 20/36 scheduled identities and
only 2/36 exact rooms within +/-10%; 16 scheduled identities were missing and
18 polygons were unidentified. The viewport-constrained v4 rerun produced no
metric change. The existing wall model was worse (11 identified, 0 accurate),
while dual found 21 but still only 2 accurate. v4 therefore remains default;
the existing model is not promoted and dual remains diagnostic-only.

The detailed report and forward implementation contract are in
`docs/pilot/24-06748-RNVS_GEOMETRY_DIAGNOSTIC_V1.md`.

The machine-readable packet is
`data/pilot_projects/24-06748-RNVS.project_packet_v1.json`. Run
`python scripts/validate_project_packet.py --permit 24-06748-RNVS --strict`
to prevent a partial-page run from being mistaken for a complete project run.

## Portfolio ladder after the first project

One complete project proves the workflow; it does not prove generalization.
The first segmentation program uses:

- `24-06748-RNVS` as the one complete smoke project;
- three to four deliberately diverse complete development projects; and
- two untouched complete evaluation projects.

Projects, not pages, are the split boundary. No floor, crop, revision, or
schedule row from an evaluation building may influence training, prompt
tuning, thresholds, or selection. The initial planning range is roughly
150-300 corrected room/quantity-zone masks across the portfolio, with drawing
diversity valued over raw mask count.

The smoke project first tests whether SAM reduces human correction effort. It
cannot promote SAM to production. Development projects create training masks;
the untouched projects decide whether a frozen candidate generalizes. See
`docs/pilot/GEOMETRY_REBOOT_V1.md` for the GPU, editor, data, and promotion
contracts.
