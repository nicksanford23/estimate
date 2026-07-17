# Codex review — Geometry Label Book v1 draft

Reviewed 2026-07-17 against
`docs/pilot/GEOMETRY_LABEL_BOOK_V1_DRAFT.md`, the project-first execution
lock, the geometry reboot plan, and the current annotation-packet schema.

## Verdict

The draft is a strong foundation and is aimed at the correct problem: flooring
quantity zones rather than generic architectural rooms. It should remain
**DRAFT** and must not yet qualify training truth.

The principal blocker is that it mixes two different kinds of truth:

1. **observable geometry:** the physical surface, obstruction, and boundary
   shown by the drawing; and
2. **estimating policy:** what an estimator includes, deducts, wastes, measures
   separately, and prices.

These must be represented separately. A geometry model should not need to be
retrained because a contractor changes its cabinet, column, stair, or waste
policy.

## Foundations to keep

The following decisions are correct and should survive into the locked book:

- The label target is a flooring quantity zone, not automatically an
  architectural room.
- Boundaries distinguish `wall`, `finish`, `exterior`, and `open_split`.
- Open spaces may contain multiple scheduled identities without inventing a
  wall or unsupported split.
- Ambiguous evidence produces `unresolved`; a guessed polygon is never useful
  training truth.
- Only the confirmed proposed-plan viewport contributes primary quantity.
- Printed schedule area is compared only after drawing. It must not select or
  reshape a candidate mask.
- Reviewer decisions and model proposals remain separate from qualified human
  truth.
- Rule changes require a new book version and re-review of affected zones.

## Required structural change

The locked system should have three connected but distinct rule layers.

### Layer A — observable geometry

Records what the plan supports:

- physical finish surface or room footprint;
- wall face, finish transition, exterior edge, open split, or unresolved edge;
- doors/openings;
- shafts, cores, columns, casework, fixtures, stairs, and other obstructions;
- source drawing, viewport, coordinates, and edge-level evidence.

### Layer B — estimating policy

Records how a company converts geometry into a bid quantity:

- include or exclude flooring under casework and fixtures;
- minimum obstruction/column deduction;
- stair measurement method;
- treatment of closets, alcoves, thresholds, decks, and existing surfaces;
- waste, rounding, minimum-order, and material-specific rules.

The same geometry may be processed by different policy versions without
changing the training mask.

### Layer C — annotation and review

Records how a proposal becomes qualified evidence:

- machine proposal and score;
- positive/negative prompts and editing actions;
- corrected geometry;
- unresolved reason;
- reviewer identity and qualification;
- geometry-book version and estimating-policy version;
- human decision and evidence-eligibility state.

## Trade authority

The `FOUNDER ANSWER` fields should become `TRADE POLICY DECISION` fields.

Nick may approve the product behavior and business policy, but the initial
answers for door thresholds, closets, stairs, casework, columns, exterior
surfaces, and measurement tolerances should be established or confirmed by a
qualified flooring estimator. AI-proposed defaults are questions for that
expert, not authoritative trade rules.

Future truth need not be confirmed only by Nick. The binding rule should be:

> A qualified, authorized human reviewer creates the decision; eligibility is
> granted separately under the evidence-governance rules.

Nick can remain the pilot reviewer without hard-coding one individual into the
permanent truth model.

## Rule-specific findings

### R1 — wall face

Following the room-facing wall surface is a sound observable-geometry default.
The estimator should confirm how finish thickness, base, and poorly resolved
double-line walls affect the tolerance.

### R2 — doors and openings

“Under the closed door leaf” is geometrically ambiguous on a plan that shows a
swinging leaf. Define a straight threshold segment between the jambs and state
whether it aligns to the wall center, closed slab center, or a finish-transition
line. Separate physical finish continuity from accounting splits between two
scheduled identities.

### R3 — closets and alcoves

The schedule is useful identity/scope evidence, but a schedule row does not by
itself create a visible boundary. A separately scheduled closet with no
defensible line must be an open-zone member or unresolved accounting split,
not an invented wall.

### R4 — decks, balconies, and exterior surfaces

These surfaces must receive explicit outcomes and cannot be silently skipped.
However, absence of a finish from one schedule is insufficient to conclude
`not_in_scope`. That outcome requires affirmative scope evidence from the
contract documents or an authorized policy decision.

### R5 — open areas

The “never invent a wall” rule is excellent. Preserve one physical zone with
member identities when no defensible split exists. Only a visible finish edge,
dimensioned division, or qualified policy split may create a separate boundary.

### R6 — stairs

A planar stair footprint is not necessarily the installed flooring quantity for
treads, risers, landings, nosings, or stringers. Add an outcome such as
`specialty_surface` or `nonplanar_measurement`. Store the plan footprint as
observable geometry, then apply a separate stair-measurement policy. Do not
train ordinary room-SF automation on stair footprint as if it were field floor.

### R7 — casework, fixtures, islands, tubs, and built-ins

Whether to measure wall-to-wall or deduct an obstruction is estimating policy,
not universal geometry truth. Label the obstruction and whether the drawing
supports floor beneath it; let the policy choose the quantity treatment.
“Absorbed as waste” should not be a geometry-label assumption.

### R8 — columns and obstructions

A fixed two-foot threshold is a company/material policy. Geometry should retain
the obstruction and its dimensions. The policy can decide whether its area is
deducted.

### R9 — precision and curves

A universal three-inch edge tolerance may create unacceptable percentage error
in small closets and bathrooms. Store both coordinate/edge tolerance and
resulting area error. Curve approximation should be governed by maximum chord
error or area error at the resolved scale, not only one-foot segment spacing.

### R10 — unresolved

Keep this rule essentially unchanged. Require a structured unresolved reason,
such as `clipped`, `illegible`, `contradictory`, `missing_scope`,
`missing_finish_boundary`, or `external_reference_required`.

### R11 — drawing selection

Keep the confirmed proposed-plan viewport rule. Add phase/scope metadata so
“existing” linework inside a proposed viewport is not confused with an
unrelated existing/demo view elsewhere on the sheet.

## Annotation-schema changes required before labeling

The current annotation packet has one `polygon_pdf` field and a flat
`boundary_types` list. That cannot represent the geometry and evidence needed
by the reboot architecture.

The next schema should support:

- `Polygon` and `MultiPolygon` geometry;
- interior rings/holes for shafts, cores, and deducted surfaces;
- disconnected pieces belonging to one quantity zone;
- edge or segment identifiers;
- one boundary type and source-evidence reference per edge;
- explicit room/schedule membership independent of spatial label containment;
- observable obstructions independent of deduction policy;
- `specialty_surface` / nonplanar outcomes;
- structured unresolved reasons;
- geometry-book and estimating-policy versions;
- original machine proposals separated from final human geometry.

Example conceptual shape:

```text
quantity zone
├── member identities: 107
├── surface geometry
│   ├── exterior ring
│   │   ├── edge: wall
│   │   ├── edge: finish
│   │   └── edge: exterior
│   └── interior ring: masonry shaft
├── observed obstructions
├── estimating policy reference
└── human decision / eligibility state
```

## Reviewer-checklist changes

The checklist should additionally require:

- valid, non-self-intersecting geometry with explicit holes/multipart pieces;
- no unexplained overlap between neighboring quantity zones;
- explicit gaps, missing scheduled spaces, and unresolved coverage;
- edge-level boundary provenance;
- correct coordinate transform back to the immutable source PDF;
- no schedule-area-driven mask selection;
- separation of physical geometry from policy deductions;
- area-error checks scaled to room size;
- external room-label or leader-link exceptions when a legitimate label is not
  physically inside the polygon.

The current “polygon contains its own room label” rule should remain a strong
default, not an absolute requirement. An external tag or leader may establish
identity if its source relationship is explicit and reviewed.

## Recommended path to lock

1. Keep the current file as the preserved Claude v1 draft.
2. Create a v2 draft separating observable geometry, estimating policy, and
   annotation/review rules.
3. Upgrade the annotation packet before confirming any geometry labels.
4. Have a qualified flooring estimator answer the trade-policy questions using
   real examples from `24-06748-RNVS`.
5. Test the proposed rules on all 36 spaces, including stairs, decks, closets,
   garage, open zones, finish-only boundaries, shafts, and small obstructions.
6. Resolve contradictions and publish the exact list of affected tasks.
7. Lock `geometry-label-book-v1` only after the rules and schema agree and the
   authorized human reviewer accepts the pilot examples.

## Final opinion

The draft has the right objective, strong no-guessing discipline, and a useful
boundary vocabulary. Its essential correction is not a different AI model; it
is a cleaner definition of truth. Train the model on observable, sourced
geometry. Apply company-specific flooring estimating policy afterward. That
separation will make both the training data and the eventual estimating product
more consistent, auditable, and reusable.
