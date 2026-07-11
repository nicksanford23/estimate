# Plan of record

## Label schema (locked 2026-07-04)
Per page, one page_label row: `category` (15-class taxonomy), `confidence`
0–1, `sheet_title` (title-block text or NULL), five observations
(`scale_visible, finish_codes_visible, table_present, room_labels_visible,
dimensions_visible` as 0/1), `flag_reason` (NULL unless the agent raises a
hand), `evidence` (one sentence). Everything else — keep, usefulness,
geometry-readiness, review routing — is DERIVED in code, never hand-labeled.

## Labeling tiers
1. **page-labeler** (Sonnet, ×4 parallel, disjoint documents, ≤80 pages/run)
2. **label-reviewer** (Sonnet, ×2) — re-labels BLIND, then compares. Reviews:
   confidence < 0.8 ∪ flagged ∪ 10% random audit of high-confidence.
3. **label-adjudicator** (Opus) — only labeler↔reviewer disagreements.
Human sees only what all three couldn't settle.

## Scale strategy
~2,300 plan-like docs ≈ 50–90k pages. Agents do NOT label everything:
target ~4–6k labeled pages across diverse documents, train Model 1, and the
model triages the rest. Agent labels are for training, not production.

## Model 1 bake-off (cheapest rung first; leaderboard in data/experiments.csv)
1. Cached embeddings (CLIP / SigLIP / DINOv2) × heads (linear, MLP, XGBoost)
2. + text features (sheet_title, PDF vector text) — likely biggest win
3. Fine-tuned small ViT on RunPod — only if rungs 1–2 miss target
Train both 15-class→collapse and direct binary; compare on the benchmark.

## Dedup (before any training — Nick's catch 2026-07-04)
Permits carry revisions/resubmittals of the same set. Defenses: render one
doc per permit; embedding cosine-similarity pass flags near-duplicate pages
(>0.98) → exclude dupes from eval, downweight in train; NEVER let two docs
of the same permit straddle the train/test split.

## Benchmark (the number that matters)
Per held-out plan set (split by PERMIT, never by document or page): recall of keep pages —
**zero missed finish_plan/finish_schedule**, ≥95% floor_plan/demo_plan,
false positives tolerated. Threshold tuned to over-keep. Generic accuracy
is meaningless at 17.7% keep rate.

## Amendments (2026-07-05, from Nick's review)
- Parallelize experiments, serialize conclusions: cheap independent rungs
  may run concurrently; each experiment changes ONE variable. Skip a rung
  only when it promises no new information, never to "go fancy" blind.
- Production design: distilled model handles everything; pages below the
  confidence bar escalate to a vision-LLM fallback (cents, seconds) — the
  maker/checker pattern running live. Never LLM-for-every-page (margins).
- Reviewer tier order: audit EVAL-split permits first — a wrong label in
  the exam corrupts every leaderboard after it.
- Next render batch: breadth over bulk — more permits, fewer pages each,
  per-permit page cap. Largest-doc-per-permit heuristic caused the whale.

## Loop (once pilot passes)
Label batch → retrain sweep → eval → diagnose worst mistakes → fix cause
(labels/data/taxonomy) → repeat. Every experiment appends one row to
data/experiments.csv: config, packet-recall numbers, notes. Plateau after
3 cycles → stop, bring the human one specific question.

## Status ledger
- Downloads to R2: running (bg), queue 2,272 plan-like docs
- Pilot: 50 pages, new schema, one labeler — in flight
- Next: pilot review → fix skill → full fleet → rung-1 sweep on 1,165
  existing labels (baseline before mass labeling)
