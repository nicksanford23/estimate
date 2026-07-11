# Commercial Flooring Estimator — standing rules

Read STATE.md before doing anything. Update it before finishing a session.
Taking over as driver, or deciding what to work next? Read the
improvement-loop skill — it is the standing machine + decision gates.

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
- V2 is authoritative. Legacy `estimate.page_label` is read-only history; new
  agent labels are append-only `v2.machine_observation` candidates, never
  `v2.human_decision`, and page status is not mutated by labeling.
- `keep` is a versioned policy derived from category; it is not hand-labeled.
- Evidence eligibility is append-only and purpose-specific. Missing
  qualification means DENY. Quarantine never mutates source rows.
- Dataset splits use frozen conservative leakage groups with whole plan sets,
  buildings, revisions, and design families together—never random pages or
  document/permit identity alone.
- Two-building pilot page workers: isolated Claude Sonnet + Codex, with Codex
  reasoning pinned to medium. Nick resolves all disagreements and audits the
  deterministic stratified agreement sample; no third-agent adjudicator.
- Max ~80 pages per worker run, then exit—never continue after compaction.
- Labelers judge the page IMAGE (Read tool); title block is a hint, not a verdict.
- data/ and .env are gitignored — no PDFs/PNGs/DB/secrets in git. Never commit unasked.
- Spend big-model tokens only on design, pilot review, and mistake diagnosis.
  Scripts do mechanical work; scripts cost nothing.
- SPEED IS A CORE TENET (without quality loss): parallelize by default —
  agent fleets, sharded scripts, GPU over CPU. Never serialize work that can
  run concurrently; never wait on a step a cheap rental would collapse.
  Small compute spend (<$5) for hours of wall-clock: just do it, note cost.
- Quality gates that never bend for speed: isolated dual-vendor labeling,
  founder review/audit, leakage-safe frozen splits, append-only evidence and
  decisions, and default-deny snapshot eligibility.
