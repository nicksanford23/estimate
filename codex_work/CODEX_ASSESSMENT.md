# Codex Assessment For Claude

Written from a repo read-through on 2026-07-04. This is a candid assessment of
where the estimating project looks strong, where the claims are ahead of the
evidence, and what I would do next.

## Short Version

The direction is good. The team is doing the hardest part correctly: defining
the business decision, naming the error costs, testing on held-out permits, and
discarding flattering numbers when the split artifact was found.

The main problem is evidence discipline. The project now has a conservative
demo path, but some docs say or imply "shipping" before the eval is strong
enough. The honest frozen-split result says the page classifier is promising,
not proven.

## What Looks Good

1. Decision-first framing is strong.

   The roadmap is organized around decisions, done numbers, and cheapest
   credible approaches instead of starting with a model. This is the right
   shape for an estimating product, where silent misses are much worse than
   extra review.

2. Error-cost asymmetry is correctly encoded.

   The docs consistently treat missed finish pages as the dangerous failure
   and false positives as tolerable. The serving code follows this by
   force-keeping no-text pages instead of trusting the text model.

3. The split-artifact correction is a very good sign.

   The old `finish_recall@0.5 = 0.974` number was not defended. It was
   downgraded after the unstable permit split and whale-permit effect were
   found. That is exactly the kind of correction that keeps an ML project from
   lying to itself.

4. Frozen permit-level eval is a real improvement.

   `scripts/make_split.py` creates a stable eval permit list, forces huge
   permits into train, and prevents new labels from silently changing existing
   train/eval membership. This is much better than reshuffling the current
   permit list every run.

5. The model ladder is pragmatic.

   Embeddings first, text features next, router after that, higher-res/fine
   tuning only if needed. That order is sensible and cheap.

6. The long-term chain is mostly sequenced correctly.

   Page finding -> grouping -> scale -> room boundaries -> finishes ->
   quantities -> review UI is the right dependency order. Room boundaries are
   correctly treated as a hard later bet, with a cheap vector-geometry probe
   before building.

## What Looks Weak Or Risky

1. "v1 shipping now" is too strong.

   The honest frozen-split headline is weak at the default threshold:
   `text_only finish_recall@0.5 = 0.267`. Full finish recall is achieved by
   lowering the threshold, which keeps roughly 24% of pages. That may be useful
   for a demo or assisted triage, but it is not enough evidence for a confident
   production claim.

2. The eval set is thin.

   The frozen split has only 15 finish pages in eval. That is too few for a
   high-confidence "zero missed finish pages" claim. One mislabeled page or one
   weird permit can swing the conclusion materially.

3. Threshold selection uses eval.

   `scripts/train_v1.py` chooses `thr_star` from eval finish pages, then reports
   eval metrics at `thr_v1 = thr_star / 2`. This is acceptable for a demo
   artifact, but not for a final claim. The next version needs:

   - train set for fitting
   - validation set for threshold selection
   - untouched test set for final reporting

4. Cross-permit generalization is still the binding constraint.

   The project correctly identifies that the signal transfers weakly across
   permits. More thresholding, routing, or pages from the same permits is
   unlikely to fix this. The highest-conviction lever is more diverse permits.

5. Documentation has drift.

   `STATE.md` says Neon is source of truth. `CLAUDE.md`, `schema.sql`, and
   `AGENT_PIPELINE.md` still describe SQLite/v0 paths. This creates risk for
   future agents following stale instructions.

6. README is not useful yet.

   `README.md` is effectively empty. A new worker cannot tell the current
   source of truth, current commands, or current status without reading many
   docs.

7. No tests exist.

   I ran a syntax-only parse over 22 Python files and they parse, but there are
   no executable checks for the things that matter:

   - frozen split membership stability
   - no eval leakage in vectorizer/model fitting
   - threshold-selection behavior
   - keep-category derivation
   - no-text conservative fallback
   - CSV/Neon experiment loader idempotency

8. Dates look confusing.

   Several docs are dated 2026-07-05 while this session date is 2026-07-04 UTC.
   Maybe that is from another timezone or future-dated notes, but experiment
   history should use exact UTC timestamps or it will become hard to audit.

## My Read On Current Product Status

The current classifier is useful as an assisted triage demo:

- Upload a PDF.
- Extract text.
- Score pages with text-only TF-IDF/logreg.
- Force-keep no-text pages.
- Surface likely takeoff pages for human review.

That is a real useful thing. But it should be described as conservative page
triage, not as a fully validated page classifier.

The model is not yet good enough to be trusted as an autonomous filter. It can
reduce review load if the user understands that "kept" means "review this" and
"hidden" still depends on a threshold that has not been validated on a large
untouched test set.

## Recommended Next Moves

1. Audit eval labels first.

   Wrong labels in eval corrupt every leaderboard. Prioritize the frozen eval
   permits for blind review and adjudication before another modeling push.

2. Create a real train/validation/test protocol.

   Keep `split_v1` if useful, but add a validation/test separation. Pick the
   operating threshold on validation only. Report final metrics once on
   untouched test.

3. Label more new permits, not more pages from existing permits.

   The strongest evidence says the binding problem is cross-permit
   generalization. Use breadth: more permits, per-permit page caps, finish-page
   targeting where needed.

4. Refresh the embedding cache before judging image/router paths.

   The current image eval has missing embeddings skewed worse on eval than
   train. That makes image/router conclusions less clean.

5. Clean documentation into one current source of truth.

   Update `CLAUDE.md`, `AGENT_PIPELINE.md`, and `schema.sql` notes so future
   agents do not follow SQLite-era instructions by accident. Add a useful
   `README.md` with the current architecture and commands.

6. Add small tests around the critical invariants.

   Keep this lightweight. The goal is not broad coverage; it is to prevent
   another silent split or threshold mistake.

7. Be precise in claims.

   Suggested language:

   - "Demo-ready conservative page triage"
   - "Promising text-only baseline"
   - "Full recall on thin frozen eval at a conservative threshold"

   Avoid:

   - "Shippable classifier"
   - "Zero missed finish pages" without naming the eval size and threshold
     selection method

## Suggested Claude Prompt

Use this when resuming:

```text
Read CODEX_ASSESSMENT.md, STATE.md, RESULTS.md, PLAN.md, and
ESTIMATING_ROADMAP.md. Treat CODEX_ASSESSMENT.md as a critique, not gospel.

Goal: tighten the Model-1 page-classifier evidence loop.

Please prioritize:
1. resolving doc drift around Neon vs SQLite,
2. defining a proper train/validation/test threshold protocol,
3. auditing frozen eval labels before trusting leaderboard claims,
4. proposing the smallest useful tests for split stability, thresholding,
   keep derivation, and no-text fallback.

Do not start a fancy model until the evidence protocol is clean.
```

## Bottom Line

The project is on the right path because it is learning from measured failures.
The biggest danger is not model choice. The danger is turning a useful,
conservative demo into an overclaimed production milestone before the eval
protocol can support that claim.

## Label Audit - Before

Started 2026-07-05 on branch `impl-plan-codex`. This is a focused audit, not a
full relabel of the corpus. The goal is to pressure-test whether the current
labeling system is good enough to support the next data wave and whether the
frozen eval labels are clean enough to keep using for decisions.

Before looking at sampled pages, my expectations are:

1. The broad taxonomy is probably good enough.

   I expect most obvious categories like MEP, elevations, details, cover/index,
   floor plans, and finish plans to be usable. The skill instructions are
   detailed, and the observed data has clear title/text signals.

2. The highest-risk labels are hybrids and adjacent classes.

   Likely confusion pairs:
   - `floor_plan` vs `finish_plan`
   - `finish_plan` vs `finish_schedule` on mixed schedule/plan sheets
   - `floor_plan` vs `life_safety` where egress plans show real floor layouts
   - `floor_plan` vs `detail` for enlarged room/unit plans
   - `finish_plan` vs `elevation_section` for bathroom/interior finish sheets

3. Finish pages need heavier review than ordinary pages.

   A missed finish page is business-critical. I expect the current first-pass
   labels to be directionally useful, but I would not trust finish labels in
   eval without second-pass review/adjudication.

4. Sheet-title coverage is uneven.

   The page image labels can be correct even when `sheet_title` is blank. That
   is acceptable for Model 1, but it hurts grouping and scale work. I expect
   the audit to find useful labels with weak metadata extraction.

5. Generic agreement is the wrong metric.

   The audit should emphasize finish false negatives, false finish positives,
   and whether observations like `scale_visible`, `finish_codes_visible`, and
   `room_labels_visible` are reliable enough for Stage 2/3 probes.

Post-audit notes will be appended below after the agent review finishes.

## Label Audit - After

Completed focused agent audit on 2026-07-05. The audit packet was built from
Neon current truth over the frozen split_v1 eval permits:

- Eval current-truth pages: 725
- Eval finish pages: 15
- Risk-weighted audited pages: 68
- Audited all 15 eval finish pages
- Also audited likely finish false negatives, low-confidence/flagged pages,
  floor/demo samples, and adjacent non-keep categories

Summary:

- 67 of 68 pages had the same recommended category as current truth.
- 1 clear category disagreement was found.
- 2 pages were same-category but marked uncertain/policy-sensitive.
- No sampled non-finish page was recommended as a missed finish page.
- 1 of the 15 eval finish labels appears wrong or at least should be
  adjudicated: page_id 4489, currently `finish_schedule`, recommended
  `floor_plan`.

My post-audit read:

1. The page-category labeling system is good enough to keep using.

   I would not redesign the taxonomy before labeling more plans. The categories
   are mostly coherent, and agents agreed with current labels on nearly every
   audited page.

2. Eval finish labels still need mandatory review.

   One challenged finish label out of 15 eval finish pages is a large metric
   swing. Even if the overall label system is good, the eval finish subset is
   too small to tolerate unreviewed labels.

3. Auxiliary observations are not as reliable as category labels.

   Agents repeatedly found missing/incorrect `scale_visible`,
   `dimensions_visible`, `table_present`, `room_labels_visible`,
   `finish_codes_visible`, and `sheet_title` values. These fields are useful
   hints, but Stage 2/3 should derive/check them from page text/PDF geometry
   rather than treating them as final truth.

4. Hybrid policy needs one narrow tightening.

   A page should be `finish_schedule` only when a meaningful finish schedule
   table dominates or is important enough to recover. A mostly blank or
   secondary schedule on a floor-plan sheet should not turn the page into a
   finish_schedule. Conversely, finish-coded interior elevations should stay
   `elevation_section` unless a plan/finish layout dominates.

5. More diverse data remains the bigger issue.

   The audit did not reveal a broken labeling system. It revealed that the
   current labels are serviceable, but the corpus is still too concentrated in
   a few project conventions. The next wave should target more finish-heavy
   permits with caps, not relabel the same whale.

Recommended changes before the next labeling wave:

1. Add mandatory reviewer/adjudicator pass for all eval finish pages.
2. Add mandatory reviewer pass for all new finish pages in the next wave, not
   just a random sample.
3. Tighten the label skill examples for:
   - `finish_schedule` vs hybrid floor/plan sheet
   - finish-coded `elevation_section` vs `finish_plan`
   - `scale_visible` for NTS/no-scale notes vs usable architectural scales
4. Add a small packet-level gold layer for grouping:
   `group_id`, `group_name`, `applies_to`, and `plan_scope`.
5. Keep collecting diverse finish-heavy permits; cap per-permit labels so one
   project cannot dominate again.

## Next Options

My recommendation is Option A first, then Option B. Option C should wait until
we have the small gold set.

### Option A - Collect More Diverse Finish-Heavy Permits

Do this next.

Why:

- The audit did not show a broken labeling system.
- The biggest weakness is data concentration: one Omni permit dominates finish
  examples.
- More Model 1 tuning will not fix cross-permit generalization if the corpus is
  still mostly one finish convention.
- Stage 2 grouping and Stage 3 scale probes will also benefit from seeing more
  project styles, sheet-number systems, finish legends, and schedules.

How:

- Search filenames/page text for finish-heavy signals:
  `finish plan`, `finish schedule`, `room finish`, `floor finish`, `interior
  design`, `LVT`, `VCT`, `CPT`, `carpet`, `tile`, `base`.
- Prioritize permits, not pages.
- Cap each permit so no new whale dominates. A reasonable first cap is 40-80
  candidate pages per permit.
- Review all finish pages from the wave.

Definition of done:

- At least 20-30 permits with some finish content.
- No single permit contributes more than roughly 20% of reviewed finish pages.
- All finish pages in the new wave receive reviewer/adjudicator coverage.

### Option B - Build A Small Gold Packet Set

Do this in parallel or immediately after the first new diverse batch.

Why:

- Page category labels answer "what kind of page is this."
- The estimator needs packet truth: which floor/area a page belongs to, whether
  a schedule is global, and whether a plan is overall/enlarged/unit/detail-like.
- The grouping probe can assign pages, but without gold packet labels we only
  know that it assigned something, not that it was right.

How:

- Pick 10-20 permits/documents across old and new data.
- For every relevant page, label:
  - `group_id`
  - `group_name`
  - `applies_to`: `single_floor`, `multi_floor`, `global`, `unknown`
  - `plan_scope`: `overall`, `enlarged`, `unit_room`, `detail_like`
- Include messy cases: finish schedules, hybrid pages, multi-floor sets,
  enlarged bathroom/guestroom plans.

Definition of done:

- A locked gold file under `codex_work/outputs/` or promoted later into project
  data.
- Grouping probe can report real accuracy against it.

### Option C - Improve Stage 2/3 Probes

Do this after A/B have enough truth to evaluate against.

Why:

- The first grouping probe already showed feasibility: most pages can be
  assigned by rules.
- But improving rules without gold truth risks optimizing vibes.
- Scale parsing looks promising from page text, but it should be tested across
  more diverse vector floor plans.

How:

- Improve grouping rules for finish schedules, interior-design unit plans, and
  global schedules.
- Build the scale probe next: parse scale strings, dimensions, and report
  verified/parsed/conflict/no-scale statuses.

Definition of done:

- Grouping has measured accuracy on gold packets.
- Scale probe reports clear denominators across diverse vector plans.

### Option D - More Model 1 Work

Do not do this now.

Why:

- Model 1 is not the current bottleneck.
- The audit suggests labels are mostly serviceable.
- The next model limitation is data diversity, not architecture.
- A demo is not needed right now.

Only revisit this after:

- More diverse finish-heavy permits are labeled.
- Eval finish labels are reviewed.
- Train/validation/test threshold protocol is clean.
