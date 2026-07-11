# ML Roadmap Review - Round 1

*Outside review, 2026-07-11. Read against `CLAUDE.md`, `STATE.md` from
Rung-2c onward, `SCHEMA_V2.md` v1.4, `V2_CLARIFICATIONS.md` 11-14, the
improvement/design-loop skills, both probe 30 reports, the converged Togal
teardown, and all four approved screen images. This is a consultation round,
not a lock. All proposed data volumes below are planning priors to be replaced
by leakage-safe learning curves. I accept the founder-verification debt in
section 0 as real; none of the inherited metrics becomes ground truth merely
because it is repeated here.*

## A. CLARIFYING QUESTIONS

1. **What does BUILT mean in the screen map?** The three review routes and
   components exist, but is the claim that they are fully backed by V2
   identities/decisions/jobs, or that the approved interaction shell renders?
   Pilot readiness depends on that distinction.

2. **Is the schedule-only path intentionally limited to area-bearing
   schedules?** A conventional room-finish schedule often supplies finish
   codes but no room SF. Such a schedule can automate material assignment, but
   cannot produce a quantity takeoff without geometry or another area source.

3. **What exactly does Station 1's "full recall" cover?** All four keep-policy
   categories, finish pages only, or every category plus all eight flags? The
   current 0.267 number is finish recall, while the proposed product gate reads
   like a gate for every page needed downstream.

4. **Does "zero clicks" at the join mean zero clicks to a complete proposal,
   or zero clicks to binding truth?** The latter conflicts with
   `SCHEMA_V2.md`: machine output is an observation and a current
   `space_source_link` depends on a binding human decision.

5. **What is the denominator of coverage?** Gross building area, net floor
   area, the union of accepted plan regions, printed schedule area, or known
   canonical spaces? Coverage cannot be a defensible percentage until its
   denominator and source are displayed.

6. **Does "perimeter LF (wall base)" mean raw polygon perimeter or bid-ready
   base LF?** Raw perimeter is useful evidence. Base LF additionally needs
   scale verification, door/opening deductions, scope exclusions, and rules
   for casework, glazing, and sides of shared boundaries.

7. **Where will Station 3's room-type and junk labels come from?** CAD wall
   layers weakly label boundary segments; they do not label bedroom, corridor,
   shaft, or flooring-scope exclusion. That objective currently has no stated
   confirmed-claim source.

8. **What is the first bounded demo claim?** "Works on selected area-schedule
   projects," "works on clean vector tenant plans," and "works on arbitrary
   flooring plan sets" imply radically different evidence and data volumes.

9. **Is `[permit]` temporary route debt?** The locked identity model and IA
   make building the top-level object, while a building can have many permits
   and plan sets. A route named `/b/[permit]` encodes the identity conflation
   that V2 was designed to remove.

## B. SUGGESTIONS

1. **Add Station 0: intake, identity, and plan-set assembly.** It should ingest
   immutable files, associate permit/building/level, establish document roles
   and revision/supersession proposals, and require confirmation of the active
   plan set before downstream joins. **Reason:** a perfect schedule-to-room
   matcher can still create a wrong bid by joining different revisions or
   levels. `SCHEMA_V2.md` makes `plan_set` load-bearing, but the roadmap starts
   after that work is assumed complete. **Cost:** moderate backend/query work
   plus a real Source Files/plan-set design round; no new ML.

2. **Add Station 2b: scale resolver and verifier.** Inputs should include
   printed scale text/OCR, viewport transform, page dimensions, and one or more
   printed-dimension cross-checks. Output should be a typed machine observation
   and, for verified quantities, a binding scale decision. It must abstain on
   disagreement. **Reason:** probe 30 could not downstream-grade 6 of 10
   holdouts because scale was unverified. SF and LF are unsafe without this
   stage. **Cost:** moderate deterministic/OCR engineering and a compact
   confirmation control in Page or Geometry Review; low model-training cost.

3. **Keep `takeoff.py` as the reproducible CLI facade, not the production
   workflow owner.** Implement each station as an idempotent job handler with a
   versioned input/output contract; let `takeoff.py` submit or synchronously
   execute the same DAG for research and replay. **Reason:** a single in-process
   orchestrator is poorly matched to V2's async queue, retries, partial reruns,
   addenda, and exact per-stage provenance. **Cost:** moderate refactor; it pays
   back in retry isolation and reproducibility.

4. **Split Station 3 into three components:** 3a boundary/closure, 3b space
   semantics and exclusion proposals, and 3c derived quantities. Start 3b with
   room-label text, schedule evidence, deterministic normalization, and LLM
   fallback; train a type model only after corrections accumulate. **Reason:**
   the objectives have different labels, failure modes, and adequate engines.
   Multi-tasking them now would make probe 31 uninterpretable. **Cost:** low
   architecture/documentation work now; one additional eval set later.

5. **Use four explicit gates: research, shadow, bounded demo, bid/export.** A
   research candidate may beat a baseline; a shadow candidate must abstain and
   route disagreements correctly; a demo candidate must clear absolute safety
   and review-load thresholds on a sealed benchmark; bid/export quantities
   must inherit human verification. **Reason:** "promote," "ship," and
   "demoable" currently blur together. A model can beat rules-v4 while still
   missing 26.4% of addressable rooms. **Cost:** low schema/documentation cost,
   moderate evaluation work.

6. **Build a sealed geometry truth set before calling Station 3 shippable.**
   Keep TRUTH_AREA for quantity reconciliation, but add fully corrected room
   polygons, room identities, exclusions, and scale evidence on cluster-new
   regions. Preserve probe 26-30 permits as development data because their
   grader accumulated fixes on them. **Reason:** schedule SF can expose an area
   mismatch but cannot prove boundary location, fake closures, or the correct
   split/merge. **Cost:** high human cost: roughly 40-60 fully reviewed regions
   for a first credible benchmark; the selected-room correction policy can
   reduce training cost but not sealed-eval completeness.

7. **Retain `split_v1` as a historical regression set, not the future sole
   Station 1 ship gate.** Create a new snapshot with leakage-group and
   firm-cluster separation, a calibration split, and a sealed founder-audited
   test. Report recall and kept fraction with confidence intervals by category,
   firm, and plan type. **Reason:** the current eval contains only 15 finish
   pages and all later permits default to train, so it becomes less
   representative as the corpus grows. **Cost:** low code cost, moderate
   labeling/audit cost.

8. **Specify field-level schedule metrics and constrained join metrics.** For
   Station 4 measure row recall, cell/field exactness, note/legend propagation,
   duplicate rows, and totals; do not accept total agreement alone. For Station
   5 use a level-aware bipartite assignment with uniqueness/cardinality rules,
   aliases, and explicit one-to-many/many-to-one cases. LLM output may rank or
   explain candidates but should not "adjudicate" a conflict. **Reason:** a
   swapped room row can preserve the printed total while assigning the wrong
   material. Fuzzy strings alone do not handle repeated Room 101s. **Cost:**
   moderate harness and normalization work; LLM spend remains small.

9. **Model coverage as two orthogonal axes.** Axis 1 is quantity source:
   geometry, schedule area, printed dimension, estimate, or none. Axis 2 is
   disposition: assigned, excluded-with-reason, pending review, or unresolved.
   The displayed rollup must choose mutually exclusive buckets and show its
   denominator evidence. **Reason:** "measured," "from schedule," "excluded,"
   and "awaiting review" can overlap, so the current proposed buckets cannot
   safely sum to 100%. **Cost:** moderate claim/query design and one mockup
   revision; it avoids much more expensive reconciliation bugs.

10. **Complete the screen map before the image round.** Add exact public route,
    filesystem route, operational actor, entry/exit state, and data/jobs for
    every row. Add the currently missing Pipeline screen, plan-set/revision and
    level confirmation, scale confirmation, material/quantity assumptions, job
    failure/retry, and export blockers. **Reason:** the stated deliverable is
    purpose + route + data dependencies, but the needs-mockup table supplies
    only purpose. **Cost:** low documentation cost plus one to two mockup
    rounds; Material Setup is a small new surface if dollars remain in export.

11. **Run the schedule/join delivery track independently of probe 31.** Pilot
    one area-bearing schedule end to end, implement the join, then broaden its
    format benchmark while boundary research runs. **Reason:** the wedge does
    not depend on a successful boundary experiment, and the roadmap should not
    place the moonshot on the critical path to the near-term demo. **Cost:**
    coordination only; it can reduce elapsed time.

12. **Acquire diversity units, not nominal rows.** Station 1 samples by
    leakage group/firm; Station 3 by design cluster and plan category; Station 4
    by schedule-format family; Station 5 by identity-conflict family. **Reason:**
    probe 30b showed that 79 permits were only 49 clusters and that same-design
    refiles dominated the optimistic score. **Cost:** low metadata/clustering
    work; fewer but more useful labels.

13. **Replace "permanently" for the vision LLM with explicit reconsideration
    triggers.** Keep it as the default now, then reconsider only if measured
    cost per accepted row, latency/SLA, privacy, vendor variance, or correction
    rate crosses a threshold for three consecutive snapshots. **Reason:** no
    current evidence supports training a table model, but permanence is not an
    architectural property. **Cost:** very low; add cost/latency/correction
    telemetry.

14. **Make every gate produce a signed audit artifact.** Record sample seed,
    snapshot, hidden machine output, founder decisions, discrepancies, and the
    exact metrics recomputed after audit. **Reason:** a free-text
    "founder-spot-checked" line is not reproducible and will not reliably shrink
    section 0's debt. **Cost:** low-to-moderate evaluation plumbing; recurring
    founder time is addressed in Answer 6.

## C. STRONG AGREEMENTS

1. **The station architecture and cheapest-adequate-engine rule are right.**
   Rules, rented models, and trained models should compete on measured total
   cost and error, not prestige.

2. **The schedule join is the correct wedge.** It attacks a demonstrated
   manual part of the competitor workflow and fits this project's evidence
   model better than a generic one-click geometry claim.

3. **Do not train a viewport model now.** Heuristics plus Approve/Redraw/Full
   Page are sufficient until measured redraw burden says otherwise.

4. **Do not train a schedule-table model now.** A rented multimodal LLM with
   deterministic extraction, validation, and human confirmation is the
   economically correct first engine.

5. **Pilot before broad build-out, with Nick personally verifying outputs.**
   Founder confusion and correction burden are product findings, not noise.

6. **Probe 31 should compare raster and vector-topology approaches, and the
   cluster-disjoint rebaseline plus label hygiene must happen first.** The
   learning curve by design/firm cluster is more informative than page count.

7. **Coverage, explicit exclusions, evidence cards, and non-uniform trust
   states are the right product center.** The approved screens already provide
   a strong base for this and avoid a confident-green demo.

8. **Versioned components, immutable artifacts, append-only decisions, and
   purpose-specific dataset snapshots are non-negotiable.** These are what make
   later corrections useful rather than destructive.

## D. STRONG DISAGREEMENTS

1. **A finish schedule does not generally yield a full takeoff without
   geometry.** Counter-proposal: call this the **area-schedule path** and gate
   it on an explicit, verified area source. A non-area finish schedule still
   provides high-value material assignment, but SF remains unmeasured. This is
   visible in the project's own special `TRUTH_AREA` tier: if all finish
   schedules carried area, that tier would not be special.

2. **"The architecture must change" is too certain today.** Probe 30b supports
   "the current feature model did not improve as cluster diversity grew," but
   it also found a leaked holdout and serious label contamination. The roadmap's
   build order correctly cleans and rebaselines first; its diagnosis should use
   the same caution. Counter-proposal: architecture change is the leading
   hypothesis, tested only after the clean cluster-disjoint v2 baseline.

3. **A relative Station 3 gate is unsafe.** Beating rules-v4 is necessary for
   model promotion but insufficient for demo or shipment. Counter-proposal:
   require both paired improvement and absolute thresholds for accepted SF,
   silent high-impact errors, abstention quality, coverage, and estimator review
   time on a sealed benchmark. The current model's 26.4% missed-room result is
   not demo-ready merely because rules miss more.

4. **An LLM must not adjudicate join conflicts into truth, and "zero clicks"
   must not mean auto-binding.** Counter-proposal: deterministic constraints
   generate candidates; an LLM may normalize/explain; conflicts and uncertain
   matches remain pending until human confirmation. This follows the V2
   constitution and makes the trust-state pitch real.

5. **The proposed coverage states cannot be one reconciliation equation.**
   Source states and review/disposition states overlap. Counter-proposal: the
   two-axis model in Suggestion 9, with a page-level disjoint calculation and a
   plan-set-aware building rollup.

6. **A building route keyed by permit contradicts the locked identity model.**
   Counter-proposal: canonical `/v2/b/[buildingId]` routes with permit and active
   plan-set context inside; preserve permit URLs only as redirecting aliases.

7. **Polygon perimeter is not automatically wall-base quantity.**
   Counter-proposal: emit `gross_perimeter_lf` from geometry, explicit opening
   lengths, and a separately derived `net_base_lf` with named scope rules and
   evidence.

8. **"Permanently" is the wrong commitment for Station 4.** The correct strong
   commitment is "do not train now; reconsider only from measured economics or
   reliability," not a prediction about all future volume and constraints.

## E. ANSWERS TO SECTION 6

### 1. Screen map completeness

1. The map is close for a demo, but incomplete for a defensible pilot. I would
   lock the following inventory before generating more images:

| Surface | Recommended public route | Purpose / required data |
|---|---|---|
| Work Queue | `/v2/queue` | Approved design; blocking stage, audit due, job and deep-link state |
| Buildings | `/v2` | Building list; never treat permit as building identity |
| Building Summary | `/v2/b/[buildingId]` | Active plan set, levels, source/schedule/geometry coverage, export blockers |
| Source Files & Plan Sets | `/v2/b/[buildingId]/sources` | Uploads, document roles, revisions, supersession, active plan-set assembly |
| Page Review | `/v2/b/[buildingId]/pages` | Stations 1/2, level assignment, viewport and scale proposals |
| Rooms & Finishes | `/v2/b/[buildingId]/rooms` | Schedule extraction, normalized finishes, space-link proposals |
| Geometry Review | `/v2/b/[buildingId]/geometry` | Boundary, type/exclusion, corrections, region/run verdicts |
| Activity | `/v2/b/[buildingId]/activity` | Meaning-changing decisions, supersession, grouped machine events |
| Datasets | `/v2/datasets` | Snapshot to decisions/extractions/clustering trace |
| Models | `/v2/models` | Model to snapshot, sealed eval, audit, and deployment state |
| Pipeline | `/v2/pipeline` | Job health, errors, retry/cancel, engine versions and latency/cost |
| Demo upload/process | `/demo/new` then `/demo/[projectId]/process` | Upload, immutable files, job narration, page filmstrip, failures |
| Customer takeoff review | `/demo/[projectId]/review` | Product-facing evidence, bulk verbs, exclusions, coverage |
| Material/quantity setup | `/demo/[projectId]/materials` or review drawer | Code normalization, waste, carton/roll/base rules, optional rates |
| Export | `/demo/[projectId]/export` | Quantity/bid sheet, assumptions/exclusions, verification split and blockers |

2. The evidence card remains a shared component, not a route. Page-level
   coverage belongs in Page/Geometry Review; the building rollup belongs in
   Summary. Scale confirmation should be a reusable component rather than a
   standalone screen.

3. Revision comparison is valuable but can be post-pilot if Source Files can
   at least assemble and confirm one active plan set. Authentication/team
   administration is also outside a founder-only pilot, but actor identity
   must still be recorded.

### 2. U-Net versus graph-over-vectors

1. **Prior: raster U-Net first for the broad product target; graph model as a
   vector specialist.** A U-Net has the stronger inductive bias for local wall
   appearance plus larger spatial context, and the same input form exists for
   vector, flattened, and raster pages. It also avoids dependence on whether
   fitz exposes the original segment structure.

2. **Graph advantages:** exact geometry, scale-independent connectivity,
   efficient long-range/topological features, and outputs that feed the
   existing polygonizer without raster vectorization. It is likely best on
   clean vector PDFs.

3. **Graph risks:** it is unavailable on true raster pages; extraction exposes
   hidden/clipped/offset vectors; graph construction choices can encode a
   firm's CAD dialect; and a few missed edges can prevent whole rooms from
   closing.

4. **U-Net risks:** CAD-layer weak labels can omit existing walls and include
   junk; scan/render domain shift can be severe; thin walls require careful
   resolution/tiling; and turning a probability mask back into topologically
   correct polygons is not free.

5. Probe 31 should use the same cluster-disjoint split, clean weak labels, and
   fully human-corrected sealed downstream set for both. Compare a cleaned v2
   baseline, U-Net, graph model, and a cheap raster-patch/vector fusion
   baseline. Report per-category learning curves and downstream room actions,
   not only pixel/segment PR-AUC. A later fused router may be correct, but probe
   31 should first reveal which component contributes what.

### 3. Credible-demo data volumes

1. These are **minimum planning priors for a bounded external demo**, not
   promises that sample count creates accuracy. Independent units are plan
   sets/design clusters/format families, never nominal pages or segments. If a
   clean learning curve is still rising at the target, acquire more; if flat,
   change the engine or narrow the claim.

| Component | Proposed development minimum | Sealed evaluation minimum | Credible bounded-demo condition |
|---|---|---|---|
| Station 1 page classifier | 150 leakage-disjoint plan sets, at least 50 firms; at least 200 train positives per critical keep category | 50 cluster-new plan sets and at least 60 positives per critical keep category | Zero misses among each 60-page critical slice gives only about a 95% one-sided lower bound of 95%; also require kept fraction <=15% and report by plan type |
| Station 2 viewport heuristics | 250 confirmed regions from 50 plan sets, including at least 50 multiple/rotated/cropped cases | 100 pages from 20 new plan sets | Zero catastrophic crop misses, at least 95% full-content containment, redraw <=10%; do not train until roughly 500-1,000 real corrections exist |
| Station 2b scale | 200 confirmed scale decisions from 50 plan sets and at least 10 notation/source families | 100 quantity-bearing pages from 20 new plan sets | No guessed scale, all conflicts abstain, and every verified SF/LF has printed-dimension or equivalent cross-check evidence |
| Station 3 boundary | 300 clean regions from at least 150 design clusters, balanced across clean vector, flattened, raster, renovation, open-plan, and irregular layouts | 40-60 fully corrected regions from at least 30 cluster-new buildings, roughly 2,000 rooms | Paired win over rules plus no silent error above the agreed impact threshold, at least 80% of addressable SF accepted without boundary edit, and review time competitive on the bounded categories |
| Station 3b room type/junk, if learned | 2,000 confirmed polygon/space decisions from at least 75 buildings; at least 100 examples per common class and 50 per retained rare class | 500 polygons from at least 20 cluster-new buildings | High precision on auto-applied types/exclusions; rare/ambiguous classes abstain. Rules/LLM may reach this gate without a trained model |
| Station 4 schedule reader | No training minimum while rented LLM is used; build a reference corpus of 50 format-distinct schedule regions from at least 30 buildings and at least 1,000 rows | 20-30 unseen schedules, at least 500 rows, across at least 10 format families | Row recall >=99%, critical finish/base/area field exactness >=98%, no silent dropped rows, and totals/notes conflicts surfaced rather than forced |
| Station 5 join | 1,000 confirmed source links from at least 30 buildings, deliberately including repeated room numbers, levels, aliases, addenda, and one-to-many cases | 300 links from at least 15 unseen buildings | Auto-link precision >=99%, useful auto-link coverage >=80%, no silent conflict on the demo set, and every unresolved link visibly abstains |

2. Current Station 3 data (80 nominal layered permits, 49 clusters) is enough
   to run probe 31, not enough for the broad boundary claim above. Current
   Station 4 evidence (four area-schedule permits) is a useful harness but too
   format-thin for a field-facing claim. Current Station 1's 15-positive finish
   eval is also too small for a full-recall claim.

3. Togal's "millions" story should not be answered with a smaller raw-count
   story. Answer it with a narrower claim, a sealed category-stratified
   benchmark, estimator review time, accepted SF, abstention behavior, and
   evidence completeness. If the intended claim is "any floor plan," none of
   the proposed minima is remotely sufficient.

### 4. Coverage level

1. **Build the page/region calculation first and ship both views from the same
   initial data model.** Page/region is where omissions and overlaps can be
   corrected. Building-level is the demo headline and should be a strict
   aggregation over the active plan set and levels, never an independent
   calculation.

2. If forced to choose one implementation first, choose page/region. Do not
   show a building percentage until duplicate viewports, repeated unit plans,
   missing levels, and schedule-versus-geometry overlap have explicit rollup
   rules.

3. Display both quantity source and disposition. When there is no defensible
   area denominator, show counts and unresolved categories instead of a false
   percentage.

### 5. Where the schedule path breaks first

1. **Missing area is the first scope break.** Many finish schedules identify
   material but not SF, so the no-geometry path cannot produce quantities.

2. **Wrong plan-set/revision/level context is the highest-consequence break.**
   A correct string match against a superseded schedule is still wrong.

3. **Row extraction failures:** merged cells, multi-row headers, continued
   tables, ditto marks, keyed notes, abbreviations, floor/base/wall columns,
   addenda, and schedules embedded in finish plans.

4. **Identity failures:** repeated Room 101 across levels/buildings, unit-type
   rows standing for many rooms, ranges, suffixes, renumbering, and plan labels
   that differ from schedule names.

5. **Semantic failures:** a finish code points through a legend/keynote,
   alternates conflict, base and floor use different scopes, or schedule and
   plan genuinely disagree. An LLM should expose the conflict, not choose a
   truth silently.

6. The first field pilot should therefore include at least one clean area
   schedule, one ordinary no-area finish schedule, one repeated-unit/level
   schedule, one note/legend-indirected schedule, and one revision conflict.

### 6. Cheapest founder-verification protocol

1. **Separate production confirmation from blind audit.** In a blind-audit
   queue, hide machine proposals until Nick commits his answer; then reveal the
   comparison. Ordinary confirm clicks made while viewing a suggestion are not
   blind evidence.

2. **Pilot buildings 1-2: review 100% of consequential outputs.** That means
   active plan set, kept pages/regions, scale, all schedule rows, all join
   links, every exclusion, and every quantity reaching export. Deep-correct
   only selected geometry rooms, but account for every room as accepted,
   pending, excluded, or unmeasured.

3. **After calibration: sustain a 5% stratified blind audit, with floors.** Per
   work session audit at least two page decisions (one predicted keep and one
   drop), one viewport/scale case, five schedule rows, five join links, and
   three geometry spaces including an exclusion or abstention. Sample by risk
   stratum, not plain random. This is roughly a fixed 15-20 minute tax and
   accumulates evidence every session.

4. **Review 100% of triggers regardless of sample rate:** scale conflicts,
   schedule/geometry total mismatch, join conflict, split/merge, wrong
   viewport, exclusion above the agreed SF threshold, large quantity delta,
   model disagreement, and every item contributing dollars to an export.

5. **For every promotion gate:** Nick blindly rechecks a seeded, stored slice
   from the sealed eval plus all machine-identified high-impact failures. The
   gate artifact records what he checked and recomputes metrics from those
   decisions. Start with at least 20 independent units per relevant stage;
   increase the sealed set to the volumes in Answer 3 before market claims.

6. **Taper only from evidence.** After at least 100 audited units in a stage
   with no critical silent error, keep the 5% floor but reduce low-risk
   oversampling. Any critical silent error resets that stage to 100% review
   until its named failure cause is fixed and re-audited.

## F. ANYTHING ELSE WORTH DISCUSSING

1. **Define model contracts in the roadmap.** Each station card should add
   input schema/version, output claim names, abstention/error states,
   idempotency key, latency/cost budget, and the exact decision that makes its
   output eligible downstream. Inputs/outputs alone are not enough for an async
   production assembly line.

2. **Reserve constitutional words.** Use "candidate ranking" for LLM join
   assistance; reserve "adjudication" for the append-only human decision graph.
   Use "proposal complete" rather than "takeoff complete" until verification
   and coverage gates clear.

3. **Add an explicit risk register to the locked roadmap.** The top risks are
   currently: schedule-without-area scope, plan-set/revision mismatch, scale,
   weak-label domain shift, geometry truth scarcity, repeated-space identity,
   and founder audit capacity. Give each an owner, observable metric, and stop
   condition.

4. **Recommended R1 disposition:** retain the five-station product framing but
   add Station 0 and scale, split Station 3's objectives, narrow the
   schedule-only claim, make production execution job-based, and replace every
   relative-only or machine-only truth gate before lock.
