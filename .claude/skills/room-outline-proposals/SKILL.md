---
name: room-outline-proposals
description: Generate machine room-outline proposals for a complete project (crops -> Claude-vision polygons + optional SAM cross-check -> editor preload) and route them to human review. The proposal factory feeding geometry training data. Written 2026-07-17 (Fable) after the 24-06748-RNVS bake-off.
---

# Room-outline proposal pipeline

Turns a complete plan set into per-surface outline PROPOSALS and routes them
through the locked measured gate to human review. Proposals are MACHINE
observations; only a qualified reviewer's per-edge confirmation makes training
truth. Never skip that sentence when explaining status.

**Authority: `docs/pilot/FULL_PROCESS_LOCKED.md` (v1.0).** This skill is the
operational recipe for its S1-S10 project flow + T-LOOP/M1-LOOP; if this file
and the locked doc ever disagree, the locked doc wins. Read STATE.md first.

## The canonical unit is the SURFACE, not the room
One continuous open floor is ONE physical_surface_region with room identities
as MEMBERSHIPS (great-room 305/306/307 = one surface; deck 404/405 = one
surface). One surface = one geometry decision = one training label, counted
once; identities counted separately. Two denominators always: identity count
AND surface count (see `surfaces.json`).

## Project flow (per project) — maps to locked S1-S10
- **S1 PAGES / S1.5 PLAN-SET MAP** — classify pages; pick active revision;
  level plans, viewports, schedule capability, roster. Missing members are
  explicit blockers. Roster = UNION of schedule rows + plan labels.
- **S1.7 SCALE GATE (blocking)** — `scripts/scale_gate.py`: per viewport record
  scale + source + >=1 independent dimension check (parse a printed dim, find
  its vector dimension line, measure the span, compare printed vs measured).
  Status verified_machine until founder countersign. NO inch measurement passes
  downstream while a viewport is unverified.
- **S2 ANCHORS** — room-label text coords from PDF words, whitelisted by roster,
  INSIDE the proposed-plan viewport. Door-tag rule (proven): room tag = hit with
  "SF" token directly below; REJECT hits whose right neighbor is "|" (door tags
  share the numbering). Graphics-only labels -> place visually, mark
  anchor_provenance=visual_manual; unplaceable -> no_anchor, never dropped.
- **S3 EVIDENCE PACKET** — one packet PER SURFACE (overlapping/open identities
  consolidate first). Crop from ORIGINAL PDF (fitz clip), longest side ~1000px,
  px_per_ft + transforms recorded with round-trip self-test (<0.01pt). Crop
  borders are never boundary evidence; auto-expand + rerender when an edge nears
  the border. Open/clipped zones -> use the FULL level viewport as the crop
  (the 305/306/307 room-sized-crop failure).
- **S4 DRAFT** — one vision agent per level, background, parallel; apply the
  GEOMETRY_LABEL_BOOK R1-R11; output ordered polygon in ORIGINAL image px,
  outcome, per-edge boundary_notes, confidence. IGNORE printed SF (the answer
  must not shape the proposal). Agents never read SAM (independence).
- **S5 CRITICIZE** — independent vision pass judges every numbered edge; cross-
  vendor on disputes/failures + random pass samples.
- **S5.2 SURFACE-MODEL GATE** — `scripts/consolidate_surfaces.py`: collapse open
  duplication to one surface; stairs -> specialty_stair, elevators -> shaft
  (never room rectangles) -> needs_founder; unsupported splits/duplicates ->
  wrong_surface_model -> S6 structural redraw, BYPASSING measurement.
- **S5.5 MEASURE (reference-confirmed)** — `scripts/edge_gate.py --full` over the
  ordinary surfaces. Script NOMINATES the room-facing reference per edge from
  PDF vectors (parallel/overlap/length + double-line pair detection), records
  chosen + runner-up + rationale, measures max/mean/endpoint deviation at
  verified scale, and writes a proof image per edge (proposal magenta, chosen
  green, runner-up/outer yellow) + per surface. Reference-selection guards:
  (a) CHASE-JUMP GUARD — reject a candidate when a wall pair (or aggregated
  fragmented near face) lies between the edge and it; prefer the room-facing
  line of the FIRST assembly outward; no near ref -> unresolved_evidence.
  (b) EXTERIOR-EDGE RULE — on deck/parapet edges emit BOTH inner + outer
  candidates and mark ambiguous_pending_reviewer; never guess.
  Verdicts: pass_measured (<=1.5in) | minor_adjustment (<=4in) | major_redraw |
  wrong_surface_model | unresolved_evidence | ambiguous_pending_reviewer.
- **S6 REPAIR** — snap rejected edges to the CONFIRMED reference; wrong_surface_
  model needs structural redraw, never snapping. Any coordinate change re-enters
  the FULL chain S5 -> S5.2 -> S5.5 -> S7. Max 2 rounds, then unresolved.
- **S7 TOPOLOGY** — floor-level overlaps/gaps/duplicates/shared-edge/unmapped
  identities; obstruction layer recorded as observed evidence.
- **S8 HUMAN GATE** — (a) PRODUCT: reviewer accepts/edits/rejects SURFACES ranked
  by measured severity (`QUEUE.json`: confirm_reference_and_accept | fix_edge |
  needs_judgment); one shared surface = one decision + one label. (b) TRAINING
  eligibility only when the full evidence record + per-edge confirmed references
  pass AND a qualified reviewer decides. Saves append to
  `data/geometry_annotations/human/<permit>.outcomes.jsonl` — that file, nothing
  upstream, is truth.
- **S10 LAYER-B ESTIMATING/EXPORT** — associate finishes with LOCKED surfaces;
  obstruction/stair/waste policy; takeoff + exceptions + export. Never mutates
  locked geometry; exceptions raise structured upstream tasks (page->S1, scale->
  S1.7, identity->S2, geometry->S6, policy->S10) and regenerate under a new
  version.

## Improvement loops (async, never per-project steps)
- **T-LOOP** (geometry model): training-eligible SURFACE regions (S8b), splits by
  whole projects AND architect/design families; >=150 eligible surfaces / >=2
  projects / locked label book -> exploratory bakeoff vs the vector+rented-AI
  baseline; sealed exam opened ONCE; deployed models replace S4 first (S5 stays
  independent); rerun output is a draft re-entering S5-S8, never truth by self-
  agreement.
- **M1-LOOP** (page router): verified page labels, splits by whole projects;
  false-negative on important page types is the primary metric; deploy only as a
  REVERSIBLE routing assistant, source pages untouchable.

## Hard rules (non-negotiable)
- Machine agreement = evidence, NEVER truth. No proposal becomes training data
  without an explicit per-edge reviewer decision.
- AREA IS NEVER AN ACCEPTANCE SIGNAL; printed schedule SF is diagnostic AFTER
  prediction only — it never selects a candidate or sizes a prompt/box/polygon.
- Reference eligibility, machine observations, and decisions are APPEND-ONLY;
  history is never overwritten; every artifact stamps its S4 §-contract fields.
- Dependency invalidation (§3.5): a changed page/revision/scale/roster/geometry
  makes all downstream artifacts STALE — resume from the earliest changed stage.
- Projects, not pages; every surface carries an explicit state
  (unresolved/no_plan/not_yet_reviewed); hard cases deliberately included; a bad
  label is worse than a missing one.
