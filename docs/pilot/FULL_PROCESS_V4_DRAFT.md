# Full process v4 — LOCK CANDIDATE (round 4)

Written 2026-07-17 (Claude Fable). Supersedes V1-V3 drafts (kept unchanged).
All 5 Codex round-3 blockers ACCEPTED and incorporated; dispositions at
end. **Codex: respond LOCK or numbered blockers.** Normative rules only;
execution status lives in STATE.md.

## 0. Frame

A human estimator sets a scale, clicks points around each room, and software
turns clicks into square footage and an estimate. Our system makes the
machine do the clicking; qualified humans approve; the factory also produces
the verified data that continuously improves its own models — as a separate
loop, not as part of any single project.

## 1. Structure

```text
PROJECT FLOW (per project):   S1 -> S1.5 -> S1.7 -> S2 -> S3 -> S4 -> S5
                              -> S5.2 -> S5.5 -+-> pass: S7 -+-> pass: S8 -> S10
                                               |             `-> fail: S6
                                               `-> fail: S6 -> S5 -> S5.2 -> S5.5

IMPROVEMENT LOOPS (async):    T-LOOP  eligible geometry truth -> model ops
                                      -> improved S4/S5 models
                              M1-LOOP verified page labels -> model ops
                                      -> improved S1 routing assistant
```

## 2. Project flow

S1. PAGES — classify every page (type, phase, level, confidence, reviewer,
    uncertain-flag). ALL source pages preserved permanently; "kept" is a
    REVERSIBLE routing status; Model 1 may never delete or hide source
    pages irrecoverably. Deliberate QA/active-learning samples, not only
    pipeline byproduct. Outputs: routing statuses + non-destructive
    trimmed views (PDF/images).

S1.5 PLAN-SET MAP — active revision selection; proposed vs existing phase
    per sheet; floor levels; sheet relationships (keys, enlarged-plan
    references, matchlines); viewport identification. Missing/ambiguous
    members are explicit blockers.

S1.7 SCALE + TRANSFORM GATE — for EVERY plan viewport, before any
    inch-based work: scale and units; scale source (scale note | verified
    dimension | calibrated measurement | unknown); at least one
    independent dimension check where available; scan skew/distortion
    status; mixed-scale viewports handled per-viewport, never per-page;
    reviewer + evidence recorded. NO inch-based measurement may pass
    anywhere downstream while a viewport's scale is unverified.

S2. ROSTER + ANCHORS — roster = UNION of schedule rows and plan labels;
    conflicts preserved. room_identity is distinct from physical_surface;
    schedules never create geometry boundaries. Anchors from PDF text
    coordinates (door-tag disambiguation); visual fallback; explicit
    no_anchor/no_plan gaps.

S3. EVIDENCE PACKET (multi-scale, iterative) — per room: full-floor
    context, full-room crop, numbered edge strips, neighboring polygons,
    immutable PDF coordinates + transforms. Resolution derives from
    drawing scale with a floor sufficient to resolve the 1.5 in test.
    Because geometry does not exist at first crop: start from the anchor
    + full-floor context, then AUTOMATICALLY EXPAND AND RERENDER whenever
    a proposed edge approaches the crop boundary or any review detects
    clipping. Crop borders are visually marked and never usable as
    boundary evidence. Open-zone suspects use full-level context.

S4. DRAFT — vision model places the outline (ordered polygon, per-edge
    notes, confidence), blind to all printed SF.

S5. CRITICIZE — independent vision pass judges every numbered edge (fresh
    context minimum; pilot: independent review on all rooms, cross-vendor
    on disputes/failures + random pass samples; cross-vendor per-room is
    not a permanent cost after documented calibration).

S5.2 SURFACE-MODEL GATE — semantic check before measurement: open-zone
    duplication (one continuous surface -> ONE physical surface with
    identity memberships), stair/specialty classification, unsupported
    splits, duplicates. Failures route to S6 structural repair, bypassing
    measurement.

S5.5 MEASURE — reference-confirmed gate:
    - script NOMINATES candidate reference segments from PDF vectors
      (parallel/overlap/length filters, double-line wall-pair detection,
      artifact penalties), records candidate + runner-up + rationale;
    - a QUALIFIED REVIEWER CONFIRMS the exact reference. For anything
      TRAINING-ELIGIBLE, confirmation is PER-EDGE, always — sampling can
      support product automation later, but unconfirmed edges are
      recorded as machine-nominated, never as human-confirmed truth;
    - SCAN/RASTER PATH: where no vectors exist, a qualified reviewer
      establishes the reference segment/polyline on the raster image tied
      to verified scale and immutable source coordinates; a SECOND
      reviewer confirms it; the same deviation/proof gates then apply;
    - measurements: max + mean perpendicular deviation, endpoint
      deviation, angle/curve deviation (inches at drawing scale); proof
      image per edge (proposal + confirmed reference + printed value);
    - PASS_MEASURED, exact machine-readable definition (MEASUREMENT ONLY
      — final acceptance additionally requires S7; see branch rule below)
      — a surface passes measurement only when ALL hold:
        1. every edge's boundary type and reference are confirmed;
        2. max deviation incl. endpoints <= 1.5 in on every edge;
        3. curves meet the <= 1.5 in chord/deviation gate;
        4. area error vs the assembled confirmed reference region <= 2%
           (printed schedule area is NEVER a signal; where no qualified
           reference region exists the metric is unknown and the surface
           cannot pass);
        5. PDF/image transforms pass round-trip tolerance;
        6. the S5.2 surface-model gate has passed;
        7. no required metric is unknown (incl. verified scale per S1.7).
      Mean deviation and the provisional <= 4 in minor_adjustment
      category are routing diagnostics only, calibrated by prototype.
    - other verdicts: minor_adjustment | major_redraw |
      wrong_surface_model | unresolved_evidence (mandatory when no
      reference can be confirmed).

BRANCH RULE (explicit statuses, no circularity, no forced repair):
    S5.5 fail -> S6 -> S5 -> S5.2 -> S5.5. S5.5 pass ->
    status measurement_passed_candidate -> S7. S7 fail -> S6 (full
    chain). S7 pass -> status geometry_gate_passed -> S8. Surfaces
    needing no repair never enter S6.

S6. REPAIR (the loop) — snap rejected edges to the CONFIRMED reference;
    reviewer-referenced redraw on scans; wrong_surface_model requires
    structural redraw, never snapping. EVERY repair or human edit that
    changes coordinates re-enters the FULL chain: S5 -> S5.2 -> S5.5 ->
    S7 (-> S8 re-decision if previously decided). S7 failures also route
    back to S6. Max 2 repair rounds per surface, then structured
    unresolved.

S7. TOPOLOGY — floor-level deterministic checks after all repairs:
    overlaps, gaps, duplicates, shared-edge disagreement, unmapped
    schedule identities; obstruction/hole layer recorded as observed
    evidence (observed | uncertain | not_present).

S8. HUMAN GATE — two distinct effects:
    (a) PRODUCT decision: qualified reviewer (founder now; customer
        later) accepts/edits/rejects rooms ranked by measured severity;
        append-only, versions stamped, Neon+R2 backed. Coordinate-
        changing edits repeat the gates (S6 rule) before any further
        effect.
    (b) TRAINING eligibility: exists only when the complete evidence
        record (per-edge confirmed references, precision gates, S5.2,
        S7, schema validation) passes AND the decision is by a qualified
        reviewer with audited samples.
    Layer-B trade-policy defaults require a qualified estimator.

S10. LAYER-B ESTIMATING + EXPORT (the product output) — associates finish
    identities with locked physical surfaces; applies obstruction/
    deduction policy, stair/specialty measurement rules, waste rules;
    assigns products and pricing; produces the takeoff, an exceptions
    list, and exports. NEVER mutates locked Layer-A geometry; every
    quantity traces to locked surfaces + a named policy version.
    UPSTREAM CORRECTION ROUTE — S10 exceptions create structured tasks:
    missing/wrong page -> S1/S1.5; scale conflict -> S1.7; missing room
    identity or finish conflict -> S2; geometry problem -> S6 + full
    revalidation chain; policy problem -> S10 policy revision. After
    upstream correction, affected quantities and exports regenerate under
    a new version; locked history unchanged.

## 3. Improvement loops (asynchronous, never per-project steps)

T-LOOP (geometry model operations):
    - CANONICAL UNIT: the physical_surface_region. Geometry evidence,
      approval, and training eligibility attach to surfaces; room
      identities are memberships (one open surface with identities
      305/306/307 is ONE training mask, counted once; identity count
      reported separately). Room anchors may start evidence collection,
      but overlapping identities consolidate before geometry approval.
    - input: training-eligible surface regions (S8b), versioned dataset
      snapshots, splits by whole projects AND architect/design families;
    - >=150 eligible physical surface regions / >=2 projects / locked
      label book grants
      EXPLORATORY runs only; model-agnostic bakeoff vs the rented-AI +
      vector baseline; original labels never overwritten;
    - every iteration: fixed validation projects (evaluated repeatedly
      during development) + regression sample of previously accepted
      surfaces;
    - SEALED EXAM LIFECYCLE (one-use): a sealed project is opened ONCE,
      for a declared model/version claim; after opening it retires to
      historical evaluation; its failures are never used to tune the
      claimed model; the sealed pool is replenished before the next
      major final claim;
    - promotion AND rollback metrics defined before deployment; deployed
      models replace S4 first (S5 stays independent);
    - bootstrap reruns allowed on training projects; rerun output is a
      draft re-entering S5-S8 — never truth by self-agreement.

M1-LOOP (page-routing model operations):
    - verified page labels versioned; splits by whole projects;
    - false-negative rate on important page types is the primary metric;
    - train, compare against the current router, deploy only as a
      REVERSIBLE routing assistant (S1 statuses stay reversible; source
      pages untouchable).

## 4. State & handoff contract (every stage output)

Every artifact any stage produces records: project, document, revision,
page, source hash; input and output artifact IDs; pipeline/run ID; model,
prompt, code, and rule-book versions; reviewer identity and qualification
version; status, timestamps, structured blocker; supersedes relationship
(append-only, history never deleted). UI queues and dashboards operate
from these canonical statuses only.

REVIEWER QUALIFICATION: defined by a calibration set, minimum measured
performance on it, and periodic blind audit; qualification is versioned
and stamped on every decision. "Qualified reviewer" in this document
always means a role meeting the current qualification version — the
truth model names roles, never individuals.

## 5. Data strategy

- TRAINING pile: many projects, whole-project processing; partial coverage
  acceptable only with the complete denominator recorded — every
  unprocessed room carries an explicit state (unresolved / no_plan /
  not_yet_reviewed); omissions never confidence-selected; hard cases
  deliberately included.
- EXAM pile: 4-6 complete buildings across architects at 100% including
  hard rooms; 2 sealed untouched until final claims. Production claims
  require diversity beyond the training floor.
- Diversity beats volume; a bad label is worse than a missing label;
  machine agreement is never truth.

## 6. Round-3 blocker dispositions (all accepted)

1 S1.7 scale + transform gate added; unverified scale blocks all inch
  measurement: incorporated.
2 Canonical unit = physical_surface_region; "150 eligible physical
  surface regions"; identities are memberships counted separately:
  incorporated (T-LOOP + S5.5/S8 language).
3 Circularity removed: pass_measured = measurement only; explicit branch
  statuses (measurement_passed_candidate, geometry_gate_passed); clean
  surfaces never forced through S6: incorporated (branch rule + §1).
4 Sealed exam one-use lifecycle + retirement + replenishment:
  incorporated (T-LOOP).
5 S10 upstream correction routes + versioned regeneration: incorporated
  (S10).
(Rounds 1-2 dispositions: see V2/V3 drafts.)
