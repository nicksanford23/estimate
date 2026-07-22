# Geometry reset v2 — flooring-boundary first

Status: **LOCKED FOR EXECUTION**  
Date: 2026-07-21  
First teaching surface: `24-06748-RNVS / 107 GARAGE`

This document supersedes the geometry proposal, reference-selection, repair,
and approval portions of `FULL_PROCESS_LOCKED.md` and
`GEOMETRY_REBOOT_V1.md`. Their page routing, project-first ingestion, scale,
provenance, topology, estimating, and project-held-out evaluation rules remain
in force.

## 1. Why the reset exists

The July 17 pipeline produced useful diagnostics but did not produce qualified
flooring truth. It performed this sequence:

1. a vision model proposed a polygon;
2. code searched nearby PDF vector segments for parallel candidates;
3. code measured the proposal against its selected candidate;
4. code colored the original proposal by the resulting verdict; and
5. the workbench exposed those verdicts as if they were ready for approval.

That sequence is backwards. A precisely measured distance to the wrong drawing
line is not flooring evidence. The system must first establish what physical
event stops the flooring, then establish the drawing evidence representing
that event, and only then use vector measurement for placement.

No existing colored edge-gate image is approved geometry or training truth.
It is retained as diagnostic evidence and as a regression baseline.

## 2. Product question

For each flooring area, the product must answer:

> What real floor receives this finish, where does that floor stop, and what
> evidence supports every part of that boundary?

The product question is not:

> Which nearby PDF line is closest to the model polygon?

## 3. Vocabulary shown to people

- **Flooring area**: one connected physical area being measured. It may have
  one room identity, several identities in an open area, or part of one room
  when finishes change.
- **Boundary side**: one continuous piece of the flooring-area perimeter
  between direction changes. Internal code may call it an edge; the founder
  and customer UI says boundary side.
- **Boundary meaning**: the physical reason flooring stops or continues at a
  side.
- **Drawing evidence**: the wall face, threshold, finish-transition mark,
  exterior limit, or other plan evidence supporting the boundary.
- **Draft**: a machine proposal. Never truth.
- **Approved geometry**: a corrected boundary with every side explained and
  reviewed under the current qualification rules.

## 4. Boundary meanings are chosen before lines

Every boundary side receives exactly one status from the following contract
before vector snapping or inch measurement can approve it:

| Meaning | Plain-English rule | Typical drawing evidence |
|---|---|---|
| `wall_face` | Flooring stops against the room-facing surface of a wall. | The inside stroke of the wall assembly. |
| `threshold` | Two separately measured areas meet through a doorway/opening. | Jamb-to-jamb threshold line or locked estimating convention. |
| `finish_transition` | Flooring material changes without a wall. | Finish boundary, hatch change, keyed note, or detail. |
| `open_continuation` | Flooring continues; this is not a true physical boundary. | Absence of a boundary plus shared finish/scope evidence. |
| `exterior_limit` | Exterior/deck flooring stops at a physical perimeter. | Slab/deck/parapet edge selected under exterior policy. |
| `exclusion` | A shaft, opening, column, or other no-floor region is removed. | Closed obstruction/void evidence. |
| `unresolved` | Current documents do not justify a boundary. | A structured blocker, never an invented line. |

A single straight proposal side may cross different meanings—for example wall,
door threshold, then wall. In that case it must be split into separate
boundary sides before approval. A long line cannot be approved merely because
one short section overlaps a plausible vector segment.

## 5. New per-room execution loop

```text
Original plan crop and project context
                 ↓
Identify the physical flooring area and identity memberships
                 ↓
Draft a closed boundary
                 ↓
Assign a physical meaning to every boundary side
                 ↓
Find visible drawing evidence for each meaning
                 ↓
Independent critic tries to disprove the draft and evidence
                 ↓
Correct geometry and split mixed-meaning sides
                 ↓
Use vector/PDF measurement only for confirmed evidence
                 ↓
Re-run boundary, topology, scale, and area checks
                 ↓
Show a plain-English before/after to a qualified reviewer
                 ↓
Approve, correct again, or record unresolved
```

The drafter may use a vision model, promptable segmentation, vectors, or a
combination. The critic must be a separate pass without access to the drafter's
confidence argument. Agreement between machine passes is evidence, not truth.

### 5.1 Agent-with-tools evidence loop

“Meaning before measurement” does not mean a semantic agent hands work to a
dumb one-shot nearest-line script. For every side, the agent can iteratively:

1. inspect the full viewport, neighboring areas, openings, schedules, notes,
   and details;
2. ask the geometry tool for all plausible vector/raster candidates in a
   bounded region;
3. overlay candidates on the source and reject dimension, furniture, far-wall,
   partial, or wrong-side evidence;
4. select, combine, split, or trace the evidence matching the physical meaning;
5. redraw the boundary and receive deterministic failure feedback; and
6. repeat up to the declared round limit.

For a mixed side, the agent must split it—for example wall face -> threshold ->
wall face—rather than force one vector reference across the whole run. For a
scan or undrawn transition, the agent may create reviewed raster/semantic
geometry without a native PDF segment. The deterministic tool remains the
ruler, coordinate engine, and contradiction detector; it does not decide what
the architecture means.

A separate verifier challenges the final evidence and geometry. After two
failed correction rounds, the result becomes structured `unresolved`; the
drafter may never certify itself by repeating its own reasoning.

## 6. Human-facing room screen

The default screen shows one room/flooring area at a time and answers, in this
order:

1. What floor are we measuring?
2. What did the machine draw?
3. What does every boundary side represent?
4. What evidence supports each side?
5. What is still uncertain?
6. What changed during correction?
7. What square footage results from the corrected geometry?
8. What decision is being requested from the reviewer?

Internal names (`e0`, `max_deviation`, candidate scores, PDF points) and raw
edge strips are hidden under optional technical evidence. Colors never carry
meaning alone; every status includes words and the required next action.

## 7. Room 107 is the teaching gate

Room 107 must be completed before bulk room review resumes. The locked teaching
package must contain:

- original plan crop;
- machine draft and its four current sides;
- each side's proposed physical meaning;
- visible evidence selected for each meaning;
- explicit machine disagreements;
- corrected geometry, or an honest unresolved blocker;
- before/after area calculated from the same verified viewport scale;
- reviewer decision and provenance; and
- a statement of training eligibility.

Current status on 2026-07-21: **diagnostic only; no corrected/approved geometry
exists**. The existing systems disagree:

- Claude vision proposed a four-side rectangle with confidence `0.7`;
- the first edge inspector marked all four sides `correct`;
- a later blind audit flagged the east wall jog as a missed shape detail; and
- the vector edge gate called the top reference unresolved, the right and
  bottom sides major redraws, and the left side a measured pass despite only
  partial reference overlap.

Those contradictions are blockers, not votes to average.

## 8. Training and RunPod gate

No geometry model training starts from the July 17 outputs. RunPod remains off
until all of the following exist:

1. Room 107 teaching gate completed and understandable to the founder.
2. One complete project reviewed under this boundary-meaning-first contract.
3. At least one qualified flooring estimator audits the ambiguous boundary
   conventions and a sample of completed areas.
4. Diverse development projects supply corrected masks/polygons and boundary
   meanings with project-level splits.
5. A versioned training manifest excludes diagnostic-only and unresolved data.

The first trained model improves drafting. It never replaces the independent
evidence, geometry, topology, and human gates.

## 9. Immediate execution order

1. Publish the Room 107 teaching package and guided UI.
2. Establish and record the correct Room 107 boundary side by side.
3. Produce a corrected polygon and rerun measurement/topology/area.
4. Get qualified review of Room 107 and lock the resulting rule examples.
5. Apply the identical workflow to five straightforward Baronne rooms.
6. Add irregular/open/specialty cases; finish the complete project denominator.
7. Repeat on diverse development projects.
8. Train only after the data and portfolio gates pass.

## 10. Stop conditions

- Never approve a side whose physical meaning is unknown.
- Never treat nearest-line selection as semantic confirmation.
- Never move a boundary by a displayed inch value until the underlying drawing
  evidence is confirmed.
- Never use printed schedule area to choose a candidate polygon.
- Never hide unprocessed or unresolved areas from project denominators.
- Never call a machine-reviewed polygon human-verified.
