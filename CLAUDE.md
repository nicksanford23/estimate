# Commercial Flooring Estimator — standing rules

Read STATE.md before doing anything. Update it before finishing a session.

## What this is
Training-data pipeline + models for a commercial flooring estimating app.
Model 1 (now): classify plan-set pages — which matter for flooring takeoffs.
Moonshot (later): auto-suggest room boundaries for square footage.

## Data layers
- Shared raw (READ, keyed by NOLA ids): Neon Postgres `permits`+`documents`
  (`NEON_DATABASE_URL` in .env), R2 bucket `nola-permit-docs` `docs/{doc_id}.pdf`
  (creds in .env). The R2 file existing IS the "downloaded" flag.
- Ours (WRITE): Neon schema `estimate.*` (same NEON_DATABASE_URL; page_label
  etc.), plus local files under data/ (triage JSONL/CSVs, renders, pagetext).
  data/estimate.db is LEGACY read-only (pre-cutover SQLite).
- Never write another repo's tables. Never PUT to R2 without `%PDF` validation.

## Hard rules
- `page_label` is append-only. NEVER UPDATE or DELETE label rows.
- `keep` derives from category: 1 iff category ∈ {floor_plan, finish_plan,
  finish_schedule, demo_plan}. Site plans are NEVER keep=1. Don't hand-set it.
- Eval splits by document, never by random pages.
- Worker agents: Sonnet. Adjudication: Opus. Max ~80 pages per agent run,
  then exit — never keep labeling after context compaction.
- Labelers judge the page IMAGE (Read tool); title block is a hint, not a verdict.
- data/ and .env are gitignored — no PDFs/PNGs/DB/secrets in git. Never commit unasked.
- Spend big-model tokens only on design, pilot review, and mistake diagnosis.
  Scripts do mechanical work; scripts cost nothing.
- SPEED IS A CORE TENET (without quality loss): parallelize by default —
  agent fleets, sharded scripts, GPU over CPU. Never serialize work that can
  run concurrently; never wait on a step a cheap rental would collapse.
  Small compute spend (<$5) for hours of wall-clock: just do it, note cost.
- Quality gates that never bend for speed: blind labeling, reviewer tier,
  by-permit eval splits, append-only labels.
