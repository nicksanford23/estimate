# Model-1 experiment results (consolidated)

## What this is
This is the consolidated experiment log for **Model 1** (the plan-set page
classifier that decides which pages matter for flooring takeoffs). Every result
row from the three sweep CSVs under `data/` — `experiments.csv` (rung-1 Sonnet),
`experiments_opus.csv` (rung-1 Opus), and `experiments_rung2.csv` (rung-2 / 2b /
2c) — is now folded into a single Neon table, **`estimate.experiment`**, loaded
idempotently by `scripts/experiments.py`. Run `python3 scripts/experiments.py
--leaderboard` to see the ranked board (honest frozen-split numbers on top);
`--load` re-syncs from the CSVs and inserts only rows not already present.

## Headline: the honest numbers on the frozen split (`split_v1`)
These are the rung-2c rows retrained on the **frozen, whale-safe permit split**
(`data/split_v1.json`), with 91%-coverage backfilled page text. Per STATE.md
these are the **first numbers in the whole rung ladder that are safe to compare
across future reruns** — everything before `split_v1` ran on an unstable
reshuffling split (see next section).

| config | n_train | n_eval | finish_recall@0.5 | fp@0.5 | thr_full_finish | fp_at_full_finish |
|---|---:|---:|---:|---:|---:|---:|
| **text_only** (tfidf + logreg + direct_binary) — *chosen v1 family* | 2191 | 725 | **0.267** | **0.006** | **≈0.096** | 0.175 |
| image_only (dinov2 + logreg + multiclass_collapse) | 2109 | 635 | 0.286 | 0.069 | 0.003 | 0.501 |
| router_v2 (text + dinov2, shared-threshold variant) | 2191 | 725 | 0.333\* | 0.019 | 0.000 | 0.989 |

**`text_only` is the chosen v1 family**: finish_recall@0.5 = **0.267**, fp@0.5 =
**0.006**, thr_full_finish ≈ **0.096**. It buys full finish recall at only ~24%
of pages kept (fp_at_full_finish = 0.175) — materially cleaner than the other
two families, whose full-recall operating points collapse toward keeping half
(image_only, fp 0.501) or essentially everything (router_v2, fp 0.989).

\* router_v2's stored `finish_recall = 0.333` is the *shared-threshold* variant
reported parallel to the other columns. Its **canonical, as-designed** operating
point (each branch's own train-tuned full-finish threshold, no eval leakage)
gives finish_recall = 0.267 at frac_kept = 0.032 and **does not reach full
recall** — i.e. the router does **not** beat `text_only` alone. See STATE.md,
"Rung-2c results".

## Why the older numbers aren't comparable
The pre-`split_v1` rung-2 headline of **finish_recall@0.5 = 0.974** (row
`rung2 / text_only / logreg / direct_binary`, same code path as the 0.267 row
above) was a **split artifact**, not real skill. The old `split_permits()`
reshuffled the permit list on every corpus growth, so "seed 42" did not pin
train/eval membership. Under that split the whale permit **`26-12298-NEWC`** (a
~1,000-page hotel project dense with finish-schedule-style text) sat in *train*,
inflating apparent recall in a way that does not survive a whale-safe split.
`split_v1` freezes a stable, whale-in-train, floor-enforced permit split; on it
the same config lands at **0.267**, nearer rung-2b's regressed 0.339 than the
0.974 mirage. Neither 0.974 nor 0.339 should be treated as a baseline going
forward. (STATE.md, "Rung-2b results" and "Rung-2c results".) In
`estimate.experiment` these two eras are separated by the `split_version`
column: `split_v1` (3 rows) vs `seed42_canonical` (46 rows).

## The binding constraint
Per the STATE.md rung-2c diagnosis, the binding constraint is **cross-permit
generalization**, not thresholding or routing. The signal organizes
within-project and transfers weakly across permits at this data size; fixing the
split instability didn't fix that — it just let us see it clearly for the first
time. Per-branch train-only threshold tuning (router_v2's design) generalizes no
better than a shared threshold. The highest-conviction lever is therefore **more
labeled PERMITS** (cross-project diversity), not more pages within the permits
already labeled and not more thresholding/routing cleverness.

---
*Backed by `estimate.experiment` (Neon, schema `estimate`). Loader:
`scripts/experiments.py`. Source CSVs live under `data/` (gitignored). Regenerate
the table any time with `python3 scripts/experiments.py --load`.*
