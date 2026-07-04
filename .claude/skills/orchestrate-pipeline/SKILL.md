---
name: orchestrate-pipeline
description: The orchestrator's manual — how to run the flooring-estimator pipeline (worker routing, labeling waves, throttling, rung ladder, budget rules). Read when taking over as the main/orchestrating model.
---

# Running this pipeline (conductor's manual)

You are the orchestrator. Your job is design, diagnosis, specs, and reading
results — NEVER bulk work. If you're viewing page images or writing
boilerplate for more than a few minutes, you're doing a worker's job.

## Session start
Read STATE.md → PLAN.md → (if new to project) PROGRESS.md + PHILOSOPHY.md.
Trust their numbers over your assumptions; verify anything load-bearing
with one query (`./scripts/db.sh`).

## Worker routing
- **Sonnet workers**: labeling (page-labeler agent), reviewing
  (label-reviewer), and any BUILD task with a tight spec you wrote.
- **Opus agents** (label-adjudicator, or ad-hoc): judgment-heavy, rare
  calls — adjudication, loosely-specified builds, second opinions.
- **Scripts**: everything mechanical. If a script can do it, a script does
  it — scripts cost nothing. GPU (RunPod) for embeddings/fine-tunes/corpus
  inference only; quote cost first (usually <$2).
- **You**: specs for the above, diagnosis (use diagnose-model skill after
  EVERY sweep), architecture decisions, and updating the docs.
- For important builds, consider TWIN builds (two independent workers, same
  spec, different files) and cross-check — it caught a real bug day one.

## Labeling waves (the drip system)
1. Build assignment files (80 page ids per file, one per worker run) via
   SQL: rendered ∩ unlabeled, ordered by priority — currently permits with
   fewest labels first (diversity), previously finish-vocab docs (scarcity).
   Files live in the session scratchpad; regenerate rather than reuse stale.
2. Spawn `page-labeler` agents, one per file, prompt = file path + source
   tag. THROTTLE = how many run concurrently. Ask the user their credit
   comfort; 2 = drip, 8 = burst. Respawn one on each completion
   notification. Hard cap 80 pages/agent — never raise it (context rot).
3. Reviewers (`label-reviewer`) ride behind on: confidence<0.8 ∪ flagged ∪
   10% random audit. Adjudicator (Opus) only on labeler↔reviewer category
   disagreements. Humans only see what adjudication can't settle.
4. Labels are append-only rows in Neon (schema estimate) via
   ./scripts/db.sh. Corrections = new rows, never UPDATE/DELETE.

## The rung ladder (model work)
Current rung status lives in STATE.md. Protocol per rung: worker builds/
runs sweep from your spec → you run diagnose-model skill on results →
name binding constraint → prescribe cheapest attack → update STATE.md →
commit. Never skip a rung because a higher one "should" be better.

## Budget rules
- User's Sonnet credit is the labeling constraint — ask throttle level.
- Orchestrator tokens are precious: outsource builds, keep replies tight,
  batch respawns into notification turns.
- Compute <$5 that saves hours: just do it, note cost (see memory).

## Versioning
Commit code/docs/skills (NEVER data/, .env, settings.local.json — they are
gitignored) at every milestone: rung result, schema change, skill update.
Clear message: what changed + the number that justified it.

## Files map
CLAUDE.md rules · STATE.md live state · PLAN.md plan of record ·
PROGRESS.md narrative · PHILOSOPHY.md thinking rules · MOONSHOT.md
room-boundary track · skills: label-pages, review-labels, diagnose-model,
this one · agents: page-labeler, label-reviewer, label-adjudicator ·
scripts/ per PROGRESS.md §7 · data layers per CLAUDE.md.
