# ML Two-Building Pilot Execution Plan

*Draft v1.1, 2026-07-11. This replaces the proposed separate five-page
coordinator test. The coordinator is proven on the two real pilot buildings,
starting with a small page batch and then continuing through each building.
This is an execution plan, not an ML accuracy claim or a locked roadmap.*

## 0. Decisions Already Made

1. Pilot only two buildings before choosing a larger data or model program.
2. Two independent vendors label the same rendered source images: Claude
   Sonnet and Codex.
3. Exact per-claim agreement becomes machine cross-verified (soft confirmed),
   never automatic human truth.
4. Nick resolves every disagreement directly; no third-agent adjudicator.
5. Nick audits a stratified 10% of agreements to detect correlated mistakes.
6. Nick confirms every consequential scale, quantity, exclusion, room link,
   and output used in a takeoff or demo.
7. Nick does not author labels blind. His confirmations are binding human
   decisions with `blind=false`.
8. Old labels and probe outputs are preserved but quarantined from truth and
   model gates. They may be audited later for measured weak-training use.
9. The first demo is an end-to-end assisted workflow with visible trust and
   coverage states. No geometry-automation accuracy claim is locked in advance.
10. Existing permit-based URLs migrate to canonical buildingId routes.
11. One neutral repo-local MCP server is the coordination surface. Codex can
    call Claude, Claude can call Codex, and either can launch the isolated
    dual-page workflow. It is plumbing, not a truth source.

## 1. Pilot Buildings

### Building A - Geometry-Centric

| Field | Value |
|---|---|
| Permit | `26-10321-RNVN` |
| Current V2 inventory | 42 pages, one legacy geometry run, no schedule rows |
| Why selected | Manageable complete plan set and an existing geometry artifact for shadow comparison |
| Primary learning | Page labeling, viewport/scale, geometry review, correction burden, material evidence from plans |

### Building B - Schedule-Centric

| Field | Value |
|---|---|
| Permit | `24-06748-RNVS` |
| Current V2 inventory | 15 pages, one schedule region, 36 candidate rows, no V2 geometry run |
| Why selected | Small plan set with a real area-schedule candidate, complementary to Building A |
| Primary learning | Page labeling, table extraction, field confirmation, schedule-to-space join, schedule-versus-geometry limits |

1. All existing machine observations, schedule rows, and geometry runs on
   these buildings are legacy candidate evidence. The pilot does not inherit
   their truth status.
2. These two buildings intentionally cover different paths. A single building
   is not required to prove every station.

## 2. Honest UI/UX Status Today

| Surface | Status | What is real | What is missing or provisional |
|---|---|---|---|
| Buildings index | Partial build | Reads V2 buildings and page counts | Still links by permit, no global V2 nav, no plan-set/revision summary |
| Page Review | Functional thin slice | Real page images, category picker, eight flags, append-only human decisions, supersession, keyboard navigation | No dual-agent results, soft-confirmed state, agreement audit, viewport confirmation, scale confirmation, blind/isolated worker controls, or quarantine awareness |
| Rooms & Finishes | Partial legacy-backed slice | Real schedule page, candidate rows, row confirmation, bulk confirmation, extracted/printed totals | One backfilled schedule at a time, heuristic rather than exact row crop, no field editing, no dual-agent comparison, no canonical spaces or joins, no evidence card |
| Geometry Review | Partial legacy-backed slice | Existing baked overlay, region/run/room verdict writes, issue list, bulk accept | No live polygon geometry, real room crops, overlay toggles, zoom-to-room, redraw/split/merge/trace tools, viewport/scale workflow, or correction annotations |
| Work Queue | Approved image only | Design exists | Route and data-backed lanes not built |
| Building Summary | Not built | Mockup requested | Active plan set, levels, coverage, and blockers missing |
| Source Files / Activity | Not built | IA is specified | Plan-set assembly, revisions, provenance activity missing |
| Coverage reconciliation | Not built | Two-axis model agreed | No page/building calculations or UI |
| Datasets / Models / Pipeline | Not built in V2 | Schema concepts exist; legacy ops pages exist separately | V2 traceability tables, trust eligibility, job health, retries missing |
| Dual-label coordinator | Core bridge built | Shared MCP server, bidirectional consultation, isolated parallel page workers, structured category/flag comparison, raw run artifacts, live vendor smoke test | Frozen pilot rubric, V2 observation persistence, quarantine enforcement, review queue, audit UI, batch manifest, retry/job controls |
| Customer upload/processing | Not built | Mockup requested | Upload, page filmstrip, job narration, failures missing |
| Customer takeoff review | Not built | Legacy prototype and V2 design rules exist | V2 product-facing review, evidence, bulk verbs, exclusions missing |
| Material setup / export | Not built | Inventory agreed | Waste/base/carton assumptions, verification-aware quantities/dollars, export blockers missing |

### Build Health

1. The current Next.js production build compiles when the configured Google
   Fonts are reachable.
2. ESLint is not clean: two current React errors exist, including a synchronous
   state update in `V2ReviewBoard`, plus nine warnings across the web app.
3. Conclusion: the ML workbench UI is **partially built**, not complete. Page
   Review is the most usable slice. The broader demo and pilot workflow are not
   ready yet.

## 3. Phase 0 - Make the Pilot Safe to Run

### 3.1 Truth Inventory and Quarantine

1. Produce `truth_inventory_v1` with every existing pilot observation and
   decision grouped by source, actor, claim, binding, blind status, and run.
2. Produce `pilot_quarantine_manifest_v1` before any writes.
3. Add the chosen append-only eligibility-denial mechanism; do not mutate old
   machine observations or flip immutable decision fields.
4. Snapshot builders deny quarantined or unqualified items by default.

### 3.2 Rewrite the Active Process Rules

1. Rewrite `label-pages` to emit V2 machine observations, never legacy truth
   rows or page-status updates.
2. Rewrite `review-labels` for explicit Claude/Codex run IDs and vendor-neutral
   comparison.
3. Rewrite `triage-permits`, `diagnose-model`, improvement-loop, and
   `CLAUDE.md` so machine keys are candidates and splits follow conservative
   leakage groups/plan sets.
4. Add a short versioned page-label rubric covering category, eight flags,
   uncertainty, and image-viewing requirements.

### 3.3 Build the Neutral Dual-Label Coordinator

1. Use a repo-local coordinator, not Claude calling Codex or Codex calling
   Claude.
2. For every assignment create two isolated read-only input bundles containing
   only:
   - exact rendered image;
   - source/page hash and extraction ID;
   - frozen rubric/taxonomy version;
   - identical structured-output schema;
   - assignment and run IDs.
3. Launch concurrently:
   - `claude -p --model sonnet ... --json-schema ...`;
   - `codex exec --ephemeral --sandbox read-only --image ... --output-schema ...`.
4. Prevent either worker from reading database labels, prior outputs, shared
   scratch files, or the other worker's result.
5. Validate both outputs, then compare each claim independently. Category
   agreement does not hide a flag disagreement.
6. Store both original observations plus a separate cross-verification result.
7. Route disagreements directly to Nick's review UI.
8. Start with the first 5 pages of Building A as a smoke batch. This is not a
   separate experiment: after Nick checks the coordinator mechanics, continue
   the remaining 37 pages under the same versioned run.

### 3.4 Add Minimum Pilot UI States

1. Page Review displays both vendor observations, exact agreement/disagreement
   by claim, cross-verified status, and Nick's final decision.
2. Agreement audit sampling is deterministic, stratified, and visible.
3. Disagreements deep-link to the exact page and claim.
4. Before the geometry walkthrough, Page Review adds viewport and scale
   confirmation; geometry quantities remain locked until both resolve.
5. Before Building B's schedule pass, Rooms & Finishes supports field editing,
   exact source evidence, and schedule-to-space link confirmation.
6. Before Building A's geometry walkthrough, Geometry Review supports real
   polygon coordinates, real room crops, zoom-to-room, and structured verdict/
   correction capture for the selected walkthrough region.
7. All pilot screens record elapsed review time and decision provenance.

### Coordinator Smoke Gate

1. Both workers demonstrably view the correct image.
2. Structured outputs validate and remain isolated until both commit.
3. Cross-verification never resolves as human truth automatically.
4. Nick can resolve a disagreement and audit an agreement through V2.
5. Quarantined legacy data cannot enter pilot truth or evaluation queries.
6. Web build passes and Page Review lint errors are cleared.

1. Schedule, join, scale, and geometry controls do not block the first five
   pages. Each must pass its own acceptance check before its corresponding
   pilot step begins.

## 4. Phase 1 - Building A (`26-10321-RNVN`)

### 4.1 Page Pass

1. Dual-label all 42 pages from images.
2. Compare category and flags per claim.
3. Nick resolves 100% of disagreements.
4. Nick reviews the deterministic 10% agreement sample.
5. Any overturned agreement expands the audit within that failure stratum.
6. Confirm relevant plan regions and scale evidence.

### 4.2 Geometry Walkthrough

1. Select one representative geometry-capable region after page/viewport
   confirmation.
2. Teach the workflow in the UI:
   - accepted room;
   - missed room;
   - merged or split room;
   - fake closure;
   - open zone;
   - excluded non-flooring area;
   - scale and source evidence.
3. Run rules-v4 and `wall_model_v2` only as legacy shadow candidates.
4. Nick confirms or corrects the region and all quantities shown in the pilot.
5. Record time per region, room, and correction type.
6. Do not train or choose a new architecture from this single region.

### Building A Exit Evidence

1. Complete page decision ledger.
2. Agent agreement/disagreement and Nick-overturn report.
3. Verified viewport and scale evidence for the walkthrough.
4. Structured geometry failure taxonomy and correction time.
5. Honest coverage: accepted, excluded, pending, and unmeasured.

## 5. Phase 2 - Building B (`24-06748-RNVS`)

### 5.1 Page Pass

1. Dual-label all 15 pages with the rubric version established on Building A.
2. Nick resolves disagreements and audits 10% of agreements.
3. Confirm the schedule region, relevant plan region, and scale/area sources.

### 5.2 Schedule Pass

1. Claude and Codex independently extract the schedule into the same
   field-level schema: room, name, floor, base, area, notes, source cells.
2. Compare rows and fields rather than only totals.
3. Agreement is soft confirmed; disagreement goes directly to Nick.
4. Nick confirms every row/field that contributes to a displayed quantity.
5. The printed-total comparison remains evidence, not automatic truth.

### 5.3 Join and Geometry Boundary

1. Create canonical spaces with building and level context.
2. Generate deterministic schedule-to-space link proposals.
3. Nick confirms every link used by the pilot; ambiguity stays unresolved.
4. Run current geometry engines in shadow on one representative region only
   after viewport and scale confirmation.
5. Show schedule-derived area separately from geometry-measured area; never
   double count them.

### Building B Exit Evidence

1. Complete page and schedule decision ledger.
2. Field-level agent agreement and Nick-overturn report.
3. Confirmed schedule rows and space links.
4. Source-versus-disposition coverage reconciliation.
5. List of schedule-only quantities, geometry-supported quantities, and
   unresolved quantities.

## 6. What We Measure Across Both Buildings

1. Agent agreement rate per claim and plan/schedule type.
2. Nick's disagreement decisions.
3. Nick's overturn rate on audited agreements.
4. Review minutes per page, schedule row, link, region, and correction.
5. Uncertainty and unresolved counts.
6. Page/region/scale false-suggestion failure taxonomy.
7. Schedule row and field disagreement taxonomy.
8. Geometry accepted/pending/excluded/unmeasured coverage.
9. UI confusion, extra clicks, dead ends, and missing evidence.
10. Cost and elapsed time for each vendor worker.

1. These are pilot workflow measurements. They are not general model accuracy,
   data sufficiency, or market-performance claims.

## 7. Decisions Made After Building 2

1. Whether dual-agent agreement quality is high enough for a larger weak-train
   labeling run.
2. Which legacy label sources are worth auditing for salvage.
3. How many additional buildings and plan categories are needed.
4. Whether geometry's next constraint is data, labels, rules, input quality, or
   architecture.
5. Whether probe 31 should test U-Net, graph, fusion, a cheaper baseline, or be
   deferred.
6. The sustainable agreement-audit rate based on measured time and errors.
7. The credible customer-demo claim and which trust states must remain visible.
8. Whether thin Claude/Codex plugin packaging adds value beyond the working
   project-scoped MCP server. Plugin packaging follows the pilot; the neutral
   server already exists.

## 8. Do Not Do Before the Two-Building Review

1. Do not retrain Model 1.
2. Do not run probe 31 as a decision experiment.
3. Do not promote rules-v4 or `wall_model_v2`.
4. Do not label ten buildings.
5. Do not bulk-convert legacy observations into human decisions.
6. Do not build separate Claude-to-Codex or Codex-to-Claude truth paths.
7. Do not claim geometry accuracy, broad plan coverage, or data sufficiency.
8. Do not build polished pricing/export around unverified quantities.

## 9. Immediate Work Order

1. Keep the working shared MCP bridge; do not run pilot labels yet.
2. Create truth inventory and quarantine manifest.
3. Rewrite the active labeling/truth skills and freeze the pilot rubric.
4. Connect MCP run artifacts to V2 machine observations behind quarantine
   enforcement; never auto-create human decisions.
5. Add the minimum Page Review comparison/audit states.
6. Clear the existing pilot-route lint errors and validate the web build.
7. Run Building A's first 5 pages as the coordinator smoke batch.
8. Continue Building A, perform the geometry walkthrough, then run Building B.
9. Hold a two-building review before any larger ML/data commitment.
