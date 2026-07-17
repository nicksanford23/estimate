# Geometry Label Book v2 — REVIEWED DRAFT (consultation round 2)

Status: **REVIEWED DRAFT v2 — architecture accepted, rules/schema not locked.**
Codex round-2 review completed 2026-07-17. No outline is training truth
against this book until the implementation and lock gates at the end pass.
Supersedes the v1 draft, which is preserved unchanged at
`docs/pilot/GEOMETRY_LABEL_BOOK_V1_DRAFT.md`. Until locked, no outline is
training truth against this book.

Written 2026-07-17 (Claude), merging the v1 draft with the Codex review
(`GEOMETRY_LABEL_BOOK_CODEX_REVIEW_V1.md`). Binding architecture:
`GEOMETRY_REBOOT_V1.md`, `PROJECT_FIRST_EXECUTION_V1.md`. Proposal mechanics:
`.claude/skills/room-outline-proposals/SKILL.md`.

## Round-2 disposition

- The three-layer architecture is accepted.
- The V1 simple-room fast path is **rejected for training truth**. V1 rows may
  remain machine/human proposals, but they must be re-reviewed into V2.
- `not_in_scope` is a Layer-B scope verdict, not a Layer-A geometry outcome.
- Geometry resolution and scope resolution are stored separately.
- A8 requires both applicable precision gates, not either one.
- The normative machine-readable record shape is
  `docs/pilot/schema/geometry_annotation_v2.schema.json`.
- The existing web editor remains a V1 proposal/review tool until it writes
  and validates the complete V2 record. Saving in that editor does not grant
  training eligibility.

## What this document is

The written rules for recording an observable **floor surface region** on a
plan viewport, then converting it into a **flooring quantity zone** under a
versioned estimating policy. We are not blindly tracing architectural rooms.
Layer A answers "what floor surface and defensible boundaries does the drawing
show?" Layer B answers "how is that surface grouped and measured for this bid?"

The essential correction from round 1 (Codex): the book previously mixed two
kinds of truth — what the drawing physically shows, and what an estimator
chooses to include, deduct, waste, and price separately. **These are now
separated into three layers.** A geometry model must never be retrained
because a contractor changes its cabinet, column, stair, or waste policy.

- **Layer A — observable geometry:** what the drawing supports. Trainable.
- **Layer B — estimating policy v0:** how geometry becomes a bid quantity.
  Provisional AI defaults awaiting a qualified estimator. Swappable without
  touching Layer A.
- **Layer C — annotation & review:** how a proposal becomes qualified truth.

Consistency is the point: a model cannot learn a boundary rule that changes
from room to room. If a Layer-A rule is wrong, we version the book and
re-check affected zones. **Layer-B policy changes NEVER change a Layer-A
geometry label and NEVER require relabeling.**

## Vocabulary

- **Surface region** — observable floor geometry supported by the drawing.
- **Quantity zone** — one or more surface regions grouped for measurement by a
  Layer-B policy. Usually one scheduled room; an open region may have several
  member identities.
- **Boundary type** (per edge) — `wall`, `threshold`, `finish` (material
  change, no wall), `exterior` (edge of deck/balcony/building), `open_split`
  (a visible annotation/dimension defining a division without a physical wall
  or finish line), `unresolved`.
- **Geometry status** — `resolved`, `partial`, or `unresolved`.
- **Zone form** — `enclosed`, `open`, or `finish_defined`.
- **Surface kind** — `ordinary_floor` or `specialty_surface`.
- **Scope status** (Layer B) — `unreviewed`, `in_scope`, `not_in_scope`, or
  `unresolved`.

---

# Layer A — Observable geometry (the trainable truth)

A labeler applies these rules from the drawing **alone**. No schedule area, no
policy judgment. Record what the plan supports; where it doesn't support an
answer, say so.

### A1 — Wall face
The outline follows the **room-facing inside face of the wall** — where
flooring meets the wall. Never centerline, never far side. On double-line
walls, trace the line facing the room. (Finish-thickness/base offset is a
Layer-B tolerance question, not a Layer-A choice.)

### A2 — Doors and openings (Codex R2 fix)
At a door or cased opening, the boundary is a **straight `threshold` segment
between the two jambs** — not the swinging leaf arc, which is geometrically
ambiguous in plan. Record, per segment, which reference the segment aligns to:
`jamb_line` (default), `wall_center`, or `finish_transition`. Keep **physical
finish continuity** (does material run through?) separate from the
**accounting split** between two scheduled identities; the segment geometry is
Layer A, the decision to split quantities is Layer B.

### A3 — Finish transitions
Where material changes with no wall, the edge is `finish`, placed on the
**visible finish-plan/legend transition line**. Only a drawn/legible material
edge creates a `finish` boundary; a schedule row alone does not.

### A4 — Exterior edges
Decks, balconies, patios, building perimeter: trace the physical edge,
boundary type `exterior`. The surface is always recorded (never silently
skipped — skipping hides missing coverage). **Whether it is in flooring scope
is Layer B**, not a Layer-A skip.

### A5 — Open zones with member identities (never invent a wall)
One physical space shared by multiple schedule rows is **one surface region
with all member identities listed** (`zone_form: open`). Split it only by a
**visible finish edge** (`finish`) or a **visible drawn/dimensioned division**
(`open_split`). A schedule row alone can never create an `open_split`. If no
defensible line exists, keep one zone and record the member identities —
**never invent a wall or an unsupported split.**

### A6 — Stairs as specialty_surface (Codex R6)
Record the **plan stair footprint** as observable geometry, `surface_kind:
specialty_surface`. A planar footprint is NOT the installed quantity for
treads, risers, landings, nosings, or stringers. Never train ordinary room-SF
automation on stair footprint as field floor; the stair-measurement method is
a Layer-B policy applied later.

### A7 — Obstructions RECORDED, not policy-judged (Codex R7/R8 fix)
Casework, islands, tubs, built-ins, columns, shafts, chases, masonry cores:
**record each as an obstruction** with its footprint/dimensions and whether
the drawing shows floor beneath it (`floor_beneath`: `yes`/`no`/`unknown`).
Layer A does **not** decide whether the area is deducted or absorbed as waste —
that is Layer B. Full-height shafts/cores that clearly have no floor are
recorded as interior rings (holes) because no surface exists there; a cabinet
with floor beneath it is an obstruction record, not a hole.

### A8 — Precision, scale-aware (Codex R9)
No single universal inch tolerance. Store both the **edge/coordinate error**
and the **resulting area error at resolved scale**. For a qualified reference
geometry, both applicable gates must pass:

> **area error <= 2% per surface region AND maximum edge deviation <= 1.5
> inches from the reviewed drawing line at drawing scale.** Small
> closets/baths are often constrained by the area gate; large open regions by
> the edge gate.

"Area error" means error against independently reviewed/reference geometry,
never difference from a printed schedule area. If no qualified reference
exists, record the precision values as unknown and treat the label as
provisional; do not manufacture a numeric pass.

Curves are approximated to a **maximum chord error** (same 1.5 in / 2% test),
not a fixed 1-ft segment spacing. Corners snap to linework.

### A9 — When you can't tell: structured unresolved (Codex R10)
If the drawing genuinely doesn't show the boundary, record `geometry_status:
unresolved` (or `partial` if only a portion is defensible) with a **structured
reason** from:
`clipped`, `illegible`, `contradictory`, `missing_boundary_evidence`,
`missing_finish_boundary`, `external_reference_required`. **Never guess** — a
guessed polygon is poison; an unresolved label is useful data.

### A10 — Which drawing counts (R11 + phase metadata)
Outlines are drawn only inside the confirmed **proposed-plan viewport** for
that level. Room tags in existing/demo plans, enlarged details, legends, or
schedules are never outlined. **Record phase/scope metadata per viewport** so
"existing" linework inside a proposed viewport is not confused with an
unrelated existing/demo view elsewhere on the sheet.

---

# Layer B — Estimating policy v0 (PROVISIONAL — awaiting trade authority)

These are the v1 draft's policy-flavored defaults, restated as **provisional
settings**, status `provisional_ai_default`. They exist so an expert has
something concrete to correct. **AI-proposed defaults are questions for a
qualified flooring estimator, not authoritative trade rules.**

Authority split (Codex, adopted in spirit): **Nick approves product behavior
and business policy; a qualified flooring estimator establishes or confirms
the trade defaults** below using real `24-06748-RNVS` examples.

**Changing any Layer-B setting NEVER changes a Layer-A geometry label and
NEVER triggers relabeling.** The same mask is reprocessed under the new policy
version.

| ID | Provisional default | Awaiting decision on |
|----|--------------------|----------------------|
| B1 casework/fixtures | Measure wall-to-wall; floor under cabinets/fixtures absorbed | Deduct vs. absorb; per material |
| B2 columns/obstructions | Ignore obstructions < ~2 ft on a side; deduct larger | The threshold; per material |
| B3 closets/alcoves | Follow schedule identity; alcoves join parent room; a separately scheduled closet with no drawn line is an `open_zone` member or unresolved split, never an invented wall | Whether closets split quantities |
| B4 decks/exterior scope | Always retain the Layer-A surface. Set Layer-B `scope_status: not_in_scope` only with **affirmative scope evidence** from contract docs, not mere absence from one schedule | What counts as in-scope surface |
| B5 stair measurement | Apply a stair method to the A6 footprint (treads/risers/landings) | The method and multipliers |
| B6 thresholds/accounting splits | Split quantities between two scheduled identities at the A2 threshold segment | When to split vs. merge |
| B7 waste/rounding/minimums | (not yet drafted) | Waste %, rounding, min order |

Every Layer-B setting carries a `status` (`provisional_ai_default` /
`estimator_confirmed`) and a policy version. Geometry from Layer A is
processed by any policy version without changing the training mask.

---

# Layer C — Annotation & review (how a proposal becomes truth)

Records how a proposal becomes qualified evidence. Every zone stores:

- **proposal provenance** — machine proposal source, score, prompt points,
  editing actions, original machine geometry kept separate from final human
  geometry;
- **reviewer identity + qualification** — who decided and their qualification;
- **version stamps** — geometry-book version and estimating-policy version;
- **geometry status, zone form, surface kind, scope status, and structured
  unresolved reason**;
- **a reference to the append-only human decision**. Evidence eligibility is
  a separate governance event and is never a mutable field inside the
  geometry annotation.

**Eligibility separation (Codex, adopted):**

> A qualified, authorized human reviewer creates the decision; eligibility is
> granted separately under the evidence-governance rules.

Nick is the pilot product reviewer without hard-coding one individual into the
permanent truth model. A geometry-qualified reviewer may approve Layer A; a
qualified flooring estimator must approve Layer B. Machine/agent agreement is
evidence, never truth.

## Reviewer checklist

A proposed or corrected outline passes only if:

1. geometry is **valid and non-self-intersecting**, with explicit holes /
   multipart pieces where present;
2. it lies inside the confirmed viewport and correct phase;
3. identity is established — the polygon **contains its own room label
   (strong default)**, OR an external tag/leader establishes identity with an
   explicit, reviewed source relationship (reviewed leader-line exception);
4. the project-level coverage validator reports **no unexplained overlap**
   with any neighboring region; explicit gaps, missing scheduled spaces, and
   unresolved coverage are called out;
5. every non-wall edge carries a **boundary type + source-evidence ref**
   (edge-level provenance);
6. the **coordinate transform back to the immutable source PDF** round-trips
   within tolerance;
7. obstructions are recorded; only true no-floor shafts/cores are holes;
   **physical geometry is separated from Layer-B deductions**;
8. **area-error check scaled to room size** (A8), not one flat number;
9. **no schedule-area-driven mask selection** — printed area is a diagnostic
   compared only after drawing, never a selector or reshaper.

---

# Schema v2 (normative machine-readable contract)

The v1 packet's single `polygon_pdf` and flat `boundary_types` cannot carry
this. The normative schema is
`docs/pilot/schema/geometry_annotation_v2.schema.json`. The shape below is
illustrative; where prose and schema differ, the schema controls until the
next reviewed version.

Validate a V2 JSON or append-only JSONL file with:

```bash
python scripts/validate_geometry_annotation_v2.py path/to/annotations.jsonl
```

This validates structure and local geometry invariants; it does not grant
evidence eligibility or replace the project-level overlap/gap audit.

```json
{
  "schema_version": "geometry_annotation_v2",
  "annotation_id": "ga_24-06748_03_307_0001",
  "task_id": "24-06748-RNVS:level_03:room_307",
  "zone_id": "24-06748-RNVS:level_03:zone_open_306_307",
  "identity_memberships": [
    {"space_code": "306", "relationship": "member"},
    {"space_code": "307", "relationship": "member"}
  ],
  "geometry_status": "resolved",
  "zone_form": "open",
  "surface_kind": "ordinary_floor",
  "scope_status": "unreviewed",
  "surface_geometry": {
    "type": "MultiPolygon",
    "polygons": [
      {
        "part_id": "part_1",
        "exterior": {
          "coordinates_pdf": [[0,0], [10,0], [10,10], [0,10], [0,0]],
          "edges": [
            {"seg_id": "e0", "boundary_type": "wall",
             "evidence_refs": ["sheet=A103;layer=A-WALL"]},
            {"seg_id": "e1", "boundary_type": "threshold",
             "alignment_reference": "jamb_line",
             "evidence_refs": ["sheet=A103;door=307A"]},
            {"seg_id": "e2", "boundary_type": "finish",
             "evidence_refs": ["sheet=A103;finish_legend=CPT-1/LVT-2"]},
            {"seg_id": "e3", "boundary_type": "open_split",
             "evidence_refs": ["sheet=A103;dimension=8ft-0in"]}
          ]
        },
        "holes": [
          {"hole_id": "h0", "hole_kind": "masonry_shaft",
           "coordinates_pdf": [[2,2], [3,2], [3,3], [2,3], [2,2]],
           "edges": []}
        ]
      }
    ]
  },
  "observed_obstructions": [
    {"kind": "column", "footprint_pdf": [...], "dims_ft": [1.5,1.5],
     "floor_beneath": "yes"},
    {"kind": "casework", "footprint_pdf": [...], "floor_beneath": "yes"}
  ],
  "precision": {"max_edge_deviation_in": 1.1, "area_error_pct": 0.9,
                "reference_geometry_ref": "review:ga_ref_307", "passes": true},
  "source": {
    "permit": "24-06748-RNVS", "onestop_doc_id": 7372349,
    "document_revision": "600 Baronne 6-28-24 Arch",
    "document_sha256": "...", "page_index": 7, "sheet_number": "A103",
    "viewport_bbox_pdf": [1961.24, 86.4, 674.18, 1879.2],
    "phase": "proposed", "viewport_transform_id": "...",
    "viewport_transform_sha256": "..."
  },
  "unresolved_reason": null,
  "versions": {"geometry_book": "v2-reviewed-draft",
               "estimating_policy": "unapplied"},
  "machine_proposal": {
    "proposal_id": "vision:307:1", "source": "claude_vision",
    "model_version": "claude-opus-4-1", "proposal_rank": 1,
    "score": 0.82, "score_type": "uncalibrated_model_score",
    "geometry_pdf": {"type": "Polygon", "coordinates": [...]},
    "prompt_points": [...], "edit_actions": [...]
  },
  "human_decision_ref": "geometry_decision:ga_24-06748_03_307_0001:1"
}
```

Required properties: `Polygon`/`MultiPolygon`; interior rings only for true
no-floor voids such as shafts/cores, never for policy deductions; disconnected
pieces under one zone (MultiPolygon);
per-edge `boundary_type` + `evidence_refs`; **membership independent of spatial
label containment**; obstruction records **independent of deduction policy**;
`specialty_surface` and structured unresolved; geometry-book + policy version
stamps; immutable source document/transform checksums; proposal score type and
model version; **machine proposal separated from final human geometry**;
human decision and eligibility stored as separate append-only records.

---

# Simple-room fast path — REJECTED FOR TRAINING TRUTH

The proposal was to lock a room under the V1 flat schema if all of:

- every edge is `wall` type;
- no interior holes;
- single polygon (not MultiPolygon);
- no open-zone membership (single scheduled identity);
- not a stair, deck/exterior, or shaft.

**Round-2 decision: reject.** The migration is not provably lossless. V1 omits
per-edge evidence, threshold alignment, immutable source/transform identity,
coordinate precision, reviewer qualification, and separate eligibility
history. A room that appears wall-only can also contain a door threshold or an
unrecorded obstruction. Adding those facts later would be reconstruction, not
lossless migration.

V1 rows remain useful as proposals or provisional review notes. They may be
displayed in the V2 editor and re-reviewed, but they are not training/evaluation
truth and receive no eligibility grant.

---

# Open items (round-2 agenda)

1. **Trade-policy decisions (B1-B7)** — pending a qualified flooring estimator,
   confirmed against real `24-06748-RNVS` examples. Nick approves product
   behavior; estimator confirms trade defaults.
2. **Schema v2 implementation** — schema contract now written; packet builder,
   editor, append-only decision records, eligibility events, and project-level
   overlap/gap validator remain to implement before confirming labels.
3. **Lock criteria (Codex path steps 4-7):** estimator answers trade questions
   on real examples (4); test all 36 spaces incl. stairs/decks/closets/garage/
   open/finish-only/shafts/small obstructions (5); resolve contradictions and
   publish the exact affected-task list (6); lock `geometry-label-book-v2`
   only after rules and schema agree and authorized geometry/trade reviewers
   accept the pilot examples (7).

## Current operational rule

Until every lock gate passes, the 36-room pilot is a **data-collection and
workflow test**, not a source of training truth. Preserve all V1 work, expose
it as proposals, and re-review project-by-project into V2. Do not start GPU
training or promote labels merely because a polygon has been saved.
