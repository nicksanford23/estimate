# Commercial Flooring Estimator

A training-data pipeline + models for a commercial flooring estimating app. An
estimator manually "takes off" a plan set — for each room, how many SF of each
flooring material, plus linear feet of base/transitions. This repo builds the
data and models to automate that.

**Two models:**
- **Model 1 — page classifier** — which pages of a plan set matter for flooring
  (floor plans, finish plans/schedules, demo). Currently paused; see STATE.md.
- **Model 2 — square-footage extraction** — per-room SF + material from vector
  floor plans (Route A geometry pipeline). The current focus.

## Data layers
- **Shared raw (READ-only, keyed by NOLA ids):** Neon Postgres `permits` +
  `documents` (`NEON_DATABASE_URL` in `.env`); R2 bucket `nola-permit-docs` at
  `docs/{doc_id}.pdf` (creds in `.env`) — the R2 file existing IS the
  "downloaded" flag.
- **Ours (write):** Neon schema `estimate.*` (`document`, `page`, `page_label`,
  etc.) plus local files under `data/` (triage JSONL/CSVs, renders, pagetext).
  `data/estimate.db` is a legacy, read-only pre-cutover SQLite file — not the
  current write store.
- `data/` and `.env` are gitignored: no PDFs/PNGs/DBs/secrets in git.

## Key entry points
- `scripts/pipeline.py` — permit status board + worklist (`board`, `worklist`,
  `mark`, `evaluate`): what's todo/in_progress/done/dismissed, ranked by value.
- `scripts/triage.py` — mechanical per-permit signal scan (wall-segment count,
  resolved page labels, schedule text, candidate per-room SF) that emits
  provisional SF-pipeline tiers to `data/triage/results.jsonl`.
- `.claude/skills/` — the instruction manuals agents read: `triage-permits`
  (sorting permits into SF tiers), `label-pages` (the 15-category page
  taxonomy), `sf-extraction` (the vector geometry pipeline), `orchestrate-
  pipeline` (worker routing, labeling waves, budget rules), `review-labels`,
  `diagnose-model`.
- `.claude/agents/` — the scoped sub-agents those skills spawn (schedule
  reader, doc selector, page labeler/reviewer/adjudicator, sf-prober, etc.).

## Where state lives
- **STATE.md** — the living project state: verified facts, what's running,
  what's next. Read it before doing anything.
- **ESTIMATING_ROADMAP.md** — the stage-by-stage plan from upload to a
  finished square-footage estimate, with done-numbers per stage.
- **CLAUDE.md** — standing rules (data ownership, labeling discipline, speed
  posture) that override default agent behavior in this repo.

## experiments/ — the probe log
`experiments/` holds dated, numbered probe writeups (`probeN_*.md`) — the
honest, sequential record of what was tried on the SF-extraction problem, what
worked, what failed, and why. They are history: don't rewrite old probes to
match current conclusions: add a new probe instead.
