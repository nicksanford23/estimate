# Upload → square footage: the full chain, first principles

*Planning doc (2026-07-05). Think before trying — each stage lists the
decision, its done-number, cheapest credible approach, and what data it
needs. Build order is top to bottom; nothing below stage N starts until
stage N has a measured baseline.*

## Stage 1 — Find the pages that matter  [v1 SHIPPING NOW]
Decision: which pages of an upload does the estimator ever see?
Done: zero missed finish pages, ≥60% junk cut (currently: 100% recall @
76% cut on frozen split — thin eval, hardening via more eval labels).
Approach: text model + conservative no-text fallback; LLM referee for the
uncertain slice later. Data: the labeling factory (running).

## Stage 2 — Group pages into areas/floors
Decision: which floor plan + finish plan + schedule pages describe the SAME
area? (A set has L1/L2/L3 plans; SF is per-area.)
Done: ≥90% of pages grouped to the right floor/area on eval packets.
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
Decision: propose room polygons the user accepts/adjusts vs draws.
Done v0: ≥70% of rooms auto-proposed on vector plans, median area error
<2%, ZERO confident-but-wrong (silent bid error is the one unforgivable
failure — suppress low-confidence proposals entirely).
Route A (first): vector geometry — walls are line segments IN the PDF;
extract (fitz get_drawings on ORIGINAL PDFs, never rendered PNGs), filter
wall candidates, close door gaps, polygonize, area = geometry × stage-3
scale. ML only for "which lines are walls," rules first.
Route B (scans, later): segmentation model; polygon labels via the same
labeling factory + reviewer tier. Not before Route A has a verdict.
First probe (cheap, do before any building): extract drawings from 5
labeled floor_plan pages — do wall lines exist as clean segments, or are
sets flattened? This one stat decides Route A's ceiling.

## Stage 5 — Attach finishes to rooms
Decision: which flooring material does each room get?
Done: ≥90% of rooms matched to schedule rows on docs that have schedules.
Cheapest: extract the finish-schedule table (rows: room → floor/base) and
join on room number/name from stage 4 polygons' text labels. Table
extraction = LLM-assisted at first (low volume, keep-pages only), distilled
later exactly like page classification was.

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
