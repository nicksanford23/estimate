1
# Geometry Label Book v1 — DRAFT

Status: **DRAFT — not locked.** Becomes `geometry-label-book-v1` only after
(a) every FOUNDER ANSWER below is filled in by Nick and (b) Codex review.
Until locked, no outline may be confirmed as training truth against it.

Written 2026-07-16 (Claude). Companion to the annotation contract in
`data/geometry_annotations/*.geometry_annotation_packet_v1.json` and the
architecture lock in `docs/pilot/GEOMETRY_REBOOT_V1.md`.

## What this document is

The written rules for outlining a **flooring quantity zone** on a plan
viewport. We are not tracing architectural rooms; we are answering "where
does flooring material go, and where does one zone stop and the next
start." Anyone drawing or judging an outline — Nick, an AI reviewer, a
future customer — applies these rules and nothing else.

Consistency is the entire point: a model cannot learn a boundary rule that
changes from room to room. If a rule here turns out wrong, we change the
rule (new version) and relabel affected zones; we never quietly deviate.

## Vocabulary (defined once)

- **Zone** — one outlined region that receives one flooring quantity. A
  zone usually equals a scheduled room, but an open area can be one zone
  with several scheduled identities as members.
- **Boundary type** — why the outline stops where it does. One of:
  `wall`, `finish` (material change with no wall), `exterior` (edge of
  deck/balcony/building), `open_split` (a scheduled division inside one
  open space), `mixed`, `unresolved`.
- **Outcome** — the per-space verdict recorded in the packet:
  `enclosed_polygon`, `open_zone`, `finish_zone`, `not_in_scope`,
  `unresolved`.

## Rules

Each rule states the proposed default and the trade question behind it.
Nick confirms or overrides. "Proposed" reflects common takeoff practice as
I understand it — Nick's trade knowledge is authoritative and several
defaults exist precisely so he has something concrete to correct.

### R1 — Where the line goes at a wall
Proposed: outline follows the **inside face of the wall** — the line where
flooring actually meets the wall. Never the wall centerline, never the far
side. On double-line walls, trace the line facing the room.

FOUNDER ANSWER: pending

### R2 — Doorways and cased openings
Proposed: at a door where material changes, the boundary runs **under the
closed door leaf** (centerline of the door in plan). Where the same
material continues through an opening into another scheduled room, still
split at the opening centerline so each room's quantity stays separate.

FOUNDER ANSWER: pending

### R3 — Closets and alcoves
Proposed: **follow the schedule.** If the schedule lists the closet as its
own row, it is its own zone. If not, include it in the parent room's zone
when it opens into that room. Alcoves and niches always belong to their
room.

FOUNDER ANSWER: pending

### R4 — Decks, balconies, exterior surfaces
Proposed: outline them (they are real surfaces and the L4 test floor is
mostly deck), boundary type `exterior`, outcome `finish_zone` when the
schedule assigns them a finish, `not_in_scope` when it does not. They are
never silently skipped — skipping hides missing coverage.

FOUNDER ANSWER: pending

### R5 — Open areas with no wall between scheduled rooms
Proposed: one physical space shared by multiple schedule rows is outlined
as **one zone with all member identities listed** (`open_zone`), then split
by `finish` boundary where a finish plan/schedule shows a material change,
or by `open_split` along the drawn/dimensioned division when the schedule
demands separate quantities but no physical line exists. If there is no
defensible split line, keep one zone and flag it — never invent a wall.

FOUNDER ANSWER: pending

### R6 — Stairs
Proposed: the stair footprint is its **own zone** (stair flooring is
measured and priced differently than field flooring), boundary at the
edge of the stair enclosure or the top/bottom nosing lines.

FOUNDER ANSWER: pending

### R7 — Casework, fixtures, islands, tubs, built-ins
Proposed: **ignore them — outline wall to wall.** Standard takeoff
practice measures the room as if empty; flooring under cabinets and
fixtures is absorbed as waste/coverage. Exception: full-height shafts,
chases, and masonry cores are cut out (no floor exists there).

FOUNDER ANSWER: pending

### R8 — Columns and small obstructions
Proposed: columns smaller than ~2 ft on a side are ignored (included in
area). Larger solid cores are cut out per R7's exception.

FOUNDER ANSWER: pending

### R9 — Precision and curves
Proposed: corners snap to the drawing's linework; a boundary within ~3
inches (at drawing scale) of the true line is acceptable; curved walls are
approximated with segments every ~1 ft of arc. Perfect tracing is not the
goal — consistent, wall-face-following outlines are.

FOUNDER ANSWER: pending

### R10 — When you can't tell
Proposed: if the drawing genuinely doesn't show where the boundary is
(clipped viewport, illegible linework, contradictory plans), record
outcome `unresolved` with a note. **Never guess.** An unresolved label is
useful data; a guessed polygon is poison.

FOUNDER ANSWER: pending

### R11 — Which drawing counts
Binding (from the project-first lock, not a new question): outlines are
drawn only inside the confirmed **proposed-plan viewport** for that level.
Room tags appearing in existing/demo plans, enlarged details, legends, or
schedules on the same sheet are never outlined.

## Reviewer checklist (what an AI or human reviewer judges)

A proposed or corrected outline passes only if:

1. the polygon is closed and lies inside the confirmed viewport;
2. it contains its own room label (or membership is explicit for open zones);
3. it does not cross into any neighboring zone or corridor;
4. every edge follows R1–R9 (wall face, door splits, closet/stair/deck
   handling);
5. boundary types are recorded for every non-wall edge;
6. nothing that should be cut out (shaft/core) is included;
7. the area passes sanity (positive, within the viewport, not absurdly
   small/large for the space type). Printed schedule area may be compared
   **after** drawing as a diagnostic only — it never drives the outline.

Reviewer verdicts are machine evidence. Nick's confirmation is the only
act that makes an outline training truth.

## Versioning

This book is versioned like the page-label rubric. Any rule change after
lock = v2, with a list of which existing zones must be re-checked.
