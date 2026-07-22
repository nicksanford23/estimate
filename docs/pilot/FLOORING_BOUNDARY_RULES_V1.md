# Flooring boundary rules v1 — plain-language working contract

Status: **WORKING CONTRACT — estimator calibration required**  
Date: 2026-07-21  
Parent: `GEOMETRY_RESET_V2_FIRST_PRINCIPLES.md`

This is the beginner-facing rule book for deciding where a flooring area
stops. It deliberately separates physical meaning from PDF line measurement.

## The one question

Stand inside the area in your imagination and walk its perimeter:

> At this exact place, what physical or estimating event makes this flooring
> stop, change, continue, or become excluded?

If that question has no defensible answer, the boundary is unresolved.

## Rule 1 — wall

When flooring meets a wall, trace the face of the wall that touches the room.
Do not use the wall center, far face, window center, or whichever black stroke
is closest to the draft.

Required record:

- meaning: `wall_face`;
- evidence: visible room-side wall face;
- interruptions: doors/openings identified explicitly; and
- uncertainty: wall face ambiguity recorded instead of guessed.

## Rule 2 — doorway

A doorway is not automatically a wall boundary. First decide whether the two
sides belong to separate measured areas or one continuous flooring area.

- If separate: record a `threshold` with a stated jamb/transition convention.
- If continuous: record `open_continuation`; do not invent a boundary for
  geometry merely because two room names exist.

The Layer-B estimating policy decides how shared thresholds are assigned. That
policy must not alter the physical geometry history silently.

## Rule 3 — finish change without a wall

Use `finish_transition` only when a finish plan, hatch change, keyed note,
detail, or qualified reviewer supports the location. A room name or printed
area alone cannot create a transition line.

## Rule 4 — open plans

Several room identities may belong to one connected physical flooring area.
Do not manufacture rectangles around labels. Preserve one physical area with
multiple identity memberships until finish or estimating evidence justifies a
split.

## Rule 5 — exterior/deck limits

Exterior walls and deck/parapet assemblies may contain several parallel lines.
Record which physical limit the estimating policy requires. If inside versus
outside edge is ambiguous, route to review instead of choosing the closest.

## Rule 6 — holes and exclusions

Create a hole only for a physical no-floor region supported by the documents
and current deduction policy. Furniture, fixtures, text, and hatch symbols are
not holes by themselves.

## Rule 7 — stairs, shafts, and specialties

Record observed geometry separately from whether finish is in scope. A shaft
can have an observable footprint while receiving no flooring. Specialty scope
requires the named estimating policy and, during calibration, qualified
estimator review.

## Rule 8 — clipped or missing evidence

A crop border is never a flooring boundary. Re-crop using the full viewport.
If the required plan/detail is missing, record `unresolved` with the missing
evidence; do not close the polygon confidently on the image edge.

## Rule 9 — curves, angles, and jogs

Preserve shape changes that materially affect the flooring perimeter. Add
vertices or curve/chord segments with controlled error. A clean rectangle is
not an improvement when it deletes a real jog.

## Rule 10 — measurement comes last

After meaning and drawing evidence are confirmed:

1. map the evidence into PDF coordinates;
2. use the verified viewport scale;
3. measure proposal-to-evidence distance;
4. correct the geometry;
5. remeasure; and
6. calculate area from the corrected closed boundary.

The inch gap is a placement diagnostic. It is not a confidence score, area
error, or proof that the selected evidence is correct.

## Reviewer decisions

The founder/customer interface uses:

- **Approve area** — the visible corrected boundary and explanations make
  sense;
- **Fix again** — a named side or region remains wrong; and
- **Not sure** — qualified review or missing evidence is required.

The interface never asks a nontechnical reviewer to approve candidate scores,
PDF coordinates, or unexplained colored lines.

