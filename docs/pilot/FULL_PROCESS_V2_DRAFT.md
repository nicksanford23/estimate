# Full process v2 — DRAFT FOR LOCK (round 2)

Written 2026-07-17 (Claude Fable). Supersedes FULL_PROCESS_V1_DRAFT (kept
unchanged). All 11 Codex round-1 blockers ACCEPTED and incorporated below;
per-blocker disposition at the end. **Codex: respond LOCK or numbered
blockers.** Normative rules only — execution status lives in STATE.md.

## 0. Frame

A human estimator sets a scale, clicks points around each room, and software
turns clicks into square footage. Our system makes the machine do the
clicking; qualified humans approve. The same factory serves pilot projects
today (rented AI) and produces the verified data that later replaces the
rented AI with our own model.

## 1. Pipeline (one project, start to finish)

S1. PAGES — classify every page (floor plan, schedule, other; phase, level,
    confidence, reviewer, uncertain-flag). ALL source pages are preserved
    permanently; "kept" is a REVERSIBLE routing status, never deletion.
    Page-label QA includes deliberate audit/active-learning samples, not
    only pipeline byproduct. Outputs: routing statuses + trimmed views
    (PDF/images) derived non-destructively.

S1.5 PLAN-SET MAP — before any roster work: active revision selection,
    proposed vs existing phase per sheet, floor levels, sheet relationships
    (keys, enlarged-plan references, matchlines), viewport identification.
    Missing/ambiguous members are explicit blockers.

S2. ROSTER + ANCHORS — room roster = UNION of schedule rows and plan
    labels; conflicts preserved, never silently resolved. room_identity
    (a scheduled/labelled name) is explicitly distinct from
    physical_surface (a floor region); schedules never create geometry
    boundaries. Anchors from PDF text coordinates (door-tag disambiguation
    rule); visual placement fallback; explicit no_anchor/no_plan gaps.

S3. EVIDENCE PACKET (multi-scale) — per room: full-floor context view,
    full-room crop (crop MUST contain the entire room; crop borders
    visually marked, never usable as boundary evidence), numbered edge
    strips, neighboring polygons, immutable PDF coordinates + transforms.
    Raster resolution derives from drawing scale with a floor sufficient
    to resolve the 1.5-inch acceptance test, not a fixed pixel count.
    Open-zone suspects use full-level context by default.

S4. DRAFT — vision AI places the outline (ordered polygon, per-edge notes,
    confidence), blind to all printed SF.

S5. CRITICIZE — an independent vision pass judges every numbered edge
    (fresh context minimum; pilot policy: independent reviewer on all
    rooms, cross-vendor on disputes/failures plus a random sample of
    passes; cross-vendor is not a permanent per-room cost after
    calibration). Rejected edges get specific instructions.

S5.2 SURFACE-MODEL GATE (semantic, before measurement) — catches
    wrong-object errors so precision is never spent on the wrong thing:
    open-zone duplication (N identities on one continuous surface ->
    ONE physical surface with identity memberships), stair/specialty
    classification (never room rectangles), unsupported room splits,
    duplicate/near-duplicate surfaces. Failures route to structural
    repair (S6), bypassing measurement.

S5.5 MEASURE — the reference-confirmed gate:
    - the script NOMINATES candidate reference boundary segments from PDF
      vector data (parallel/overlap/length filters, double-line wall-pair
      detection, artifact penalties for arcs/dimensions/furniture/hatch),
      records chosen candidate + runner-up + machine rationale;
    - a QUALIFIED REVIEWER CONFIRMS the exact reference segment (per-edge
      during pilot; batched/sampled confirmation only after the nominator's
      accuracy is calibrated and documented);
    - only after confirmation may mathematics issue pass_measured: max and
      mean perpendicular deviation, endpoint deviation, angle/curve
      deviation, in inches at drawing scale; proof image (proposal +
      confirmed reference + printed measurement) stored per edge;
    - verdicts: pass_measured (max dev <= 1.5 in vs confirmed reference)
      | minor_adjustment (provisional repair-routing category, <= 4 in,
      NEVER a pass; threshold to be calibrated by prototype) |
      major_redraw | wrong_surface_model | unresolved_evidence (also the
      mandatory outcome when no reference can be confirmed);
    - AREA: printed schedule area is never an acceptance signal. Where
      QUALIFIED reference geometry exists, area error against it is a
      required SECONDARY gate alongside edge deviation (per label book
      A8); where none exists, area error is recorded as unknown and the
      result stays provisional. (Label book A8 wording to be reconciled
      to this exact statement in its own lock cycle.)

S6. REPAIR — snap rejected edges to the CONFIRMED reference (vector math);
    visual redraw only where no vector exists (scans);
    wrong_surface_model requires structural redraw, never edge snapping.
    ALL repaired surfaces re-enter S5 (criticism) AND S5.5 (measurement),
    not measurement alone. Max 2 repair rounds, then structured
    unresolved.

S7. TOPOLOGY (floor-level, after all repairs) — deterministic checks:
    overlaps, gaps between adjacent surfaces, duplicates, shared-edge
    disagreement, unmapped schedule identities; obstruction/hole layer
    recorded as observed evidence (observed | uncertain | not_present),
    policy application deferred to Layer B.

S8. HUMAN GATE — two distinct effects, never conflated:
    (a) PRODUCT decision: the pilot reviewer (founder; later customer)
        accepts/edits/rejects rooms ranked by measured severity; append-
        only, identity + book/policy versions stamped, Neon+R2 backed.
    (b) TRAINING eligibility: created ONLY when the full evidence record
        exists (confirmed references, precision gates, surface-model and
        topology gates, schema validation) AND the decision is by a
        qualified reviewer with audited samples. A click without the
        evidence chain locks the product view, not training truth.
    Layer-B trade-policy defaults require a qualified estimator, never
    founder guesses.

S9. TRAIN + BOOTSTRAP (exploratory until promotion gates pass) —
    - >=150 eligible rooms across >=2 projects under a locked label book
      grants permission for an EXPLORATORY run only, never production
      replacement;
    - model-agnostic bakeoff against the rented-AI + vector baseline (no
      architecture is presumed the winner);
    - splits by whole projects AND architect/design families; dataset +
      model versions snapshotted; original labels never overwritten;
    - every iteration evaluated on fixed validation projects + regression
      sample of previously accepted rooms; sealed exam projects untouched
      by rerun/retrain forever;
    - promotion AND rollback metrics defined before any deployment;
    - bootstrap reruns on training projects are permitted, but new model
      output never becomes truth by self-agreement: it re-enters the full
      S5-S8 chain like any draft.

## 2. Roles

- Scripts: rendering, cropping, transforms, nomination, snapping,
  measuring, topology, area math — exact, free, auditable.
- Rented vision AI (now) / trained model (later): S4 draft + S5 criticism.
  The trained model replaces S4 first; S5 stays independent of S4.
- Cross-vendor (Claude/Codex): S5 disputes/failures + pass samples during
  pilot; periodic full blind audits as calibration scaffolding.
- Qualified reviewer(s): S5.5 reference confirmation; S8 decisions.
  Founder is the pilot reviewer; the truth model names roles, not one
  individual. Qualified estimator: Layer-B policy only.

## 3. Data strategy

- TRAINING pile: many projects, whole-project processing; partial room
  coverage acceptable ONLY with the complete denominator recorded — every
  unprocessed room carries an explicit state (unresolved / no_plan /
  not_yet_reviewed); omissions must never be confidence-selected; hard
  cases deliberately included.
- EXAM pile: 4-6 complete buildings across architects at 100% including
  hard rooms; 2 sealed untouched until final claims. Production claims
  require project + architect diversity beyond the training floor.
- Diversity beats volume; a bad label is worse than a missing label;
  machine agreement is never truth.

## 4. Round-1 blocker dispositions (all accepted)

1 S1 non-destructive + deliberate QA sampling: incorporated (S1).
2 Plan-set map: incorporated (S1.5).
3 Roster union + identity/surface split: incorporated (S2).
4 Multi-scale, scale-derived evidence packet: incorporated (S3).
5 Nominate-then-confirm; determinism bounded: incorporated (S5.5);
  batching allowed only after documented calibration.
6 Area reconciliation: incorporated (S5.5); A8 stays dual-gate where
  qualified reference geometry exists; label book edit queued.
7 4-inch = provisional routing only: incorporated (S5.5).
8 Early surface-model gate: incorporated (S5.2).
9 Repairs re-enter criticism + measurement; structural redraw for
  wrong_surface_model: incorporated (S6).
10 Click != training truth; product decision vs training eligibility
  separated: incorporated (S8).
11 S9 exploratory-only, model-agnostic, snapshotted, regression-tested,
  promotion/rollback pre-defined: incorporated (S9).
Doc hygiene: status content removed to STATE.md.
