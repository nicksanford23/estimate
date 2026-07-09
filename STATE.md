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

## Rung-2b results (2026-07-05, worker run)
- TASK 1 backfill (scripts/backfill_pagetext.py, unmodified from prior attempt
  that died after confirming the 2-prefix fact): 50 docs needed backfill (11
  local data/pdfs/, 39 r2:docs/, 0 unknown-prefix). 0 fetch/extract failures.
  Labeled-page text coverage: 54.0% (1492/2764) -> 91.1% (2519/2764). R2-fetched
  PDFs deleted after extraction; disk untouched otherwise (13G free before/after).
- TASK 2 (scripts/rung2b.py, task2_threshold_table): retrained text_only
  TF-IDF+logreg+direct_binary on canonical split (seed 42) as of NOW
  (n_train=1333, n_eval=1176, 30/7 permits). Threshold table (thr ->
  finish_recall/keep_recall/fp_rate/frac_kept): 0.9->0/0.04/0.003/0.01,
  0.5->0.339/0.403/0.038/0.10, 0.2->0.426/0.55/0.294/0.34,
  0.05->0.861/0.859/0.514/0.57, 0.02->0.957/0.963/0.669/0.72. Exact
  full-recall threshold 0.0118 -> finish_recall=1.0 but fp_rate=0.764,
  frac_kept=0.803 (keeping literally 80% of all eval pages to not miss a
  finish page). Both (a) and (b) targets collapse to this same point — no
  grid threshold reaches finish_recall>=0.97 let alone 1.0.
- **THIS IS A REGRESSION from the rung-2 CSV row (finish_recall@0.5=0.974,
  same code path, same TFIDF+logreg+direct_binary config)**, not a router
  problem. ROOT CAUSE (verified): permit `26-12298-NEWC` (a huge hotel
  project, 1097 labeled pages, 117 finish_plan) landed ENTIRELY in eval under
  the by-permit seed-42 split, because split_permits() reshuffles the *current*
  permit list every time the corpus grows — same seed does NOT mean same
  train/eval membership as more permits get labeled. This permit alone is
  ~93% of eval (1097 of 1176 pages) and ~39% of ALL labeled pages corpus-wide,
  and because it's 100% eval it has ZERO representation in train, so the
  TF-IDF vocabulary never saw this project's room-naming/finish-code
  conventions (checked actual extracted text: dense stair/room labels like
  "SA-01", "PE1", "RB-02", "PT-01" — legitimate finish/material codes, just
  not textually similar to the finish_schedule tables the model learned from).
  This is the text-feature analogue of the rung-1 diagnosis: signal
  organizes within-project, weak transfer across permits, worse when one
  project this large is eval-only. NOT fixed by this run — flagging for next
  session: either (i) stratify/cap a single permit's share of eval, or
  (ii) force very large permits into train, or (iii) re-run rung-2's own
  historical config on a FROZEN split for true apples-to-apples comparison.
- TASK 3 (router): each branch trained + threshold-tuned on its OWN
  train-side has-text/no-text subset only (no eval leakage). Populations:
  train text=1226/img=107, eval text=1023/img=153. TEXT branch (thr=0.917):
  finish_recall=0, keep_recall=0.037, fp=0.002, 114 misses — all but 5 of
  which are `26-12298-NEWC` finish_plan pages (the anomaly above dominates
  here too, since router text-branch train also excludes that permit).
  IMAGE branch (thr=0.994, n_train only 107 pages): finish_recall=0,
  keep_recall=0, fp=0, 1 miss. COMBINED: n_eval=1176, finish_recall=0,
  keep_recall=0.037, fp=0.002, 115 total misses. Router row appended to
  data/experiments_rung2.csv (features=router_v1, n_train=1333, n_eval=1176).
  Numbers are dominated by the same single-permit eval-concentration anomaly,
  not an indictment of the router architecture itself — re-test after the
  split issue above is addressed before deciding router vs. single-model.
- Script: scripts/rung2b.py (new, imports train_sweep_opus.py and
  train_sweep_rung2.py unmodified). scripts/backfill_pagetext.py unmodified
  (already existed from a prior died attempt; verified correct via dry-run
  before running for real).

## Rung-2c results (2026-07-05, split-fix + first trustworthy leaderboard)
- TASK 1 (scripts/make_split.py -> data/split_v1.json, committed): permit-level
  frozen split. Rule: >300-labeled-page permits forced TRAIN (whale guard;
  catches 26-12298-NEWC, 1059 pages). Remaining permits: sha256("42:"+permit)
  hash, lowest ~25% -> EVAL candidate; floors (>=8 eval permits, >=15 finish
  pages) topped up by walking next-lowest-hash TRAIN permits WITH finish pages
  into eval. Result on current corpus (44 permits, 2916 labeled pages, 155
  finish pages): TRAIN 28 permits/2191 pages/140 finish; EVAL 16 permits/725
  pages/15 finish (floor met exactly; 5 permits moved in to reach it). Frozen:
  any permit labeled after this file's generation defaults to TRAIN (closed
  eval list) -- this is load-bearing for scripts/rung2c.py and any future
  rung that reads split_v1.json.
- TASK 2 (scripts/rung2c.py, all 3 configs retrained on the frozen split,
  current labels, 91%-coverage backfilled text; rows appended to
  experiments_rung2.csv as *_splitv1):
  - image_only (dinov2+logreg+multiclass_collapse): n_train=2109/n_eval=635
    (82/90 train/eval pages excluded for missing embeddings -- the base2 GPU
    embed run, 5,420 pages, predates some newer/backfilled renders; eval's
    missing-embedding rate, 90/725=12.4%, is 3x train's 3.7%, worth
    refreshing before trusting image numbers further). finish_recall@0.5=
    0.286, fp@0.5=0.069. Full-recall op point: thr=0.0028, fp=0.501,
    frac_kept=0.546. Per-packet: only 1/10 finish-containing eval permits hit
    100% recall @0.5.
  - text_only (tfidf 1-2gram/30k/min_df=2 + logreg balanced + direct_binary,
    the rung-2 "winner" config): n_train=2191/n_eval=725. finish_recall@0.5=
    **0.267**, fp@0.5=0.006. Full-recall op point: thr=0.0965, fp=0.175,
    frac_kept=0.241 (materially better than rung-2b's 0.803-frac_kept
    collapse, but nowhere near rung-2's original 0.974@0.5). Per-packet: 4/11
    eval permits hit 100% recall @0.5.
  - router_v2 (text branch for has-text pages / image branch for no-text,
    each threshold self-tuned on ITS OWN train-side scores only, per spec):
    text_branch thr=0.5634 -> finish_recall=0.333 on its eval subset;
    image_branch thr=0.9983 -> finish_recall=0.000; missing-both (no text,
    no embedding) pages, 0 in eval, would be conservatively force-kept.
    CANONICAL combined (the router's actual as-designed operating point):
    finish_recall=0.267, fp=0.003, frac_kept=0.032 -- **does NOT reach 1.0**,
    i.e. thresholds picked on train do not generalize to eval even though
    they were tuned to guarantee full recall in-sample. Shared-threshold
    variant (same cutoff on both branches, reported parallel to a/b's
    columns): @0.5 finish_recall=0.333/fp=0.019; exact full-recall needs
    thr=0.0, fp=0.989, frac_kept=0.990 (i.e. keep essentially everything) --
    router is WORSE than text_only alone on the full-recall axis here.
- **KEY FINDING, answering "does text_only land nearer 0.974 or 0.339":
  0.267 -- nearer 0.339 (rung-2b's regressed number), not 0.974.** This means
  rung-2's headline 0.974@0.5 was itself a split artifact: with the whale
  permit sitting in TRAIN under the old reshuffling split, its huge volume of
  finish-schedule-style text inflated the model's apparent recall in a way
  that does not survive a whale-safe, frozen split. Neither previously
  reported number (0.974 nor even 0.339) should be treated as a trustworthy
  baseline going forward -- 0.267 on split_v1 is the first number in this
  whole rung ladder actually safe to compare across future reruns, and it is
  weak: full recall now costs 24% frac_kept (text_only) to 99% (router).
- DIAGNOSIS: the cross-permit generalization problem named in rung-1
  ("signal organizes within-project, weak transfer across permits") is still
  the binding constraint -- fixing split-instability didn't fix the
  underlying data problem, it just let us see it clearly for the first time.
  Per-branch train-only threshold tuning (router_v2's design) does not
  rescue this; it generalizes just as poorly as a shared threshold. More
  labeled PERMITS (cross-project diversity), not more thresholding cleverness
  or more pages within existing permits, is now the highest-conviction lever.
- Script: scripts/rung2c.py (new, imports train_sweep_opus.py and
  train_sweep_rung2.py unmodified, reads data/split_v1.json). Committed:
  data/split_v1.json, scripts/make_split.py, scripts/rung2c.py (commit
  b2486dc) -- nothing else (other files had unrelated concurrent edits in
  the working tree from other sessions at commit time; left untouched).

## Wave 7 + per-permit pivot (2026-07-05)
- POLICY CHANGE (Nick): think per-PERMIT, never total pages. Labels were
  36% one hotel / 48% top-5 permits. Waves now smallest-permit-first
  (orchestrate-pipeline skill updated).
- Wave 7 (1 agent, 80 pages): 19 permits COMPLETED, 7 finish_schedules,
  11 floor_plans. Blind review of hardest 25: keep/hide 96%, category 88%
  (above 82% baseline). Reviewer rescued page 7173 (hybrid cover sheet
  containing a finish schedule -> keep). Adjudicator ruled on 4 disputes
  (7173, 5922, 6452, 6624-triple-row-anomaly).
- Codex added 49 permits/1,864 rendered pages + queued 150 more (see
  codex_work/). Its assessment critiques ADOPTED as pending work: 3-way
  split for threshold selection, doc-drift cleanup, README, tests.
- LABELING PAUSED by Nick (usage). Resume = 1 agent per wave,
  smallest-first, reviewer slice + adjudication after each wave.

## Probe 3 — SF-extraction coverage survey (2026-07-05, worker run)
- Ran scripts/probe3_sf.py (imports probe2b_sf.py's two-tier pipeline
  UNCHANGED, no per-page tuning) across 18 floor_plan pages, 18 DIFFERENT
  permits, has_vector_text=1, spanning 2013-2026 (excludes the 2 permits
  already probed in probe1/2/2b). Verdicts assigned by visual review of
  every overlay (several mechanical ROOMS_GOOD/PARTIAL calls were
  overridden after eyeballing — see data/probe3/results.json
  mechanical_verdict_pre_review vs verdict).
- RESULT: 2/18 ROOMS_GOOD (11%), 1/18 PARTIAL, 11/18 BLOB (61%, the
  dominant failure), 3/18 SCALE_FAIL, 1/18 RASTER. Grading table: 33 rows
  across 7 pages, median |%error| 4.4% -- but this number is misleading in
  isolation: 2 of those 7 pages are BLOB verdicts where scale was correct
  but real rooms never resolved (small coincidental matches only).
- WORST FINDING: the current self-audit (30-10,000 sqft largest room,
  30-200,000 sqft total) cannot catch "right magnitude, wrong location."
  15-08510-NEWC (47 fabricated rooms/16,758.8 sqft, zero overlap with the
  real building) and 13-44083-NEWC (25 rooms/1218.6 sqft, all fabricated
  from a wall-partition LEGEND box in the sheet margin) both PASSED every
  mechanical gate -- exactly the "confident-but-wrong" failure the skill
  calls unforgivable. Kept as 2 of the 4 saved overlays specifically to
  make this visible.
- WHAT WORKS ROUTS-RULES-ONLY: small/simple axis-aligned single-tenant or
  branch build-outs with a modest, clearly-labeled room count.
  WHAT FAILS: dense repeated-unit projects (rowhouses/townhouses/condo
  floors), rotated/non-rectilinear massing, multi-tenant retail with many
  partition types on one sheet, legend-box/detail-box false-positives.
- RECOMMENDATION (for the wall-vs-line-classifier design decision): rules
  do NOT yet cover enough plan types for a demo (61% BLOB, and worse, some
  of the "successes" are silent wrong-location fabrications that the
  audit can't catch) -- a wall-vs-line judgment (ML) layer is needed before
  productizing, PLUS a geometric sanity check on WHERE polygons land
  (e.g. must overlap the page's principal room-label-text cluster / must
  not be majority-contained in a legend/notes bounding box) as a cheap
  rules-based guard in the meantime.
- Artifacts: data/probe3/{results.json,results_raw.json,coverage_summary.md},
  4 overlay PNGs (2 best, 2 worst; rest deleted after grading). Script:
  scripts/probe3_sf.py (new, imports probe2_sf.py/probe2b_sf.py unmodified).

## Next Steps (07-05 list — SUPERSEDED by the 07-09 section at bottom)
1. Resume wave 8 on Nick's go (same pattern as wave 7).
2. Retrain on frozen split with 3-way threshold selection once new
   complete permits accumulate; report per-packet numbers.
3. Doc-drift cleanup commit (CLAUDE.md/schema.sql still describe SQLite),
   README, commit codex_work/.

## Last Session Summary
2026-07-04: full pipeline built and running end to end — shared infra (Neon
+ R2), 2,258 PDFs downloaded, renderer sharded, v2 schema + skills + agent
defs + pilot + 2 fleet waves (12 agent runs), Postgres cutover, GPU embed
run live, speed-is-core-tenet added to CLAUDE.md.

## SF probes 1-3 (2026-07-05, Route A verdict)
- Probe 1 (6 pages): vectors exist 5/6; naive filter 2/6; fixes: rotation-
  relative filtering, hatch suppression.
- Probe 2/2b (hotel page): full pipeline runs end-to-end; scale+geometry
  PROVEN (closed spaces grade 1.4-4.8% vs printed dims); dense interiors
  stay merged — thin partitions indistinguishable from fixture glyphs by
  rules. 11 polygons vs 4; door-arc gap closing works; naive 4.5ft gap
  closer explodes at high density (disabled).
- Probe 3 (18 plans, 18 permits, NO tuning): ROOMS_GOOD 2/18 (11%),
  PARTIAL 1, BLOB 11 (61%, dominant), SCALE_FAIL 3 (regex gaps), RASTER 1.
  Graded rooms: median |err| 4.4%. CRITICAL: 2 BLOB pages FABRICATED
  plausible rooms from legend boxes and PASSED the numeric self-audit —
  confident-but-wrong exists; mechanical audit is insufficient.
- BINDING CONSTRAINT: wall-vs-line classification in dense zones (ML or
  much smarter local heuristics). CHEAP INTERIM GUARD (do first): require
  room polygons to contain/overlap room-label TEXT (rooms have printed
  names); reject polygons inside legend/notes boxes; polygon containing
  many room labels = merged blob, flag not trust. Would have caught both
  fabrications. Room-label text = anchor/seed for segmentation AND the
  merge detector AND the confidence signal.
- Artifacts: scripts/probe_vector_walls.py, probe2_sf.py, probe2b_sf.py,
  probe3_sf.py; data/probe1..3/. Skill: sf-extraction. Agent: sf-prober.

## CATCH-UP: the 07-08 SF sprint, probes 4-24 + triage system (written 07-09)
STATE.md was NOT updated during the 07-08 sprint (~25 commits + a pile of
uncommitted work). This section reconciles. Detail lives in experiments/*.md,
experiments/ML_ARC_layers_to_product.md, SF_TRIAGE_PROCESS_CODEX_REVIEW_V2.md,
and `python3 scripts/pipeline.py board`.

### SF arc (probes 4-24), compressed
- Probes 4-6: rules geometry on dense interiors is a dead end (negative
  results, gap-closing sweeps disproved the gap hypothesis).
- Probe 7 UNLOCK: CAD layers. Wall-named layers -> clean geometry -> rooms
  close. Probe 8: layers double as FREE multi-class training labels
  (wall/door/furniture/finish) for an ML model.
- Probe 11 metric pivot: 4 of the bank's 5 "merges" are CORRECT open-plan
  grouping (no wall exists). Score product ACTIONS, not polygons-per-label:
  auto_quantity / geometry_review / vision_correct_or_redraw / open_zone_split.
  Open areas need FINISH boundaries, not walls -> ML target = walls + finish.
- Bank 14-11290 final (probes 22/23): 10 auto / 2 review / 1 redraw / 5
  open-zone. Layer geometry vs independently-read printed dimensions agree
  within a few % on clean rooms. Caveat: two ESTIMATES agreeing, not truth.
- Probe 24 (buildings #2, #3): 26-10321-RNVN WORKS end-to-end — vision scale
  + layer geometry + vision room-anchor montage (outline-only crops) + finish
  plan materials = 15 rooms, 2,323 SF, carpet/LVT split matches finish key.
  25-33341-NEWC FAILS: wall layer is a `.3D` solid (16k fragments), never
  polygonizes; no tolerance fixes representation. Re-tiered MODEL_TARGET.
- KEY FINDING: "layered" != "geometry-usable". Segment counts over-report
  supply. Closeability scan (data/triage/closeability.csv, 75 permits with
  labeled floor plans): only 11 have named wall layers at all; ~2 PROVEN
  usable (14-11290, 26-10321) + ~3 candidates (19-00670, 20-21673, 23-05848).
- Ground truth: TRUTH_AREA permits (room finish schedules WITH area column)
  exist in our data — probe 18 found 73 candidate pages / 36 permits. BUT
  probe 20: the GOLDEN set (usable wall layers AND parseable per-room SF on
  the same floor plan) is ~ZERO in the current ~150-permit slice. The two
  halves don't co-occur yet. North star for downloads: grow the golden set.
- First honest error number (probe 19): rules geometry on a flattened
  townhouse = +161% vs its 68-room schedule. Expected (wrong path), recorded.

### Triage system + ops (07-08)
- Tier system v2 (GPT+Codex reviewed, adopted): GOLD_ALIGNED / TRAIN_LAYERED /
  TRUTH_AREA / MATERIAL_ONLY / MODEL_TARGET / DISMISS. scripts/triage.py
  append-only w/ run_id; pipeline.py board|worklist|mark|evaluate; agents:
  doc-selector (finds the real arch docs among a permit's chunks),
  schedule-reader (real schedule vs occupant-load noise).
- Board now: 24 done / 1 in-progress / 10 todo / 1 dismissed. TODO includes 4
  TRUTH_AREA permits (24-06233, 20-29653, 24-06748, 26-05332) = complete
  takeoffs readable from the schedule alone, no geometry needed.
- page_select.py (merged from exp_pageselect, validated on all 25): floor-plan
  page selection by title filter + room-label density; fixed 8/25 picks, broke 0.
- Corpus reality (codex_work/outputs/undownloaded_inventory.md): 2,327 docs
  downloaded of 35,756 known in Neon (2,663 permits). Undownloaded: 33,429
  docs, incl. 1,690 plan-like arch PDFs across 733 permits. discover_docs.py
  (webshare proxy pool) enumerates One Stop docs for un-enumerated permits;
  only 1 permit enumerated so far (tool built, barely used).
- Web: per-permit takeoff guide pages (/permits/<id>/guide) for the bank,
  26-10321, 25-33341 (incl. honest geometry-fail imagery).

### Loose ends left by the sprint
- Batch-25 adjudication PENDING: 2 keep-impacting disagreements (page 7470
  21-35659; page 6732 20-21673) + 4 low-stakes. Some label-reviewer runs died
  mid-flight (data/triage/batch25_progress.md).
- 24-32750-NEWC NEEDS_INGEST: docs 7661538 (floor plans L1-3) + 7661540
  (finish schedule A700B) identified by doc-selector, not yet downloaded.
- Codex v2 review consistency fixes (density wording, "exact" claim,
  vector-first language, MATERIAL_ONLY confirmation rule) partially applied.
- LARGE uncommitted tree: probe23/24 writeups, ~15 scripts, web guide changes.
- Model 1 unchanged: 0.267 finish recall @0.5 on frozen split_v1; full recall
  costs ~24% frac_kept. Deprioritized (Nick); labels accrue as triage
  byproduct; retrain when permit diversity roughly doubles.

## Next Steps (07-09, Fable — supersedes the 07-05 list)
1. HOUSEKEEPING: commit the sprint work; finish batch-25 adjudication;
   ingest 24-32750's two docs; apply remaining Codex v2 wording fixes.
2. GO-WIDER with a quality gate (decision recommended to Nick, probe 24 §5):
   enumerate + download plan-like docs in controlled batches, run mechanical
   triage (layer scan -> closeability gate -> area-schedule scan) on each
   batch. Targets: geometry-usable pile >=15 permits, TRUTH_AREA >=10,
   GOLDEN >=3.
3. PROBE 25: first vector wall-classifier baseline — train on clean-layered
   permits' segments (labels free from layers), eval on a held-out layered
   permit with layers stripped. Decides whether ML can replace named layers.
4. Hand-takeoffs ONLY on gate-passing permits + the 4 TRUTH_AREA schedule
   takeoffs (cheap, validates schedule path, produces guides/demos).
5. Model 1: leave as byproduct; retrain at ~2x permit diversity.
