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

STATUS 2026-07-10: v0.5 prototype BUILT in web/ (Next.js): /demo index,
/review/[permit] for 14-11290-NEWC, 26-10321-RNVN, 24-06748-RNVS; data in
web/public/demo/*.json+png (schema mirrors future DB: project/pages/rooms/
evidence). Screenshots: data/ux_proto/. Spec: PRODUCT_UX_V1.md (three
screens; only Screen 2 is built; Screens 1 and 3 have NO mockups yet).
Nick ordered the loop PAUSED after the in-flight fix pass — do not run
more rounds until he restarts it.

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
