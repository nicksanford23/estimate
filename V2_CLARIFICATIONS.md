# V2 Clarifications Log — image-loop Q&A → schema/build notes

*Running log of founder questions during design review and the decisions
they produced. Folded into SCHEMA_V2.md at checkpoints. Started 2026-07-10.*

## From Page Review image (round 1)
1. Page Review shows ONE SECTION PER relevant downloaded doc (arch set,
   revisions, etc.); paperwork docs stay in Source Files only. Progress
   counter = building-wide; per-doc counts in section headers.
2. Sheet titles display the ARCHITECT'S extracted text verbatim (grey until
   confirmed); we never editorialize titles; hybrid content is expressed by
   flags. ("SITE PLAN + INDEX" in the mock was prompt shorthand — build
   shows "SITE PLAN".)
3. Full ~15-category taxonomy in the picker (mock showed 8 for space).
4. Kill the word "hybrid" in UI — show the actual flags (max 2 + "+n").
   Status badges (geometry ✓ / suggested / unlabeled) live in the card
   corner, never in the label row. Three chip families: category / flags /
   status — visually distinct.
5. CHIP COLOR LAW: dashed outline = machine suggestion (heuristic, vision
   agent, or model — all are observations); solid = human-confirmed. Only
   solid resolves as truth.

## From labeling walkthrough Q&A
6. KEEP is a derived, VERSIONED POLICY, not a stored fact:
   keep_policy_v1 = {floor_plan, finish_plan, finish_schedule, demo_plan}
   for Model-1/takeoff-measurement. Product page-retention uses a separate
   display_policy (includes cover_index etc.). Changing either is a
   one-line policy edit; labels never need re-touching.
7. Categories mirror discipline organization: architectural content gets
   fine-grained categories (it's our subject); MEP/structural stay coarse.
8. multiple_viewports is PER-PAGE (several drawings on one sheet).
   Project/floor structure is derived: pages → levels via sheet titles +
   the level table; never a flag.
9. contains_area_table detection runs on EVERY page regardless of
   category (SF + area/total vocab patterns) — catches title-sheet area
   blocks like 13-44121's per-floor/unit table (the "silver" miss).
10. All label/verdict changes are append-only decisions with actor+time+
    reason; Activity tab surfaces meaning-changing events.

## Open items for next checkpoint
- Level assignment UX: where does Nick confirm "A1.2 = Level 1"? (likely
  Page Review side panel, small level dropdown on floor-plan pages.)
- Project-level rollup card ("3 floors, plans p7-15, schedule p24") on
  Summary tab — derive from confirmed labels.
- Checkpoint rule: fold this log into SCHEMA_V2 after the Geometry Review
  image round, before slice-1 build starts.

## CHECKPOINT 2026-07-11: items 1-10 + image rounds 2-4 folded into
## SCHEMA_V2 §14 (v1.4). Log continues fresh from here for the pilot.

## From the Togal teardown (2026-07-11, see togal_teardown/TEARDOWN_DECISIONS.md)
11. PROPOSED for next checkpoint: extend space.kind (or a parallel
    room_type claim) with a room-type taxonomy (corridor, unit, living,
    bedroom, bathroom, closet, utility, stairs, elevator, shaft,
    balcony, lobby) + exclusion-reason vocabulary ("excluded: shaft",
    "not flooring scope", "duplicate", "bad closure") — exclusions are
    explicit states, never deletions.
12. PROPOSED: lightweight run/page rating claim (great|ok|poor) as a
    machine-feedback observation, alongside (not replacing) structured
    geometry_annotation corrections.
13. DESIGN BACKLOG (needs mockup rounds before build — spec-driven-dev):
    coverage reconciliation panel (assigned/excluded/review/unmeasured +
    coverage %), class-level bulk select verbs, exclusion-with-reason UI.
14. Geometry pipeline: emit perimeter LF per room polygon (wall-base
    quantity); room-label text harvested per polygon.
