---
name: review-labels
description: Compare isolated Claude/Codex V2 page observations and route disagreements and deterministic agreement audits to Nick.
---

# Reviewing page labels — V2 dual-vendor policy

1. Require two completed observations from the same assignment, image hash,
   extraction, taxonomy, and rubric version. A retry is a new run ID.
2. Verify each worker ran in its separate read-only bundle and could not see
   legacy labels, peer output, or shared scratch state.
3. Compare primary category and every one of the eight flags independently.
   Do not use source priority or silently merge answers.
4. Exact per-claim agreement becomes `machine_cross_verified`; it is not a
   human decision. Route every disagreement to Nick.
5. Select the agreement audit deterministically and stratify it by category,
   flags, confidence/uncertainty, building, and plan/schedule type. Record the
   sampler version and seed. An overturned agreement expands that stratum.
6. Nick's fresh decision may be written append-only to `v2.human_decision`
   with actor, blind status, taxonomy version, and provenance. Corrections use
   `v2.decision_relation`; never update/delete a decision.
7. Never read or write `estimate.page_label`. Quarantine and effective
   evidence eligibility are checked before any snapshot use; absence means
   denied.

Report run pairs, agreement/disagreement by claim, sampled agreements, Nick's
decisions/overturns, unresolved claims, and elapsed review time.
