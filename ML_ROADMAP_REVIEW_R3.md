# ML Roadmap Review - Round 3

*2026-07-11. Review of `ML_ROADMAP.md` v1.2 after Fable's Round-2 verdicts
and founder process decisions. Verdict: **NOT READY TO LOCK YET.** The
direction is strong, but a file named `ML_ROADMAP_LOCKED_V1.md` cannot contain
`PENDING-FOUNDER` sections without weakening the project's lock semantics.*

## 1. LOCK ASSESSMENT

1. **REJECT THE R3 FILE-NAMING INSTRUCTION, NOT THE PLAN.** Continue with this
   review round. Produce `ML_ROADMAP_LOCKED_V1.md` only when the founder
   decisions and process contradictions below reach zero. If a folded draft is
   useful earlier, name it `ML_ROADMAP_LOCK_CANDIDATE_V1.md`.

2. **REASON:** `spec-driven-dev` defines a locked document as an implementation
   authority. A document that is simultaneously LOCKED and PENDING invites
   builders to choose defaults silently, exactly what the drift guard prevents.

3. **CURRENT STATUS:** v1.2 is a good lock candidate. Its zero-trust reset,
   lean bootstrap, station architecture, gate ladder, and product boundaries
   survive. The blockers are now precise implementation/governance issues, not
   a need to redesign the roadmap again.

## 2. CONFIRMED FROM FABLE'S R2 VERDICT

1. **CONFIRM:** trusted semantic-label count is zero until fresh binding human
   decisions exist. Legacy labels, answer keys, clusters, models, and probe
   metrics remain preserved but diagnostic-only by default.

2. **CONFIRM:** `verified_bootstrap_v1` precedes probe 31, architecture
   selection, new learning curves, promotion, and automation claims.

3. **CONFIRM:** the restart stays lean: short versioned label books, blind mode
   as a state on existing screens, and smallest viable provenance artifacts.

4. **CONFIRM:** audit the four candidate area keys early. Their printed-total
   agreement makes them high-value audit candidates, not truth. Nick must still
   verify every source row/field used by the bootstrap metric.

5. **CONFIRM:** independent second-human review is an upgrade, not a current
   dependency. Delayed blind self-relabel is the minimum consistency check.

6. **CONFIRM:** cross-vendor Sonnet + Codex labeling is useful for measuring
   agreement and prioritizing review. Agreement remains machine
   cross-verification, never human truth.

7. **CONFIRM:** text may be a Model-1 feature, but every agent labeler must view
   the rendered page image. Any text-only labeling run is automatically
   ineligible and quarantined.

8. **CONFIRM:** R1's adopted product/architecture decisions remain intact:
   Stations 0 and 2b, Station 3a/3b/3c, area-schedule scope, constrained
   human-confirmed joins, two-axis coverage, buildingId routes, explicit gross
   perimeter/net base, jobs/contracts, risk register, and full screen inventory.

## 3. LOCK BLOCKERS

1. **SEALED-EVAL ORDER IS UNDER-SPECIFIED.** The bootstrap says Nick labels
   complete units blind, while the cross-vendor rule says model agreements are
   bulk-accept eligible. Those can coexist only with an explicit sequence:

   1. Nick sees raw source and commits the sealed human decision with all model
      output hidden.
   2. Sonnet and Codex independently label the same source under the same frozen
      rubric, without seeing Nick or each other.
   3. The system reveals and compares all three only after every answer is
      committed.
   4. No bulk accept is available on calibration, frozen-test, or canary items.

   **Required correction:** put this sequence in the lock and skills. Otherwise
   cross-vendor agreement can leak into the supposedly human-blind test.

2. **BULK ACCEPT NEEDS A PURPOSE BOUNDARY.** A human clicking "accept 500
   agreements" has authorized a batch, but has not visually verified 500
   labels. Record `blind=false`, the batch action, source run IDs, audit rate,
   and sampled errors. Such decisions may become training-eligible after the
   source qualifies; they are never gold calibration/eval truth.

3. **QUARANTINE HAS NO LOCKED APPEND-ONLY MECHANISM.** v1.2 says to mark old
   `machine_observation` rows defective, but that table has no status column.
   It also says old decisions become "superseded-non-binding," but `binding` is
   immutable and a supersession relation does not rewrite it.

   **Required correction:** choose and constitutionally document one mechanism:
   a versioned quarantine registry keyed by source/run/observation, or an
   append-only eligibility-denial decision/policy that every resolver and
   snapshot builder enforces. First produce a read-only
   `pilot_quarantine_manifest_v1`; do not mutate rows while discovering scope.

4. **ACTIVE SKILLS STILL IMPLEMENT THE OLD TRUTH PATH.** Before the restart:

   1. `label-pages` must stop inserting legacy `page_label` truth and stop
      `UPDATE page SET status='labeled'`; it must emit V2
      `machine_observation` rows with source/run/rubric/taxonomy provenance and
      the canonical flags.
   2. `review-labels` must become vendor-neutral, accept explicit first/second
      run IDs, and preserve a truly blind first pass. It currently hard-codes
      `source='claude-code'`.
   3. `triage-permits` must stop calling agent-confirmed tiers/area rows truth;
      they are candidate observations until a human decision grants
      purpose-specific eligibility.
   4. `diagnose-model` and improvement-loop sections 2-4 must require human
      ground truth before naming a binding constraint. They currently instruct
      drivers to treat legacy `truth_area` keys and probe metrics as truth.

   **Required correction:** rewrite these process locks before any pilot agent
   is launched. A roadmap lock that points to contradictory skills is unsafe.

5. **SPLIT RULES STILL CONFLICT.** `CLAUDE.md` says eval splits by document;
   V2 requires conservative leakage groups, plan sets, refiles, and firm-aware
   evaluation. The lock must say: split by leakage group/plan set, never page or
   loose document; exact/perceptual duplicates share a split; firm holdout is a
   separate reported dimension.

6. **THE 2/4/4 SET IS A BOOTSTRAP, NOT AN ARCHITECTURE GATE.** Four sealed
   buildings can reveal plumbing errors, label ambiguity, and catastrophic
   failures. They cannot establish data sufficiency, stable category metrics,
   or a U-Net-versus-graph winner. Name its output
   `verified_bootstrap_v1`, not `frozen_test_v1`; expand cluster-new sealed
   truth before P3 promotion or market claims.

7. **RUBRIC VERSIONING NEEDS A BURN RULE.** Buildings 1-2 may change the label
   book. Freeze the rubric before buildings 3-10. If a later change alters the
   meaning of an existing claim, sealed decisions under the old rubric are
   mapped only when semantics are identical; otherwise they are relabeled or
   burned to development.

8. **DUAL-WORKER INDEPENDENCE NEEDS A MANIFEST.** Each assignment must pin
   page/source hash, render extraction ID, rubric/taxonomy version, worker
   vendor/model/version, prompt hash, blind status, and run ID. Workers may
   share the rubric and source image, but never outputs, scratch files, or
   conversation context before commit.

9. **THE GEOMETRY COMMITMENT NEEDS A RELEVANCE CLAUSE.** "One region per pilot
   building" is wrong when a building has no filed floor plan or no
   quantity-bearing geometry. Use one fully traced representative region per
   geometry-capable pilot building, with a minimum bootstrap count of 8-10
   diverse regions. Record no-plan/no-geometry buildings as real coverage
   failures rather than fabricating an annotation target.

10. **TRUST INVENTORY MUST PRECEDE THE ZERO COUNT BECOMING A DATABASE CLAIM.**
    Nick's declaration correctly sets policy to zero. The first artifact should
    still enumerate existing V2 decisions by actor, binding, blind, source,
    claim, and run so the quarantine is exact and no legitimate fresh human
    decision is accidentally hidden.

## 4. REQUIRED TRUST SEMANTICS

| Event | Stored trust state | Training use | Calibration/eval use |
|---|---|---|---|
| One agent label | Machine observation | Diagnostic weak only until source audit | Never |
| Sonnet and Codex agree blindly | Machine cross-verified | Weak/train candidate after audit | Never by itself |
| Nick bulk-accepts an agreement batch | Binding human batch decision, non-blind, batch provenance | Train eligible under named policy | Never |
| Nick inspects and confirms one shown proposal | Binding human decision, non-blind | Train eligible | Never sealed truth |
| Nick labels raw source before reveal | Binding blind human decision | Gold development/train if assigned | Calibration/bootstrap eval if leakage-safe |
| Blind decision passes delayed/independent recheck | Rechecked blind human truth | Gold | Highest current sealed tier |

1. **LOCK THIS TABLE OR AN EQUIVALENT.** The UI color law alone does not encode
   purpose eligibility. The same visual "confirmed" state can contain a blind
   authored label, an inspected proposal, or an uninspected batch acceptance;
   datasets must distinguish them.

## 5. FOUNDER DECISION RECOMMENDATIONS

1. **2/4/4 pilot split:** APPROVE as bootstrap calibration/development/sealed
   smoke evaluation. Do not call the four-building slice sufficient for P3.

2. **Second review:** APPROVE delayed blind self-relabel as the current floor;
   add an independent estimator/architect review to at least 10% of geometry
   sealed truth when a qualified person becomes available.

3. **Legacy salvage:** APPROVE audit-for-salvage after human truth. Use a legacy
   source only in a named `weak_train` snapshot when measured noise, coverage,
   and bias make it cheaper than relabeling.

4. **Geometry commitment:** MODIFY to the relevance rule in Blocker 9: one
   fully traced region per geometry-capable pilot building, minimum 8-10 total,
   then measure time before committing to 15-20.

5. **First external claim:** APPROVE the area-schedule workflow with all output
   human-confirmed. Phrase it as a verified workflow demonstration, not an
   automation-accuracy claim.

6. **Routes and audit budget:** APPROVE canonical buildingId migration. Do not
   lock 15-20 minutes/session as a fact before buildings 1-2 measure the work;
   lock a sustainable 5% post-qualification floor plus all risk triggers, then
   publish the measured time budget.

## 6. PRE-LOCK ARTIFACTS

1. `truth_inventory_v1`: read-only counts and IDs by claim/source/actor/blind/
   binding/run, including all prior pilot work.

2. `pilot_quarantine_manifest_v1`: exact observation/decision/extraction/run
   scope, reason, proposed append-only quarantine action, and rollback-free
   verification query.

3. `label_policy_v1`: trust table from section 4, source qualification,
   dataset-purpose eligibility, burn/replacement rules, and batch-accept rules.

4. Updated `label-pages`, `review-labels`, `triage-permits`, `diagnose-model`,
   improvement-loop, and `CLAUDE.md` so every active process agrees with V2.

5. `pilot_assignment_v1`: 2/4/4 building IDs, leakage groups, plan sets,
   category rationale, geometry-capable marker, source hashes, and frozen
   rubric version.

6. Blind-mode acceptance criteria for Page Review, Rooms & Finishes, and
   Geometry Review: no pre-submit model value in UI/API response, explicit
   blind decision flag, reveal-after-commit comparison, and audit logging.

## 7. NEXT ROUND

1. Fable should adopt/reject/modify the ten blockers and the trust table.

2. Nick should answer the six founder decisions using section 5's recommended
   wording or provide deltas.

3. After those answers, fold the roadmap into one clean successor document.
   Do not carry v1.0 claims plus three layers of appended amendments into the
   lock.

4. Only when `STILL OPEN` is empty should the file be named
   `ML_ROADMAP_LOCKED_V1.md` and become an implementation spec.

## LOCKED

1. Zero-trust semantic baseline and non-destructive legacy quarantine.

2. Human-authored blind truth before rebaseline, architecture, promotion, or
   automation claims.

3. Legacy metrics/models are diagnostic only until regraded on human truth.

4. Cross-vendor agreement is machine cross-verification, never human truth.

5. Area-schedule is the first bounded workflow path; geometry remains research
   until human-truth gates clear.

6. R1/R2 station architecture, product boundaries, gate ladder, screen
   inventory, and lean-restart direction remain accepted.

## STILL OPEN

1. Founder ratification of the six decisions in section 5.

2. Append-only quarantine mechanism for machine observations and prior
   decisions.

3. Sealed-eval ordering and bulk-accept eligibility language.

4. V2 rewrites of the six contradictory standing skills/rules.

5. Pilot assignment, frozen rubric, trust inventory, and quarantine manifest.

6. Blind-mode implementation acceptance criteria and verification.

7. Size and composition of the post-bootstrap sealed set required for P3.
