# Upload → square footage: the full chain, first principles

*Planning doc (2026-07-05). Think before trying — each stage lists the
decision, its done-number, cheapest credible approach, and what data it
needs. Build order is top to bottom; nothing below stage N starts until
stage N has a measured baseline.*

## Execution lock — complete projects, not selected pages (2026-07-14)

The evaluation and product unit is a complete project plan set. A page is a
worker task, never the final unit of evidence. Before Stage 4 geometry runs,
the project packet must account for the active revision, every primary
level/area plan, supporting enlarged plans, schedule capabilities, proposed
plan viewports, and levels. Every required primary viewport receives an
outcome, including failures.

This prevents a successful second-floor page from being reported while the
first, third, and fourth floors are silently absent. Strict project coverage is
machine-checked with `scripts/validate_project_packet.py`.

First development project: `24-06748-RNVS` (A100 schedule; A101-A104 required
primary level plans; A201 supporting detail). Second complementary development
case: `14-11290-NEWC`, whose finish schedule provides material by room but no
area column. See `docs/pilot/PROJECT_FIRST_EXECUTION_V1.md`.

## Stage 1 — Find the pages that matter  [v1 SHIPPING NOW]
Decision: which pages of an upload does the estimator ever see?
Done: zero missed finish pages, ≥60% junk cut (currently: 100% recall @
76% cut on frozen split — thin eval, hardening via more eval labels).
Approach: text model + conservative no-text fallback; LLM referee for the
uncertain slice later. Data: the labeling factory (running).

## Stage 2 — Group pages into areas/floors
Decision: which floor plan + finish plan + schedule pages describe the SAME
area? (A set has L1/L2/L3 plans; SF is per-area.)
Done: ≥90% of pages grouped to the right floor/area on eval packets, AND 100%
of required primary level/area views accounted for before a pilot project can
claim geometry coverage. Missing views are explicit blockers, not omissions.
Cheapest: sheet-number + title-text rules ("A-101 FIRST FLOOR", "LEVEL 2")
— likely 80% from regex on data we already extract. ML only if rules stall.
Data: sheet_title is already a labeled field; no new labeling expected.

## Stage 3 — Establish scale per plan page
Decision: how many feet is one PDF unit on this page?
Done: scale correct on ≥95% of vector floor plans (verifiable: cross-check
a printed dimension string against measured coordinate distance — the page
audits itself; mismatch → flag, never silently wrong).
Cheapest: parse scale notes ("1/8\" = 1'-0\"") from pagetext + the
dimension-string cross-check. Pure code, zero ML, zero new labels.

## Stage 4 — Room boundaries (the moonshot, now just a stage)
Decision: propose room/zone geometry and the right product action for each label:
auto quantity, review geometry, redraw/correct, or split an open zone.
Done v0: ≥70% of rooms auto-proposed on vector plans, median area error
<2%, ZERO confident-but-wrong (silent bid error is the one unforgivable
failure — suppress low-confidence proposals entirely).
Route A (first): vector geometry — walls are line segments IN the PDF;
extract (fitz get_drawings on ORIGINAL PDFs, never rendered PNGs), filter
wall candidates, close door gaps, polygonize, area = geometry × stage-3
scale. ML only for "which lines are walls," rules first.
Scoring: do not grade "every room label has its own closed polygon." Open-plan
rooms may correctly share a polygon. Grade the product action instead: enclosed
room correctness, review recall for likely-wrong rooms, open-zone split quality,
and total SF sanity.
Route B (scans, later): segmentation model; polygon labels via the same
labeling factory + reviewer tier. Not before Route A has a verdict.
First probe (cheap, do before any building): extract drawings from 5
labeled floor_plan pages — do wall lines exist as clean segments, or are
sets flattened? This one stat decides Route A's ceiling.

**Complete-project checkpoint (24-06748, 2026-07-14):** v4 ran all four
required levels and found 20/36 scheduled identities but only 2/36 exact rooms
within +/-10%. A viewport-constrained rerun did not change the result. The
existing wall model regressed to 11/36 identified and 0 accurate; dual reached
21/36 identified but remained at 2 accurate. v4 stays default, model is not
promoted, and dual is review-only. The measured residual requires labeled
boundary semantics (wall vs finish vs exterior vs open split), collected as a
complete corrected project before any new training. See
`docs/pilot/24-06748-RNVS_GEOMETRY_DIAGNOSTIC_V1.md`.

**Architecture pivot:** do not spend another cycle tuning `wall_model_v2`.
The replacement target is scheduled-space/quantity-zone segmentation, seeded
by room-label point prompts and trained on complete human-corrected projects
with wall, finish, exterior, open-split, and unresolved boundary semantics.
The GPU experiment and promotion gates are locked in
`docs/pilot/GEOMETRY_REBOOT_V1.md`.

**SAM/project ladder:** first run SAM as a promptable annotation assistant on
all 36 rooms of `24-06748-RNVS`; do not use the printed SF to choose among its
candidate masks. If proposals reduce correction effort, collect complete
human-corrected geometry from three to four diverse development projects, then
train candidates and score them unchanged on two untouched projects. The
initial planning range is 150-300 corrected zones, split strictly by project
and revision. One project proves plumbing; it cannot prove generalization.

**GPU posture:** prepare the four viewport images, 36 prompts, transforms,
container, result schema, timeout, and cleanup locally before adding RunPod
credit. Use a temporary on-demand Pod for the smoke test and terminate it after
verified result retrieval. Use scale-to-zero Serverless Flex only if the model
reaches intermittent production. Secrets live in restricted environment
storage, never chat, logs, artifacts, or git.

## Stage 5 — Attach finishes to rooms
Decision: which flooring material does each enclosed room or open zone get?
Done: ≥90% of rooms matched to schedule rows on docs that have schedules.
Cheapest: extract the finish-schedule table (rows: room → floor/base) and
join on room number/name from stage 4 polygons' text labels. Table
extraction = LLM-assisted at first (low volume, keep-pages only), distilled
later exactly like page classification was.
Open-plan caveat: some commercial areas are divided by finish boundaries, not
walls. Those labels should flow from Stage 4 as `open_zone_split`, then Stage 5
uses finish tags/layers/schedules to split the blob into material zones.

## Stage 6 — Quantities and the estimate
Decision: SF per material (+ base LF, waste factors) per area.
Done: total within 2% of a human takeoff on test projects.
Pure arithmetic over stages 3-5. Waste/rounding rules come from Nick (trade
knowledge — the one input no model provides).

## Stage 7 — The product surface
Confidence-ranked review UI: model proposes, human confirms; every human
correction is a NEW LABEL flowing back to the factory (labels from
customers are free and perfectly distributed). The app is the flywheel's
final form.

## Sequencing + budget posture
1→2→3 are cheap, mostly rules, and independently useful (a v1 that finds,
groups, and scales pages already beats tools that do none of it).
4 is the hard bet — probe before building. 5 unlocks "estimate" vs
"measure." Fable/Opus plan and diagnose; Sonnet + scripts build; every
stage gets its done-number BEFORE its first experiment.
