# Togal teardown — converged decisions (Claude ⊕ GPT cross-review)

*2026-07-11. Inputs: CLAUDE_INDEPENDENT_ANALYSIS.md (blind) +
GPT_ANALYSIS.md (blind) + Nick as tiebreaker. Both analyses were produced
without seeing each other — items BOTH found independently are
high-confidence. This doc is the actionable output; the two analyses are
the evidence.*

## A. Converged findings (both models, independently — treat as settled)

1. **The wedge is the schedule join.** Togal's material assignment is
   100% manual; nothing connects its chat's finish-schedule reading to
   its room polygons. Our pipeline (finish_schedule pages →
   schedule-reader → room-name↔schedule join → SF per material) automates
   away the entire middle chapter of their demo.
2. **No trust model.** Every Togal number renders with identical
   authority — no confidence, no review states, no provenance, even
   though the demo itself shows misclassification (balconies as
   "Shafts"). Our trust states (dashed/cross-verified/confirmed) attack
   exactly this.
3. **Happy-path demo.** One clean, orthogonal, repetitive plate;
   "works on any floor plan" claimed, never shown; no boundary
   corrections shown anywhere in the video.
4. **Class-level bulk assignment is the interaction to steal** —
   room-TYPE detection is what turns 183 polygons into ~6 decisions.
5. **Don't copy the uniform success-green**, don't rely on Great/OK/Poor
   as a flywheel (satisfaction ≠ what failed), don't make claims shaped
   like "any floor plan."

## B. Adopted from GPT (Claude missed or under-weighted)

1. **Coverage reconciliation panel** — GPT's best contribution. Their
   demo leaves 15,524 SF detected vs ~12,708 SF assigned with no
   accounting. Ours shows, per page/building: assigned /
   excluded-with-reason / awaiting-review / unmeasured + coverage %.
   Turns our honesty rule into a visible, demo-able feature Togal lacks.
2. **Exclusion states instead of deletion** ("Excluded: elevator shaft",
   "not flooring scope", "duplicate", "bad closure") — deletion erases
   the evidence of failure; explicit states preserve training signal and
   audit trail. Fits append-only decisions natively.
3. **Pricing inherits verification state** ($X verified / $Y pending
   review / $Z estimated) — for the future estimate view; never a bare
   dollar next to an unverified quantity.
4. **Benchmark-shaped counter-claims**: % of SF accepted without
   correction, median estimator review time per 50k SF, unresolved rooms
   at export, performance published BY PLAN CATEGORY (clean vector /
   flattened / raster / renovation / open-plan). These become
   demo-readiness metrics.
5. **Fair self-skepticism to keep**: our differentiators are designs
   until the pilot proves them; CAD-layer training may not transfer to
   flattened rasters (probe 30b measured exactly this); schedule joins
   fail when room names/numbers don't align — instrument that failure
   mode from day one.

## C. Claude-only findings that survive (GPT missed)

1. **Forensic cracks in their demo**: 85 "Shafts" on one floor, tile EA
   math ~1.5–2% below naive division with NO waste factor, 1,359 vs
   1,361 SF same-selection discrepancy, per-item delete confirm modals.
   Ammunition for the evidence-first pitch.
2. **Room-name-text advantage**: their classifier called apartment
   "UNIT A2" rooms "Hotel Room" — it ignores text sitting on the
   polygon. We get that text natively from vectors.
3. **Ingest scale benchmark**: 513-page set auto-classified, 305
   autonamed, ~10–15 s per-plate detection, "4.5-minute" single-page
   takeoff — measure our pipeline in their units.
4. **Their feedback flywheel is real but coarse** — we build the
   3-level rating AND structured correction capture (SCHEMA_V2
   geometry_annotation already specifies the rich payload).

## D. Adjustments to current work (what changes NOW)

**Before/at the ML architecture session (FABLE_FINAL_DAYS §5):**
1. The boundary-model track gains a **room-TYPE objective** (or a
   room-label-text harvesting stage) — type labels are what enable bulk
   assignment, junk exclusion, and the schedule join. Starter taxonomy =
   Togal's observed classes (corridor, unit/guest room, living, bedroom,
   bathroom, closet, utility, stairs, elevator, shaft, balcony, lobby).
2. **Junk/exclusion classes** (shaft, chase, core, sliver <~20 SF) as
   explicit negative outputs, excluded from flooring SF by default.
3. **Perimeter LF per room polygon** emitted by the geometry pipeline
   (free — polygons exist; = wall-base quantity).
4. Demo-data sufficiency analysis (§5b) gains the benchmark units from
   C3 and the by-plan-category claim structure from B4.

**V2 build/design (through the design loop — these amend approved
screens, so they get mockup rounds, NOT ad-hoc builds):**
5. Coverage reconciliation panel/bar (B1).
6. Class-level bulk select verbs in Geometry Review (A4) alongside the
   locked bulk-accept.
7. Exclusion-with-reason verdicts in the UI (B2).

**Schema (logged in V2_CLARIFICATIONS for the next SCHEMA_V2
checkpoint — constitution is not edited ad hoc):**
8. space.kind taxonomy extension for room types + exclusion reasons as
   a claim/verdict vocabulary.
9. Rating capture (great/ok/poor) as a lightweight claim on runs/pages.

**Explicitly NOT doing (validated by both analyses):**
- All-trades object counting (furniture, fixtures).
- Generic CAD transforms (flip/rotate/copy) before the core review loop.
- Chat as a headline feature (useful later; spec-reader, not takeoff).
- Pricing columns before the verification-state machinery exists.
- Chasing their 10–15 s raster segmentation head-on — we win on the
  join + evidence, not generic speed.

## E. Standing intel tasks (cheap, background)

- Mine "Togal vs PlanSwift/Bluebeam/Onscreen" pages, patents, release
  notes for claimed metrics and training-data story (feeds §5b).
- Trial/demo access with a deliberately hard plan set (raster,
  renovation, open-plan) when feasible.
- Forums/reviews focused on correction time and failure modes.
