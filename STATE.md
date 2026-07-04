# Project State

## Current Goal
Model 1: page classifier for plan sets (keep/discard for flooring takeoffs).
Design: PLAN.md. Rules: CLAUDE.md. Then flywheel; later room-boundary moonshot.

## Verified Facts (2026-07-04 evening)
- DATABASE IS NOW NEON POSTGRES, schema `estimate.*`, via scripts/db.sh.
  data/estimate.db is legacy read-only (delta from labeler B pending copy).
- R2 `nola-permit-docs`: 2,258 plan-like PDFs at docs/{doc_id}.pdf (99.4% of
  queue). Downloads NOT rate-limited. Bucket = the downloaded flag.
- Rendered: ~5,900+ pages / 105+ docs (3 shard processes, 2-core box).
  Renderer also extracts page text to data/pagetext/<docid>/.
- Labeled: ~1,500 pages. Keep-class scarcity is THE data risk (only a
  handful of finish_schedules). Mitigation: wave 2 (8 agents, running)
  targets the 59 docs whose page text contains finish vocabulary
  (195 schedule-mention pages, 215 material-code pages found by grep).
- Pilot: 82% agreement vs v1 labels; 9 skill rules added from its findings.
- Embedding run base2 (5,420 pages, 3 backbones) on RunPod 3090 $0.22/hr,
  pod k1ygt2gvu6x18n. Data at claude-repo/embed_in/, results to embed_out/.
- RunPod balance ~$17. Neon API key + RunPod key + R2 creds in .env.

## Failed Attempts (don't repeat)
- SQLite + concurrent agents = lock storms, duplicate rows. Hence Neon.
- RunPod pod with volumeInGb but NO volumeMountPath → container create
  loops forever, pod shows RUNNING but uptime -N, never boots.
- Single-PUT of >1GB to R2 via curl fails repeatedly → boto3 multipart.
- pkill -f <script> from a Bash tool call matches its own shell → suicide.
- 4090 community capacity often dry → fallback ladder of GPU types/clouds.
- Crawling One Stop search <10s spacing → 429 storm (downloads are fine).
- Agent labeling past ~80 pages/context compaction → garbage labels.

## Open Questions
- Labeler B (SQLite era) delta: pages 1618-1680 rows must be copied to Neon
  when it finishes (INSERT without ids — sequence assigns).
- Reviewer tier not launched yet — start after wave 2 lands.

## Rung-1 results + Fable diagnosis (2026-07-04 night)
- 2,756 pages labeled (410 keep, 14.9%; finish_schedule up to 24 via
  targeted waves). Embeddings: 5,420 pages × 3 backbones (RunPod, ~$1).
- Rung-1 sweep (Opus impl, experiments_opus.csv): WEAK. Best
  finish_recall@0.5 = 0.365 (dinov2+logreg+multiclass-collapse); catching
  100% of finish pages requires keeping ~86% of everything. Not shippable.
- DIAGNOSIS (verified): embeddings are healthy — nearest-neighbor
  same-category rate 0.711 vs 0.10 chance. But neighbors are mostly
  same-document pages: the space organizes within-project, doesn't
  transfer across permits at this data size. Fine finish-vs-floor-plan
  distinctions invisible at 224px to generic photo backbones.
- FIX PATH (in order of conviction):
  1. RUNG 2 — text features. pagetext/ was extracted at render time for
     every page (production-legit input). "FINISH SCHEDULE", "LVT-1" in
     text ≈ giveaway. TF-IDF + embeddings concat, same heads. Expect a
     large jump. Have Sonnet/Opus build per PLAN spec; Fable reviews.
  2. More PERMITS labeled (cross-project diversity beats pages-per-doc;
     currently keep classes concentrated in few permits).
  3. Higher-res tiled embeddings (3×3 tiles, another ~$1 GPU pass) if 1-2
     plateau.
- Sonnet sweep impl crashed on xgboost string labels (Opus impl guarded);
  fixed with LabelEncoder, rerun queued for cross-check (experiments.csv).

## Rung-2 results + diagnosis (2026-07-05)
- text_only TF-IDF + logreg + binary: finish_recall@0.5 = 0.974 (vs 0.365
  rung-1) — text IS the signal, as diagnosed. BUT fp@0.5 = 0.794 (keeps
  most junk) and text+image combos did NOT beat text-only.
- Binding constraints (named): (a) TEXT COVERAGE — only 54% of labeled
  pages have text; yesterday's 1,165 pages were rendered BEFORE text
  extraction existed, so much of the gap is backfillable, not scans;
  (b) CALIBRATION — balanced logreg on sparse text over-predicts keep at
  0.5; needs PR-curve threshold choice, and empty-text pages need to be
  routed to the image model, not fed empty vectors.
- Prescriptions (cheapest first): 1) backfill pagetext for old renders
  (script, free); 2) PR/threshold analysis of text_only binary (free);
  3) ROUTER architecture: text model for has-text pages, image model for
  no-text pages, report combined packet metrics; 4) then retrain + decide.

## Next Steps
1. Backfill + threshold + router run (worker) → Fable reads results.
2. Resume labeling waves (w4/w5 files in scratchpad) prioritizing NEW
   permits; reviewers (conf<0.8 ∪ flagged ∪ 10% audit); Opus adjudication.
3. Delta copy SQLite → Neon: labeler-B labels (pages 1618-1680) AND any
   document/page rows the render shards wrote after the cutover (renderers
   kept writing SQLite; Neon shows 5,914 pages, SQLite may have more).
   Insert page_label rows WITHOUT ids (sequence assigns). Then archive
   estimate.db as .pre-neon.
4. Retrain; corpus triage only after finish_recall is credible.

## Last Session Summary
2026-07-04: full pipeline built and running end to end — shared infra (Neon
+ R2), 2,258 PDFs downloaded, renderer sharded, v2 schema + skills + agent
defs + pilot + 2 fleet waves (12 agent runs), Postgres cutover, GPU embed
run live, speed-is-core-tenet added to CLAUDE.md.
