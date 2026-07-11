# ML Roadmap Review - Round 2

*2026-07-11. Terse delta round against `ML_ROADMAP.md` v1.1 and
`ML_ROADMAP_REVIEW_R1.md`. Governing founder correction for this round:
Nick does not trust any semantic label, answer key, training input, or review
judgment from the first ML process because none received human review. This is
stronger than the roadmap's existing metric-verification debt.*

## 1. FOUNDATIONAL CORRECTION

1. **ADOPT AS LOAD-BEARING:** the current problem is not merely that Nick did
   not spot-check reported metrics. The labels used to train and grade the
   models are themselves untrusted. A machine-graded metric against a
   machine-produced answer key measures internal agreement, not product
   accuracy.

2. **CURRENT HONEST COUNT:** treat every station as having **zero trusted
   semantic labels for promotion/evaluation** until an inventory finds fresh
   binding human decisions made after V2. Raw PDFs still exist; reproducible
   extraction still exists; semantic truth does not yet exist.

3. **PRESERVE, DO NOT DELETE:** all legacy labels, models, probes, overlays,
   clusters, and answer keys remain immutable historical artifacts. Mark them
   `legacy_unverified` / `diagnostic_only`; exclude them by default from every
   training, calibration, frozen-test, demo, and bid-eligibility policy.

4. **TRUST LEDGER FOR THE LOCK VERSION:**

| Existing asset | R2 status | Allowed use before human audit |
|---|---|---|
| Source PDFs, hashes, page identity | Immutable source, not semantic truth | Replay and visual human labeling |
| Extracted text, vectors, layers, renders | Versioned machine extraction | Candidate evidence; never label truth by itself |
| Agent/Claude page labels and triage verdicts | Machine observations | Suggestions, diagnostics, source-quality audit |
| CAD wall-layer labels | Unqualified weak supervision | Exploratory training only; never eval truth |
| `TRUTH_AREA` JSON and printed-total agreements | Candidate answer keys | Audit queue; no metric gate |
| Firm/design clusters | Machine-proposed groupings | Conservative leakage blocking; not a verified diversity count |
| `split_v1`, canaries, probe 25-30 metrics | Legacy diagnostic record | Code regression and hypothesis generation only |
| `wall_model_v2`, rules-v4 | Legacy candidate engines | Shadow replay after human truth exists; no promotion status |
| Fresh binding, non-blind human decision | Human-reviewed truth | Training eligibility only, subject to policy |
| Fresh binding, blind human decision | Gold truth | Calibration/eval eligibility when leakage-safe |
| Blind decision independently rechecked | Highest current tier | Sealed claim/gate evidence |

5. **TERMINOLOGY CORRECTIONS:** replace "80 verified layered permits" with
   "80 machine-screened weak-label candidates"; replace "4 TRUTH_AREA answer
   keys" with "4 machine-produced candidate area keys"; replace "first
   trustworthy leaderboard" with "first reproducible legacy leaderboard."

## 2. R1 VERDICTS RE-EVALUATED

1. **CONFIRMED:** R1 D1 and D4-D8 remain correct: area-schedule scope,
   human-confirmed joins, two-axis coverage, building identity routes, gross
   perimeter versus net base, and measured reconsideration triggers for the
   rented schedule LLM do not depend on old labels.

2. **CONFIRMED:** Stations 0 and 2b, the split of Station 3, job contracts,
   plan-set gating, scale abstention, field-level schedule metrics, constrained
   joins, the screen inventory, and the risk register all remain required.

3. **REOPENED:** R1 D2 was still too generous. "Architecture change is the
   leading hypothesis" is not an evidence-backed conclusion when both the
   training targets and evaluation labels are untrusted. U-Net and graph
   remain plausible candidates, but architecture selection returns to OPEN.

4. **WITHDRAWN FROM DECISION USE:** 0.267 recall, 0.214/0.340 PR-AUC, the flat
   learning curve, 2.6% downstream match, 26.4% versus 33.5% missed rooms, the
   canary results, and +/-0.02% answer-key agreement may be reproduced and
   discussed as legacy diagnostics. None may justify train/get-more-data,
   engineer/change-architecture, promote, demo, or ship.

5. **MODIFIED:** R1 B6's sealed truth set is no longer a later bounded-demo
   requirement. A small human-authored truth seed is the prerequisite for any
   meaningful rebaseline or probe 31 architecture spend.

6. **MODIFIED:** R1 E6's 5% audit applies only after a label source and workflow
   have qualified. The restart begins with 100% blind human labeling of the
   bootstrap set. A spot-check cannot rehabilitate an untrusted eval set.

7. **MODIFIED:** R1 E3's volume table remains a long-range acquisition-budget
   prior, not part of the immediate lock. The next numbers that matter are
   human labeling time, disagreement rate, source-specific label error, and
   learning curves graded only against human truth.

8. **CONTESTED:** v1.1 build-order steps 2-3 must not rebaseline
   `wall_model_v2` on cleaned legacy targets and then run probe 31 as if the
   result answered sufficiency. The new order is human truth first, legacy
   rebaseline second, architecture decision third.

## 3. RESTART PROTOCOL

1. **Freeze eligibility, not files.** Add an explicit policy guard: a dataset
   item lacking a fresh eligible human decision cannot enter hard-label train,
   val, calibration, frozen test, canary, demo truth, or bid truth.
   Unqualified weak-label experiments get `diagnostic_weak`; a source that
   later passes human audit may enter a separate `weak_train` snapshot with its
   measured noise recorded, but never an evaluation snapshot.

2. **Write the label book before labeling.** For each claim define the visual
   question, allowed values, positive/negative examples, abstain/uncertain
   behavior, multi-viewport and hybrid rules, boundary inclusion rules,
   schedule ditto/note handling, scale evidence, and link cardinality. Version
   the book with the taxonomy.

3. **Add true blind mode to the existing review screens.** Hide category
   suggestions, proposed viewports, extracted row values, model polygons,
   confidence/recommendation text, and bulk-accept actions until the human
   decision is submitted. Reveal the comparison afterward. The approved
   normal review layouts remain unchanged outside this state.

4. **Use the 10-building pilot as the bootstrap, with a fixed split before any
   labels are seen:** buildings 1-2 are rubric calibration, 3-6 are development,
   and 7-10 are sealed bootstrap evaluation. Group known duplicates/refiles
   conservatively before assignment. Calibration data may teach the rubric;
   sealed data may not teach a fix.

5. **Label complete units, not convenient positives.** Nick labels every page
   in each pilot plan set from the raw render, every relevant viewport, every
   quantity-bearing scale, every cell/row in selected schedules, and every
   applicable schedule-to-space link. Complete plan sets are required to
   measure false negatives.

6. **Geometry bootstrap:** fully trace at least one representative plan region
   per pilot building, including missed/fake/open/excluded spaces and explicit
   scale evidence. Ten regions are enough to expose whether the old engines and
   weak labels are directionally useful; they are not enough for a demo claim.
   Expand to the R1 15-20 narrow-demo set only after annotation time is known.

7. **Compare only after the human commits.** Run every legacy label source and
   engine against the new decisions, report errors by source and plan type,
   and decide separately whether each source is salvageable, usable only as
   noisy weak supervision, or rejected.

8. **Do not mass-convert old labels into human truth.** A good audit of one
   source permits that source to generate weak or review-prioritized examples;
   it does not make unreviewed historical rows binding decisions.

9. **Measure the human too.** Re-present a hidden 10% sample after a delay to
   estimate Nick's intra-rater consistency. For boundary truth and ambiguous
   schedule/plan conflicts, obtain a second estimator/architect review on at
   least 10% of the sealed set if possible. One human is necessary provenance,
   not automatic infallibility.

10. **Burned-test rule:** once a sealed example's error is inspected to design
    a fix, move it into development and replace it with a new cluster-disjoint
    sealed example. Never repeatedly tune against the same four permits and
    continue calling them test.

11. **Bootstrap completion criterion:** the first restart phase is complete
    only when all 10 buildings have provenance-complete decisions, annotation
    time is measured, disagreement/uncertainty is recorded, and a frozen
    `verified_bootstrap_v1` snapshot can be rebuilt from manifests.

## 4. DRAFT LOCKED STATION CARDS

1. **Station 0 - Intake and plan-set assembly.** Job: establish building,
   permit, level, document role, revision, and active plan set. Engine: rules
   plus human confirmation. Truth now: zero confirmed pilot plan sets. First
   gate: all 10 pilot plan sets and levels confirmed before downstream joins.

2. **Station 1 - Page classification.** Job: one primary category plus all
   independent flags. Engine now: legacy TF-IDF/image model as hidden shadow;
   rules may prioritize work but cannot skip blind audit pages. Truth source:
   complete human page decisions. First gate: regrade the untouched legacy
   model on buildings 7-10; only then decide whether to retrain, replace, or
   retain rules. `split_v1` is code regression only.

3. **Station 2 - Region/viewport.** Job: propose all drawing/table regions and
   transforms. Engine now: heuristics plus Approve/Redraw/Full Page. Truth
   source: blind accepted/redrawn region geometry. First gate: measure full-
   content containment and redraw rate on all pilot relevant pages; no ML until
   correction volume and burden justify it.

4. **Station 2b - Scale.** Job: resolve scale from printed source and verify it
   against dimensions/transforms. Engine now: deterministic extraction/OCR
   plus cross-checks; abstain on conflict. Truth source: human-confirmed scale
   evidence. First gate: no SF/LF marked verified without a binding scale
   decision or an explicit schedule-area source.

5. **Station 3a - Boundary/closure.** Job: room/open-zone polygons and explicit
   openings. Engines now: rules-v4 and `wall_model_v2`, both demoted to legacy
   diagnostic shadow. Truth source: fully human-traced polygons, not CAD
   layers. First gate: evaluate both old engines and the CAD-layer weak labels
   on the 10-region bootstrap; only then decide whether probe 31 should test
   U-Net, graph, fusion, better rules, or more truth acquisition.

6. **Station 3b - Space semantics/exclusions.** Job: room label/type plus
   exclusion proposal and reason. Engine now: text normalization, rules, and
   rented LLM proposal; no trained type model. Truth source: human decisions
   linked to canonical spaces. First gate: error taxonomy and class counts from
   the pilot determine whether a learned model is warranted.

7. **Station 3c - Derived quantities.** Job: area, gross perimeter, openings,
   and policy-derived net base. Engine: deterministic geometry and named scope
   rules. Truth source: verified scale, corrected polygon, printed dimensions,
   and explicit deductions. First gate: every quantity carries source and
   disposition; no machine-only quantity reaches verified export.

8. **Station 4 - Schedule reader.** Job: immutable raw cells plus structured
   room/name/floor/base/area/notes fields. Engine now: rented vision LLM as a
   candidate extractor. Truth source: field-by-field human decisions from the
   source table. First gate: transcribe and audit every schedule row in the
   pilot; only then claim that the reader "works" or set field thresholds.

9. **Station 5 - Constrained join.** Job: propose level-aware, cardinality-safe
   schedule/label/polygon links. Engine: deterministic normalization and
   bipartite constraints; LLM may rank/explain only. Truth source: binding human
   `space_source_link` decisions. First gate: every pilot link confirmed and
   every ambiguity abstained; zero clicks means proposal completeness only.

## 5. GATE LADDER

1. **Gate P0 - Provenance:** label definition versioned; source visible;
   decision actor/blindness recorded; purpose eligibility explicit. Failure at
   P0 blocks every metric regardless of model quality.

2. **Gate P1 - Diagnostic research:** weak machine labels are allowed only in
   a named diagnostic snapshot. Outputs may generate hypotheses; they cannot
   change a production default or support a market claim.

3. **Gate P2 - Human-truth baseline:** the current engine is evaluated without
   tuning on a fully human-labeled, leakage-safe snapshot. All old promotion
   states reset here. This gate chooses the real baseline.

4. **Gate P3 - Shadow candidate:** a new engine beats the human-truth baseline
   on paired absolute metrics and canaries, with correct abstention and no
   critical silent error. It remains non-binding in the product.

5. **Gate P4 - Bounded demo:** the claim names supported plan categories; all
   demo outputs are human-confirmed; coverage/review burden clears the locked
   thresholds on a sealed set. A polished selected example alone does not pass.

6. **Gate P5 - Bid/export:** every quantity and dollar inherits a binding
   human decision, scale/area source, assumptions, exclusions, and unresolved
   blocker check. Machine confidence never substitutes for confirmation.

7. **Audit rule:** frozen-test metrics are computed entirely against human
   truth, not founder-spot-checked machine truth. The later 5% stratified audit
   monitors new production/training decisions; it never means 95% of eval
   labels may remain machine-only.

## 6. REVISED BUILD ORDER

1. Mark all legacy semantic datasets/models/evaluations `diagnostic_only` and
   enforce purpose eligibility in snapshot creation and model views.

2. Write the versioned label book and add blind mode/audit state to Page
   Review, Rooms & Finishes, and Geometry Review.

3. Process pilot buildings 1-2 completely from raw source to calibrate the
   rubric; revise the rubric by explicit version/superseding decisions.

4. Freeze the remaining pilot assignment; label buildings 3-6 for development
   and 7-10 for sealed bootstrap evaluation.

5. Build `verified_bootstrap_v1`; report human time, uncertainty,
   intra-rater/second-review agreement, and source-specific legacy error.

6. Re-run Model 1, viewport/scale rules, rules-v4, `wall_model_v2`, schedule
   reader, and join proposals unchanged against the bootstrap. This is the
   first honest baseline, not probe 31.

7. Qualify or reject each legacy/weak label source. Salvage only through a
   named weak-supervision policy; never by relabeling provenance in bulk.

8. Continue the area-schedule product path with every output human-confirmed.
   It may become a workflow demo before it becomes an automation claim.

9. Choose probe 31 architecture and acquisition volume from the human-truth
   failure taxonomy and learning signal. Do not promise both U-Net and graph
   "regardless" if the verified evidence points to a cheaper adequate engine.

10. Expand toward R1's long-range volume priors only after real annotation
    throughput and per-source label quality are known.

## 7. SCREEN INVENTORY DELTAS

1. **CONFIRM R1 E1 route inventory in full.** No additional top-level screen is
   required for the restart.

2. **ADD a blind/audit state to three approved review surfaces.** In that
   state suggestions and AI recommendations are hidden, comparison appears
   only after submit, bulk accept is disabled, and the header names the rubric
   version and blind status.

3. **ADD a Work Queue lane/filter:** `Build verified baseline`, with exact
   deep links and completeness counters by station, not model confidence.

4. **ADD dataset/model trust states:** `legacy unverified`, `diagnostic weak`,
   `human-confirmed train`, `blind calibration`, `sealed test`, and `burned to
   development`, each with an ineligibility reason and source-decision links.

5. **KEEP normal trust-state visuals.** Dashed machine proposals remain useful
   in production review; they are hidden only during blind labeling/audit.

## 8. RISK REGISTER DELTAS

| Risk | Owner | Guard | Stop condition |
|---|---|---|---|
| Founder labeling becomes the bottleneck | Founder + driver | Measure minutes/unit on buildings 1-2; prioritize complete high-value units | Pause model work if truth acquisition cannot sustain the next snapshot |
| One human is inconsistent or mistaken | Founder + domain reviewer | Delayed 10% relabel plus independent 10% sealed review | Do not lock taxonomy/gates while material disagreement is unresolved |
| Suggestions bias the human | UI/driver | True blind mode; reveal only after commit | Any pre-submit leakage invalidates that decision for blind eval |
| Legacy labels silently re-enter datasets | Data pipeline owner | Purpose eligibility deny-by-default; manifest audit | Snapshot build fails on any unqualified item |
| Weak CAD labels encode missing/junk walls | Station 3 owner | Compare against traced human polygons by stratum | Reject the source/stratum if errors are systematic or unbounded |
| Sealed test becomes development data | Evaluation owner | Burn-and-replace rule; access/event log | Remove inspected examples from frozen test before next gate |
| Ten pilot buildings are unrepresentative | Founder + data owner | Select diverse plan/schedule categories before labels | No broad claim; expand by missing category/cluster |
| Raw extraction is mistaken for truth | Station owner | Always retain source crop/page beside extraction | Abstain or require human correction on source disagreement |

## 9. DRAFT LOCK DOCUMENT STRUCTURE

1. `0. Status of truth` - founder correction, zero-trusted baseline, trust
   ledger, legacy quarantine, allowed claims.

2. `1. System architecture` - Station 0 through 5 contracts, job/DAG facade,
   immutable inputs, abstention, and eligibility.

3. `2. Station cards` - the nine cards in section 4, each with job, engine,
   output claims, truth source, current honest state, cost, and gate.

4. `3. Data restart` - label book, blind mode, 10-building bootstrap split,
   source qualification, weak-supervision policy, burn-and-replace rule.

5. `4. Gate ladder` - P0 provenance through P5 bid/export, absolute metrics,
   founder/domain review, signed audit artifacts.

6. `5. Demo paths` - area-schedule workflow versus geometry research, bounded
   claims, coverage source/disposition axes.

7. `6. Build order` - section 6 of this review, with owners and exit artifacts.

8. `7. Screen inventory` - R1 E1 routes plus the blind/audit and trust states
   in section 7 of this review.

9. `8. Verification protocol` - complete bootstrap truth, later 5% monitoring,
   100% triggers, second-review/intra-rater policy.

10. `9. Risk register` - section 8 plus cost/latency/privacy risks once measured.

11. `10. Planning volumes` - R1 E3 retained explicitly as post-bootstrap priors,
    replaced by measured curves and annotation throughput at each checkpoint.

## LOCKED

1. R1's adopted architecture/product corrections remain locked except where
   explicitly modified above.

2. All pre-restart semantic labels, answer keys, human-like agent verdicts,
   models, and probe metrics are legacy-unverified and ineligible for decision
   gates by default.

3. Existing artifacts are preserved; the restart changes eligibility and
   truth provenance, not history.

4. Current trusted semantic-label count is treated as zero until fresh V2
   human decisions are inventoried.

5. Human-authored blind truth precedes rebaseline, learning curves, data-
   sufficiency conclusions, architecture selection, promotion, and claims.

6. Eval truth is 100% human-verified; the 5% audit rate is later monitoring,
   not permission to leave eval labels unverified.

7. Legacy models return to diagnostic shadow status. Probe 31 is not the next
   decision gate until `verified_bootstrap_v1` exists.

8. The existing approved screens need a blind/audit state, not replacement
   layouts.

## STILL OPEN

1. Founder ratification of the proposed 10-building bootstrap split: 2 rubric
   calibration, 4 development, 4 sealed bootstrap evaluation.

2. Whether the sealed set receives an independent estimator/architect review
   or only Nick's delayed blind relabel. Recommendation: independent review for
   at least 10%, especially geometry.

3. Whether to audit each legacy label source for salvage after the bootstrap
   or start all training labels fresh. Recommendation: audit first; salvage
   only sources whose measured noise and bias make them cheaper than relabeling.

4. Founder commitment to one fully traced geometry region per pilot building;
   annotation timing from buildings 1-2 decides whether 15-20 narrow-demo
   regions is sustainable.

5. The first bounded external claim after the restart. Recommendation:
   area-schedule workflow with all outputs human-confirmed; no geometry
   automation claim until P3/P4 evidence exists.

6. Route migration to `/v2/b/[buildingId]` and the recurring post-bootstrap
   blind-audit time remain founder resource decisions from R1.
