---
name: design-loop
description: The image-first UX design loop for the estimator product — locked design rules, review checklist, current prototype state, and how to run a design round. Read before touching web/ UI or reviewing mockups. Written 2026-07-10 (Fable) for whoever drives next.
---

# The design loop (image-first, founder-locked)

Process that produced the v0.5 review screen, in one round-trip:
Nick iterates MOCKUP IMAGES with an outside model (GPT) → the driver
(you) critiques each image against the LOCKED RULES below, adopting good
ideas and rejecting violations with reasons → when an image set is locked,
it becomes the spec → a Sonnet agent builds against it (frontend-design
skill required reading) → the DRIVER personally reviews screenshots
against the rules before Nick ever sees them → founder clicks → react →
next round. Never skip the driver-review step: agents violate the rules
innocently (three violations shipped in the first build).

STATUS 2026-07-11 (V2 era): the loop ran full-cycle and produced FOUR
APPROVED screens (design_specs/{page_review,geometry_review,
rooms_finishes,work_queue}_APPROVED.png) + SCHEMA_V2 §14 build notes.
Slice-1 thin Page Review is live at /v2. docs/legacy/PRODUCT_UX_V1.md
screens are SUPERSEDED by the approved images (its 5 trade questions
remain open).
The loop is governed by the consultation-loop and spec-driven-dev
skills. v0.5 /demo + /review/[permit] prototypes remain as legacy.

## THE IMAGE-INTERROGATION STEP (added 2026-07-11; proved itself on V2)
Before ANY mockup set is approved, the driver interrogates each image
with Nick, element by element: what is this element, what data feeds it,
what happens on click, what state is it in when machine-only vs
confirmed. Every answer that changes schema or process goes into the
clarifications log (V2_CLARIFICATIONS.md) and folds into SCHEMA_V2 at
checkpoints. This step caught keep-policy versioning, the chip color
law, per-page viewports, and area-table-on-every-page — questions a
build agent would have silently guessed at. No approval without
interrogation.

## LOCKED DESIGN RULES (violations get sent back, no debate)
1. Color = STATUS in review mode (green accepted-eligible / yellow
   review / blue open zone / red draw-needed). Material is a text chip,
   never a fill color. Material-colored fills belong to the Estimate
   step's separate view mode only.
2. NO fabricated numbers, anywhere: unmeasured rooms show "—" or
   "from schedule (labeled)". Header "Estimated" total = anchored rooms +
   open zones ONLY — never unlabeled/artifact shapes.
3. Unanchored polygons get NO table rows: one collapsed "N unlabeled
   shapes, X SF — expand" row per page; grey low-opacity on canvas.
   Yellow is reserved for anchored rooms with a real doubt.
4. Evidence over vibes: every number traceable (schedule row, printed
   dim, source sheet) via the evidence card. NO "AI" badging, NO
   confidence percentages. Doubt is words ("why flagged"), not scores.
5. Rubber base (RB-x) is LINEAR FEET wall trim — never a room's floor
   material, never an area fill. Estimators catch this instantly.
6. The plan canvas dominates the viewport; table below fold/drawer.
7. Keyboard-first: Enter=accept, arrows=next/prev flagged. Accept lives
   in ONE primary place (evidence panel).
8. Every user correction is logged (future training data). Accepted
   means locked-to-estimate; say so in microcopy.
9. Desktop-first; phone gets view/approve (big targets, no precision
   drawing); tablet+stylus is the field target. Responsive from day one.
10. Verbs: Accept / Fix Boundary / Draw Room / Split Zone. v0.5 shows
    the last three disabled with "coming in v1" tooltips — visible verb
    set, nothing fake-works.

## Review checklist for any new build/screenshot
- Any rule above violated?
- Numbers: do header totals reconcile with the table? Junk excluded?
- Do polygons align on the plan raster (spot-check one room's walls)?
- Empty states, reset-demo present; localStorage persistence works.
- Mobile viewport renders; canvas pinch-zooms.

## Backlog when the loop resumes (in order)
1. Screen 1 (upload/processing narration + page filmstrip) mockups.
2. Screen 3 (bid sheet + assumptions/exclusions block) mockups.
3. Split-zone gesture and draw-room-with-snapping (v1 interactions).
4. "Fixed by you" state + correction log wiring.
5. Nick's 5 trade questions (PRODUCT_UX_V1.md §open questions) — his
   answers re-default the review screen.

## HARD RULE (added 2026-07-11 after a violation)
Once mockups are APPROVED they ARE the spec for every build pass,
including "thin"/"fast" ones. Thin = unpolished implementation OF the
approved layout — never a different layout. The approved images live in
/workspaces/estimate/design_specs/*_APPROVED.png; every UI build prompt
must point the agent at the relevant image + SCHEMA_V2 §14 build-notes.
No driver may waive this for speed without the founder's explicit OK.
