# Project State

## Current Goal (updated 2026-07-11)
V2 era: build the estimator product on the V2 constitution (SCHEMA_V2.md)
— pilot the 10 buildings, ML architecture roadmap, demo vs Togal.
Rules: CLAUDE.md. Superseded design docs live in docs/legacy/ (PLAN.md =
Model-1 design, PRODUCT_UX_V1.md = pre-V2 screens, etc.).

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

## Evening sprint results (2026-07-09, Fable session — probes 26-29, harness, audit)
- TRUTH_AREA answer keys extracted (data/triage/truth_area/): 24-06233 (66
  rooms/14,327 SF), 20-29653 (69/7,308), 24-06748 (36/5,055), 26-05332
  (68/5,279) — all ±0.02% vs printed totals. First real grading truth.
- FIX-GRADE LOOP, 3 turns vs those answer keys (rules path, 182 addressable
  rooms): missed 71%->33%, median err (matched) 73%->31%, fabricated SF
  18,759->4,004 (-79%), 37 cross-unit merge rooms now flagged guaranteed-wrong.
  Dead ends documented: cheap blob re-split (0/59 — the gap-closer is the only
  thing closing those regions); cavity shape filter caps ~31%.
  Engines: scripts/geometry_v2/v3(/v4 in progress). Graders: probe26/27/28_regrade.
  Canaries (bank p3 6->13 rooms, hotel 17-35590) held every turn.
- probe25: geometric wall-classifier does NOT transfer across firms at 2-3
  training permits (PR-AUC ~0.11 held-out vs 0.999 in-domain) — needs the
  wider layered pile, not more features. Baseline to beat.
- takeoff.py HARNESS (run/grade/scoreboard) committed: reproduces bank
  bit-identical (1,178 SF) + 26-10321 (15 rooms/2,323 SF) via acceptance
  tests; honest rules-path baseline on 24-06748. Probe 29 (running) adds
  --engine v4 + proximity continuity fix.
- FULL-CORPUS AUDIT (the "only 2 usable" check): harvest DONE across ~3,400
  docs (local + 8vCPU pod $0.24/hr): 305 permits carry named wall layers,
  984 candidate floor-plan pages. Closeability scoring on pod, ~1h; then
  audit agent calibrates + writes data/triage/usable_layered_report.md.
  Preliminary: ~27 permits pass a rough usable cut — "only 2" was a
  labeled-slice artifact (Nick called it).
- DISCOVERY: one-time full enumeration of all 9,216 unenumerated permits
  running on its own pod ($0.06/hr, self-terminating), results streamed to
  estimate.discovered_docs (NEW table, ours) every 60s. ~830 permits/6.8k
  docs so far, ~11-16% plan-like. ETA ~2 days. Progress:
  SELECT count(DISTINCT permit_num) FROM estimate.discovered_docs;
- DOWNLOADS: priority 1-3 queue DRAINED (962 new PDFs, 452 permits, ~5GB,
  scripts/select_batch.py + download_batch.py). Priority 4 (~8.5k docs)
  deliberately deferred pending audit hit-rates.
- Missing-plan verdicts: 24-06233 Bldgs A/D/F + 20-29653 units 1510A/1512
  floor plans were NEVER FILED (doc-selector read every sibling filing) —
  schedule-only rooms, cap geometric coverage, not our error.
- OPS lessons: RunPod pods have python3=3.8 vs python3.11 w/ pip deps —
  use python3.11 explicitly. "Pod created" != "pod working" — demand output
  rows within 15 min. Session limits kill agents but detached scripts +
  append-only files survive; resume via SendMessage.

## Next Steps (2026-07-09 evening — the plan going forward)
1. TONIGHT: audit report lands -> final usable-layered list (old vs new
   corpus split). Probe 29 verdict -> takeoff.py default engine.
2. ML TRAINING RUN v2 (next session): if usable+clean layered permits >= ~15
   across firms, retrain the vector wall classifier (probe25 harness) on the
   full pile; hold out >=5 permits; grade segment PR-AUC AND downstream
   rooms-vs-truth via takeoff.py grade. GPU pod ~$1-2. Decision gate:
   held-out downstream beats rules-path v4 on flattened permits -> promote.
3. DOWNLOAD ROUND 2 from estimate.discovered_docs plan-like rows as the
   crawl fills (same select/download scripts; regenerate candidates from
   Neon, not the stale codex CSV).
4. GOLDEN HUNT: scan_area_schedules over the 962 new docs + new arrivals ->
   TRUTH_AREA candidates -> schedule-reader confirm -> grow answer-key set
   (target >=10) and hunt the first GOLD_ALIGNED (layers + areas same plan).
5. Takeoff sweep: takeoff.py run over every gate-passing permit -> scoreboard
   -> per-permit guides (web) as demo inventory.
6. Model 1 retrain on the enlarged multi-firm corpus (labels accrue from
   triage byproduct); frozen split_v1 rules still apply.
7. Playbook skill (before Fable window closes): encode the fix-grade loop,
   engine ladder, pod ops, and decision gates so any driver continues.

## AUDIT VERDICT (2026-07-09 ~21:02 UTC) — the "only 2 usable" question, answered
- Full corpus (3,412 docs, coverage gap=0 verified): 305 permits carry named
  wall layers; **148 permits pass the calibrated USABLE gate**
  (125 pre-existing corpus + 23 from today's 962-doc go-wider batch).
- Honest discount: mechanical gate has a known ~1-in-5 false-pass mode
  (19-00670-type shredders are statistically identical to rooms) -> expect
  ~110-120 truly usable after per-permit eyeballing. 53 borderline flagged.
- WHY "only 2" was wrong (report §gate): (a) biased 75-permit labeled slice;
  (b) the old scan used FIXED fpp=0.1 — under-closes small-scale drawings;
  the bank's own ground-truth page scored n_mid=4/cov=0.086 under it. The
  new gate sweeps fpp {0.05,0.1,0.2} + rep_flag layer-name rejection.
- IMPLICATION: ML training gate (>=15 multi-firm layered permits) cleared
  by ~an order of magnitude. Report copy committed at
  experiments/audit_usable_layered_2026-07-09.md; live version + CSVs in
  data/triage/. NEXT: eyeball-verify the 148 (vision agents, cheap),
  then ML training run v2 per improvement-loop skill gates.

## Eyeball verification results (2026-07-09 late, 4-agent fleet + remainder)
- 188/201 gate-pass+borderline permits judged: **71 CONFIRMED, 111
  FALSE_PASS, 6 UNCLEAR** (data/triage/eyeball_verdicts.csv, overlays in
  data/triage/eyeball/). ~13 remain (session-limit cut; resume by diffing
  CSV vs report list; shared renderer scripts/eyeball_render.py).
- DOMINANT false-pass mode is NOT confetti: WRONG-SHEET-TYPE pages
  (electrical/plumbing/HVAC/roof-framing/RCP/site/landscape/elevation
  sheets reusing the arch wall xref outscore the real floor plan).
  ROOT CAUSE: scan_closeability_full.py BAD_TITLE_LINE regex has no MEP
  patterns and its anchored (^...$) patterns miss wording variants
  ("ROOF FRAMING PLAN PART A"). CHEAP FIX queued: add
  ELECTRICAL|PLUMBING|MECHANICAL|POWER|HVAC + substring matching, re-gate,
  re-rank pages per permit -> some wrong-sheet permits recover via their
  actual floor-plan page. True-confetti rate is LOW (~2/37 in slice 4).
- Other decoy patterns catalogued: planting beds/tree canopies, schedule
  tables, watermarks/legend boxes, blobs spanning rooms, stray polygons in
  blank space. MEP/RCP sheets tracing REAL layouts can be CONFIRMED.
- NET: verified TRAIN_LAYERED roster = 71+ confirmed permits (final count
  after remainder + title-fix re-gate). ML training gate (>=15 multi-firm)
  remains cleared ~5x. Next: title-filter fix -> re-gate -> settle roster
  -> ML training run v2 per improvement-loop skill.

## Re-gate queue drained + roster settled (2026-07-10, picked up mid-session
## after a restart lost the prior transcript; work banked in files)
- Reviewed the BAD_TITLE_LINE patch (commit f9dc605, scan_closeability_full.py):
  substring matching + MEP/civil/RCP/plot-plan patterns + page-level
  FLOOR-PLAN-whitelist veto, looks correct. Spot-checked the 4 documented
  MISMATCH cases in scripts/_test_title_patch.py by pulling raw page text
  directly (doc 1878269 p49, 2285638 p36, 5413829 p25, 5411538 p1): none of
  the "ROOF FRAMING PLAN PART A" / "ELECTRICAL PLAN" / "PART HVAC PLAN" /
  "RIGHT SIDE ELEVATION" title strings are in the extracted text at all —
  confirms the predecessor's call that these are a text-extraction (vision)
  limit, not a regex gap. No code fix needed.
- Diffed the predecessor's intermediate outputs (data/triage/regate_phaseA.csv,
  _phaseB_permits.txt, _regate_phaseB_render.csv) against the 124 original
  FALSE_PASS permits: **the re-gate queue was already fully drained** —
  Phase A recomputed bad_title on all 124 (10 RECOVERED/eyeballed, 44
  UNCHANGED, 70 LOST_NO_REPLACEMENT); Phase B widened all 70 to top-20
  candidates, scored all 519 new candidates (0 missing), found 4 new
  gate-passing pages (all rendered + eyeballed, all still FALSE_PASS), 66
  had no candidate even widened. Zero permits needed new ranking/scoring/
  eyeballing this session — just report + roster + board were left undone.
- Added one CONFIRMED row to eyeball_verdicts.csv for 14-11290-NEWC (the
  bank calibration anchor, verified via full takeoff in probe7 but never
  formally logged in the eyeball CSV) so the roster generator has a
  complete source of truth; slice=calibration, append-only.
- **FINAL SETTLED ROSTER: 80 CONFIRMED** (65 pre-existing corpus + 15 from
  the 2026-07-09 go-wider batch; 6 of the 80 recovered by the regate, 1 is
  the calibration-anchor addition), **117 FALSE_PASS**, **7 UNCLEAR**
  (16-36268, 20-29280, 21-07928, 21-35659, 23-01359, 24-22263, 25-31791 —
  need a second look before either bucket). 203 permits judged total (124
  were FALSE_PASS pre-regate; regate flipped 6->CONFIRMED, 1->UNCLEAR).
- Wrote data/triage/train_layered_roster.csv (permit, doc_id, page, fpp,
  verdict_source in {eyeball, regate, verified_takeoff}) — 80 rows, the
  probe-30 trainer's input. Extended scripts/report_usable_layered.py with
  a "Post-eyeball settled roster" section (regenerated
  usable_layered_report.md) as the authoritative final count, distinct from
  the headline's live gate recompute (which undercounts CONFIRMED permits
  whose candidate page has an unrelated stale score_err in
  closeability_full.csv — a pre-existing scoring gap, not a regate issue,
  left unfixed as out of scope).
- Board (data/triage/permit_status.jsonl): marked 78 newly-confirmed
  permits `done --tier TRAIN_LAYERED --note "eyeball-verified 2026-07-10"`
  (skipped 3 already tiered TRAIN_LAYERED: 14-11290-NEWC, 23-05848-RNVS,
  26-10321-RNVN; 22-03626-RNVS got a combined tier
  "TRAIN_LAYERED + READY_NO_FINISH" since it already carried a different
  tier). 81 permits now carry a TRAIN_LAYERED tag on the board.
- NEXT: ML training run v2 (probe25 harness) on the 80-permit roster,
  per improvement-loop skill gates. The 7 UNCLEAR permits are a cheap
  follow-up eyeball if anyone wants a couple more before training.

## PROBE 30 — first wall-model training run (2026-07-10 ~02:00 UTC)
- Trained on 69 verified layered permits / 10 firm-diverse holdout
  (data/probe30/roster.csv). Model: models/wall_model_v2.joblib (+R2 backup
  claude-repo/models/), loader scripts/geometry_model.py.
- Segment PR-AUC holdout: 0.34 pooled (3x the 0.11 probe-25 baseline) but
  firm-spiky (0.10-0.98). Ablation: the bucketed-stroke/feet fixes did NOT
  help (raw 0.359) — honest negative.
- LEARNING CURVE FLAT (15->69 permits: ~0.38 flat). Per diagnose gates:
  ENGINEER, don't just add same-vocabulary data. This REVISES the earlier
  "more firms fixes it" conviction — vector-feature approach is near its
  ceiling; next lever is architecture (graph/neural over vectors, or raster
  U-Net) not volume.
- Holdout-vs-layer-truth downstream: 2.6% rooms matched — segment gains
  don't survive polygonize on unseen firms. Bank canary poor (1/18 anchors),
  hotel canary good (15/17).
- PROMOTION GATE (TRUTH_AREA 4 permits/182 rooms, same grader as v4):
  model beats rules-v4 on ALL THREE: missed 26.4% vs 33.5%, matched<=30%
  29 vs 7, median err 24.6% vs 30.6% (non-uniform: worse on 24-06748).
- DECISION (Fable): CONDITIONAL PROMOTE as an ADDITIONAL candidate engine —
  dual-run rules-v4 + model, prefer whichever anchors more rooms, route
  disagreements to review; do NOT retire v4. Integration queued.
  Full writeup: experiments/probe30_wall_model_v2.md.

## PROBE 30b — dataset audit: firm clustering + holdout leak (2026-07-10 ~14:00 UTC, Fable)
- Nick challenged the flat-curve read ("maybe duplicates, not feature ceiling").
  Measured it: 79 roster permits = 49 distinct firm-clusters (68 unique
  designs). Biggest family: C. Spencer Smith / 1018 Bienville (phone
  504.566.0585) = 14 permits incl. 5 OF THE 10 HOLDOUTS; also LKHarmon x6,
  ChiefArch-dialect x5, metrostudio x4, Prytania-rowhouse refile x4.
- Curve re-read in cluster units: 13->24->33->41->46 clusters across the
  15/30/45/60/69 points — diversity DID grow while the curve stayed flat, so
  "engineer, don't add generic data" SURVIVES the challenge.
- BUT the holdout leaked: 7/10 holdouts have train-cluster siblings; 2 are
  verbatim refiled designs (0.92/0.98 PR-AUC, 29% of pooled segments).
  Honest pooled holdout PR-AUC excl. refiles = 0.214 (not 0.340). Model
  memorizes DESIGNS, not firm dialects (same-firm-diff-building median
  0.364 ~ no-sibling 0.229; 24-07484 scores 0.126 with 9 same-firm sibs).
- Label spot-check (6 renders, data/probe30b/): 3/6 train pages are
  MEP/RCP/structural sheets carrying the wall xref (gate confirmed them
  knowingly — criterion was "closes rooms"); wall layers carry stairs/
  platform/trim/offset-hidden-vectors (LKHarmon, ChiefArch); existing walls
  unlabeled (metrostudio). Label hygiene = second binding constraint.
- PRESCRIPTION (cost order): (1) rebuild holdout cluster-disjoint from
  data/probe30b/clusters.csv + re-baseline v2 (~1h, eval-only); (2) drop
  hidden/clipped vectors + out-of-ink-bbox wall segments at extraction;
  (3) only then feature/architecture work; new data only if cluster-NEW.
- Writeup: experiments/probe30b_dataset_audit.md. No labels touched, no
  retrain, no commits.

## CATCH-UP: the V2 design sprint, 2026-07-10 → 07-11 (written 07-11;
## STATE.md discipline lapsed during the sprint — this reconciles from git)
- **SCHEMA_V2.md = the V2 constitution, v1.4 LOCKED for slice-1 build.**
  Founder + Claude + GPT consultation rounds (Nick carries context between
  models). Core: permit ≠ building ≠ plan_set identity spine; sources
  immutable; extraction versioned in 3 tiers (cheap/heavy/semantic);
  machine output = machine_observation, human decisions APPEND-ONLY with an
  explicit supersession/dispute/adjudication relation graph; spaces as
  canonical logical rooms; leakage_groups + clustering_runs for split
  safety; dataset snapshots pin everything; jobs queue. v1.1→v1.4 folded
  GPT amendments + the image-loop checkpoint (§14: trust states, chip
  color law, region confirm, bulk accepts, nav lock).
- **Image-first design loop produced 4 APPROVED mockups**
  (design_specs/{page_review,geometry_review,rooms_finishes,work_queue}
  _APPROVED.png) — these images ARE the build spec (hard rule added to
  design-loop skill after a build agent invented its own layout).
  V2_CLARIFICATIONS.md = the interrogation Q&A log; items 1-10 + rounds
  2-4 folded into §14 at checkpoint; log continues for the pilot.
- **Slice 1 BUILT** (commit cd40d03 + follow-ups): estimate.* v2 schema
  applied (35 new tables), backfill of 12,106 permits + pilot pages /
  observations / reference decisions (binding=false), thin Page Review
  live at /v2 (project-first index cards, /v2/b/[permit], /api/v2/decide
  with supersession), V2ReviewBoard on the canonical 8 flags, GlobalNav
  hidden on /v2. UNCOMMITTED WIP in tree: V2Tabs.tsx +
  /api/v2/geomoverlay + edits to decide/V2ReviewBoard/v2Db — looks like a
  geometry-overlay tab mid-flight; review before building on it.
- Pre-V2 ops layer also landed 07-09/10: /ops Mission Control (funnel,
  permit browser, check queue, model report card), Permit Workbench,
  start_site.sh one-command site, overnight_downloader on a pod (drains
  discovery into R2, %PDF-validated, exception-hardened).
- **DISCOVERY CRAWL COMPLETE** (verified 07-11 by query): 9,216 distinct
  permits / 85,538 docs in estimate.discovered_docs. Download-round gate
  (>=500 new plan-like rows) is wide OPEN — overnight_downloader has been
  draining it; check its R2 log snapshots for how far it got.
- FABLE_FINAL_DAYS.md = the agenda for the remaining ~2 Fable days
  (housekeeping, skills audit, Togal blind teardown, pilot, ML
  architecture deep work + demo-data sufficiency analysis).

## Housekeeping session (2026-07-11, Fable — this entry)
- STATE.md catch-up written (above). Memory refreshed (V2 era, Nick's
  working style, window status).
- **Togal teardown STARTED (blind protocol):** 3 background agents
  analyzing the 55 frames in togal_teardown/screenshots/; Nick supplies
  the video transcript next; GPT's existing analysis stays unseen until
  Claude's independent analysis exists. Outputs land in
  togal_teardown/.
- **Skills audit (the retirement manual):**
  - improvement-loop: KEEP; V2 rewrite DEFERRED until after the ML
    architecture session (its outputs — model portfolio, gates — are the
    new content; rewriting twice is waste). Survivors of
    orchestrate-pipeline folded in meanwhile.
  - orchestrate-pipeline: DEPRECATED (banner added) — worker routing,
    twin builds, budget rules folded into improvement-loop; labeling-wave
    mechanics preserved there for reference; keep-list-change procedure
    superseded by SCHEMA_V2 keep_policy versioning.
  - design-loop: UPDATED — image-interrogation step + consultation-loop
    pointer + V2 status (4 approved screens, slice 1 live).
  - NEW skills: consultation-loop (the Nick-carries-context Claude↔GPT
    process), spec-driven-dev (locked specs + explicit drift callouts),
    teaching (explain-like-a-teacher standard for Nick).
  - label-pages / review-labels / triage-permits / diagnose-model /
    sf-extraction: KEEP as-is (still accurate for their layers). V2 note:
    agent labels import as machine_observations, never human_decisions.
- Doc status map (root .md files): CURRENT = CLAUDE.md, STATE.md,
  SCHEMA_V2.md, V2_CLARIFICATIONS.md, FABLE_FINAL_DAYS.md,
  ESTIMATING_ROADMAP.md. LEGACY (read-only history, superseded) =
  PLAN.md + AGENT_PIPELINE.md + PROGRESS.md + RESULTS.md +
  FINDINGS_LATEST.md (Model-1 era), OPS_UI_V1.md (superseded by
  SCHEMA_V2 §10 workbench IA), PRODUCT_UX_V1.md (screens superseded by
  design_specs/*_APPROVED.png; Nick's 5 trade questions in it are STILL
  OPEN), SF_TRIAGE_PROCESS_*.md (adopted into triage-permits skill),
  CLAUDE_TASK.md. PHILOSOPHY.md still applies as thinking rules.
- NEXT (per FABLE_FINAL_DAYS): Togal agents report → Claude reviews +
  reads Nick's transcript → independent analysis → THEN GPT
  cross-exchange → decisions. In parallel: ML architecture deep work
  (#5 + #5b demo-data sufficiency), then improvement-loop V2 rewrite.

## ML roadmap consultation R1 (2026-07-11, Codex outside review)
- Read the required V2 constitution/state, improvement/design-loop rules,
  probe 30/30b evidence, Togal teardown, clarifications 11-14, and all four
  approved screen images. Wrote `ML_ROADMAP_REVIEW_R1.md`; did not edit the
  position doc or constitution.
- Strong agreements: stationized cheapest-adequate-engine architecture,
  schedule join as the wedge, heuristics for viewport, rented LLM for schedule
  reading now, cluster-disjoint probe 31 after hygiene/rebaseline, and the
  evidence/coverage/trust-state product direction.
- Main R1 objections: schedule-only quantities must be limited to schedules
  with a verified area source; scale and plan-set assembly are missing stages;
  room semantics should be separated from boundary learning; the current
  coverage buckets overlap; relative improvement over rules is not a demo ship
  gate; LLM join output cannot become binding truth; `/b/[permit]` conflicts
  with V2 building identity; raw perimeter is not bid-ready base LF.
- R1 proposes planning-minimum data volumes per station, a sealed polygon-truth
  set, research/shadow/demo/export gates, a two-axis coverage model, a complete
  route inventory, and a sustainable founder protocol (100% on pilot buildings
  1-2, then 5% stratified blind audit plus 100% risk triggers). These are open
  consultation proposals, not locked decisions.
- NEXT: driver/founder replies per numbered component, adopts/rejects/modifies,
  and clarifies the bounded demo claim before any final-lock or mockup round.

## ML roadmap consultation R2 - founder-declared label reset (2026-07-11, Codex)
- Founder correction: Nick does not trust any semantic labels, training inputs,
  answer keys, or human-like review judgments from the first ML process because
  none received human review. This supersedes the weaker framing that only the
  reported metrics carried founder-verification debt.
- Wrote `ML_ROADMAP_REVIEW_R2.md` as the requested terse delta round. It treats
  the current trusted semantic-label count as zero, preserves all legacy
  artifacts as `legacy_unverified` / `diagnostic_only`, and withdraws probe
  25-30 metrics from promotion, architecture, sufficiency, demo, and ship
  decisions. Exact raw artifacts remain valid sources; extracted/layer/agent
  semantics remain machine observations.
- R2 reopens U-Net-vs-graph and the "architecture must change" hypothesis.
  Before probe 31: write a versioned label book, add true blind review mode,
  label the 10-building pilot completely (proposed split: 2 calibration / 4
  development / 4 sealed bootstrap eval), build `verified_bootstrap_v1`, then
  regrade every legacy engine unchanged against human truth.
- Unqualified legacy labels may appear only in `diagnostic_weak` experiments.
  A source that later passes human audit may enter a distinct `weak_train`
  snapshot with measured noise, never calibration/frozen-test truth and never
  mass-converted to binding human decisions.
- R1's product/architecture corrections remain: Stations 0 and 2b, split
  Station 3, area-schedule scope, human-confirmed constrained joins, two-axis
  coverage, buildingId routes, gross perimeter vs net base, gate ladder, and
  completed screen inventory. Approved review layouts need a blind/audit state,
  not replacement layouts.
- OPEN for founder: ratify the 2/4/4 bootstrap split; commit to one fully traced
  geometry region per pilot building; choose independent 10% domain review vs
  delayed founder relabel; decide whether audited legacy sources are worth
  salvaging; confirm the first bounded external claim.

## ML roadmap consultation R3 - lock withheld pending governance fixes (2026-07-11, Codex)
- Read `ML_ROADMAP.md` v1.2 and Fable's Round-2 verdict. Wrote
  `ML_ROADMAP_REVIEW_R3.md` instead of the requested LOCK document because six
  founder decisions remain pending and a locked spec with PENDING sections
  would violate the spec-driven-dev lock semantics.
- R3 confirms the zero-trust reset, `verified_bootstrap_v1` before probe 31,
  lean label books/blind UI state, early human audit of the four candidate area
  keys, cross-vendor labeling as machine cross-verification only, and all
  adopted R1/R2 station/product decisions.
- New lock blocker: sealed evaluation must order Nick's blind raw-source label
  before any Sonnet/Codex output is revealed. Cross-vendor agreements and Nick
  bulk acceptance may become non-blind training decisions after source audit,
  never calibration/frozen-test truth.
- New lock blocker: the roadmap's proposed quarantine action is not yet
  implementable append-only. `v2.machine_observation` has no status column and
  immutable `human_decision.binding` cannot be flipped. R3 requires a read-only
  truth inventory and quarantine manifest, followed by a constitutionally
  specified registry or eligibility-denial mechanism.
- New lock blocker: active `label-pages`, `review-labels`, `triage-permits`,
  `diagnose-model`, improvement-loop, and `CLAUDE.md` rules still conflict with
  V2/reset policy (legacy page_label writes/status updates, hard-coded vendor,
  machine answer keys treated as truth, document-only split rule). Rewrite
  these before launching pilot agents.
- R3 recommends: approve 2/4/4 as bootstrap smoke evaluation only; delayed
  blind self-relabel now and independent review later; audit legacy sources for
  measured weak-train salvage; trace one region per geometry-capable building
  with 8-10 total; use human-confirmed area-schedule as the first workflow
  claim; approve buildingId routes and measure the audit time before fixing a
  minutes/session budget.
- STILL OPEN: founder ratifications, quarantine mechanism, sealed/bulk trust
  semantics, process-skill rewrites, pilot/rubric manifests, blind-mode
  acceptance criteria, and the larger P3 sealed-set composition.

## Two-building ML pilot plan + UI audit (2026-07-11, Codex)
- Founder narrowed the next pilot to two buildings and rejected a separate
  five-page exercise. Wrote `ML_TWO_BUILDING_PILOT_PLAN.md`; the first five
  pages are now only a coordinator smoke batch inside Building A, followed by
  the rest of the real plan set.
- Recommended complementary pilots from the live V2 inventory:
  `26-10321-RNVN` (42 pages, one legacy geometry run, geometry-centric) and
  `24-06748-RNVS` (15 pages, one schedule region / 36 candidate rows,
  schedule-centric). Existing observations/runs remain legacy candidates.
- Pilot trust flow: Claude Sonnet + Codex independently inspect the same
  isolated rendered image; exact per-claim agreement = machine
  cross-verified; Nick resolves all disagreements and audits a deterministic
  stratified 10% of agreements; Nick confirms every consequential quantity,
  scale, exclusion, link, and demo output. No third-agent adjudicator and no
  blind human-authored labels.
- Honest V2 UI status: Buildings index + Page Review are thin functional
  slices; Rooms & Finishes and Geometry Review are partial legacy-backed
  shells. Work Queue is image-only. Summary, Source Files, Activity, coverage,
  V2 Datasets/Models/Pipeline, dual-label coordination, viewport/scale confirm,
  schedule joins, live geometry corrections, customer upload/review, material
  setup, and export are not built.
- Web verification: production `npm run build` succeeds with network access
  for Google Fonts (one Turbopack file-tracing warning). `npm run lint` fails
  on two pre-existing React errors (`ReviewScreen` and `V2ReviewBoard`) and
  reports nine warnings. Page Review lint must clear before the coordinator
  smoke batch.
- Immediate sequence: fold a lock candidate; truth inventory + quarantine
  manifest; rewrite V2 labeling/truth skills; build neutral CLI coordinator;
  add Page Review comparison/audit states; clear pilot-route lint; run Building
  A pages + geometry walkthrough; run Building B schedule/join; review both
  before retraining, probe 31, plugins, or a larger data commitment.

## Bidirectional Claude/Codex MCP bridge (2026-07-11, Codex)
- Founder clarified that the restart should be blank in the semantic sense:
  no legacy machine output is accepted as trusted truth. No pilot labeling was
  run in this session, no Postgres rows were written, and the restart's trusted
  semantic-label count remains zero.
- Founder chose to build the neutral MCP coordination surface before the truth
  inventory so either conversational client can invoke the other without
  manually coordinating terminals. Added `tools/agent-bridge/` using the
  stable v1 official MCP TypeScript SDK over stdio.
- Project registrations are bidirectional and host-specific:
  `.codex/config.toml` exposes `ask_claude`; `.mcp.json` exposes `ask_codex` to
  Claude. Both expose `consult_both`, `dual_page_label`, and `bridge_status`.
  The gitignored Claude local settings approve only `estimate-agent-bridge`.
- `dual_page_label` copies one rendered image into separate temporary worker
  directories, runs Claude Sonnet and Codex concurrently, validates the same
  structured category/flag schema, and reveals neither result to the other
  before commit. It writes only a raw gitignored JSON artifact under
  `data/agent_bridge/runs/`; the artifact says `database_writes=false` and
  `trusted_semantic_truth=false`.
- Automated MCP protocol tests pass 6/6 using fake local workers, including
  host-specific tool exposure, symlink-escape rejection, separate dual-worker
  output, per-claim comparison, and the no-human-truth invariant. The tests
  require unsandboxed subprocess execution in this environment.
- Live authenticated smoke passed both directions without page labeling:
  Claude returned `BRIDGE_CLAUDE_OK` through the Codex-hosted tool and Codex
  returned `BRIDGE_CODEX_OK` through the Claude-hosted tool. Claude MCP health
  then reported `estimate-agent-bridge` connected; Codex lists the project MCP
  enabled.
- NEXT: truth inventory + read-only quarantine manifest, append-only
  eligibility denial, V2 skill/rubric rewrite, then connect raw MCP runs to V2
  machine observations and the Page Review disagreement/audit UI before the
  first five real Building-A pages.

## Two-building pilot pre-label safety (2026-07-11, Codex)
- No page labels were run. Trusted semantic-label count remains zero.
- Codex page-label subprocess is pinned at `model_reasoning_effort="medium"`
  on every invocation and records `reasoning_effort` in the raw run artifact.
  The model remains the configured Codex default; no undocumented `terra`
  alias was introduced. Claude remains Sonnet/high effort.
- Froze `pilot-page-label-v1` in
  `docs/pilot/PAGE_LABEL_RUBRIC_V1.md` + executable schema/prompt. Rewrote the
  active label-pages, review-labels, triage-permits, diagnose-model,
  improvement-loop, and CLAUDE.md rules for V2 machine-observation-only writes,
  Nick-final review, and conservative leakage-group/plan-set splits.
- Added and applied append-only `v2.evidence_eligibility_event` governance.
  Effective eligibility is latest-event-per-subject/purpose; absence means
  DENY; UPDATE/DELETE are trigger-rejected. Sources are never mutated.
- Generated `data/pilot_safety/truth_inventory_v1.json` and
  `pilot_quarantine_manifest_v1.json`: 57 pages, 199 machine observations,
  1 nonbinding legacy decision, 1 extraction, 36 schedule rows, 1 geometry
  run = 238 legacy subjects. Appended 1,428 denial events (238 x 6 purposes).
  Idempotency rerun inserted zero.
- Bridge protocol tests pass 6/6 with fake workers, including a direct check
  that the Codex labeling CLI receives the medium-reasoning config argument.
- STILL BLOCKED BEFORE FIRST FIVE LABELS: connect raw bridge artifacts to V2
  machine observations behind eligibility enforcement; add Page Review
  comparison/disagreement/audit/quarantine states; clear its two lint errors
  and pass the web build. Current lint remains 2 errors + 9 warnings. This is
  intentionally not bypassed by the completed data/process safety work.

## Pilot Page Review comparison states (2026-07-11, Codex)
- Implemented the founder-selected compact interaction in the existing page
  cards/right panel; no separate comparison page. Card states: gray unlabeled,
  blue exact machine match, red disagreement, amber deterministic audit, green
  fresh human confirmation. Hover summarizes both vendors; click shows both
  categories/confidences and only differing flags in the existing panel.
- Corrected the UI from an obsolete invented flag set to the frozen canonical
  eight in `pilot-page-label-v1`. Active Page Review now reads only
  `agent_bridge:claude|codex` observations; legacy suggestions and nonbinding
  imported flag decisions are hidden, not deleted.
- Added `scripts/import_bridge_run.py`: explicit, idempotent raw-artifact -> V2
  machine-observation import (4 claims/vendor). It rejects non-machine-only
  artifacts and creates zero human decisions / eligibility approvals.
- Audit sampler `pilot-audit-v1` is deterministic and 10%-per-stratum using
  building, category, confidence band, and uncertainty band; minimum one match
  per represented stratum. Agreement remains machine-only until Nick confirms.
- Verification: bridge 6/6; Python compile passes; web lint 0 errors; production
  build generated a fresh BUILD_ID (only the known NFT tracing warning); live
  Building-A V2 route returns HTTP 200 through the public tunnel.
- No page labels run yet. NEXT: Nick visually checks the empty-state/card/panel
  layout, then run/import the first five Building-A pages and review all five as
  the coordinator smoke gate.

## Building A five-page dual-label smoke (2026-07-11, Codex)
- Founder authorized the first five pages. V2 page ids 224-228 map to immutable
  doc 9058456 PDF indexes 0-4. Legacy image paths were stale/missing, so the
  first bridge attempt safely failed before workers ran; rendered fresh 2200px
  images from `data/render_cache/pdf/9058456.pdf` with the new reproducible
  `scripts/render_pilot_smoke.py`.
- First real dual run exposed a Codex structured-output compatibility bug:
  `uniqueItems` is unsupported by the current response schema endpoint. Claude
  completed; Codex failed; no partial results were imported. Removed only that
  schema keyword (Zod still deduplicates flags), added a regression test and an
  isolated Codex-only retry that preserves the committed Claude result and
  failed attempt without exposing Claude output to Codex. Bridge tests 7/7.
- Codex-medium retry succeeded for all five. Comparison: page 224 exact match
  `cover_index`; page 225 category disagreement (Claude `floor_plan`, Codex
  `other`); page 226 both `life_safety` with a `table_present` flag dispute;
  pages 227-228 exact match `life_safety`. Total: 3 exact matches, 1 category
  disagreement, 1 flag-only disagreement.
- Imported exactly 40 machine observations: 5 pages x 2 vendors x 4 claims
  (category, flags, sheet number, sheet title). Import idempotency confirmed
  (repeat inserted 0). Created 0 human decisions and 0 eligibility approvals.
  Live Page Review returns 200 and now shows the blue/red/amber states for Nick.
- NEXT: Nick reviews all five in Page Review, resolves the two disagreements,
  and audits the amber agreement(s). Only after that human smoke check should
  the remaining 37 Building-A pages run.

## Final Codex handoff / UX correction (2026-07-11)
- Added `CLAUDE_MCP_HANDOFF.md` for the next Claude Opus session: exact MCP
  surfaces, smoke state, commands/invariants, and next human gate.
- Founder needs future batch coordination to be ASYNCHRONOUS by vendor because
  Claude and Codex usage replenish differently: Claude may label 10/25/35 pages
  ahead; Codex later catches up against the exact frozen assignment bundles.
  Comparisons form only after both committed outputs exist; pending states must
  be `awaiting_codex|awaiting_claude`; neither vendor may see peer output. This
  is explicitly a design request for Opus, NOT implemented in this session.
- UX correction after founder feedback: the first smoke page again opens with
  the full existing comparison/confidence/flags panel visible. The ONLY added
  escape is `Back to pages`, which closes without saving so Nick can select any
  other card and later return. Removed the over-broad previous/next redesign.
- Do not run the remaining 37 Building-A pages until Nick accepts this corrected
  smoke interaction and Opus scopes the asynchronous vendor queues.

## Project-first execution lock (2026-07-14, founder directive)
- Founder identified the page-first failure directly: a geometry run on one
  convenient second-floor sheet is not a building result when the project has
  schedules and primary plans for several levels. **The unit of ingestion,
  review, geometry execution, and scoring is now the complete plan set for one
  project.** Pages remain worker tasks only. No single-page success may be
  promoted or described as project coverage.
- Clarified the `truth_area` provenance: `24-06748-RNVS.json` was read and
  transcribed row-by-row by Claude Opus, then visually checked. It is valuable
  `agent_transcribed_reference`, not evidence that an automatic table parser
  exists. It remains legacy-unverified / diagnostic-only until freshly
  qualified, and future reusable extraction must preserve table/cell geometry,
  raw text, normalized values, version, and source evidence.
- Schedule capability split is binding for implementation: `room_finish`
  (material but no area), `room_area` (printed area), and `room_finish_area`.
  Do not discard material schedules because they lack area. `14-11290-NEWC`
  is the material-join development case; geometry supplies area. `24-06748-RNVS`
  is the combined area+finish development case and can diagnose geometry.
- `24-06748-RNVS` is the first complete development project. Packet:
  A100 schedule p4; required primary proposed-plan views A101 p5 / A102 p6 /
  A103 p7 / A104 p8; A201 p10 is support-only and must not be double-counted.
  Schedule expectations: L1 8 rooms/1,410 SF; L2 13/1,322; L3 10/1,242;
  L4 5/1,081; 36 rows / 5,055 transcribed SF vs 5,054 printed.
- Baseline at the moment of this directive was **INCOMPLETE**: only A102 p6 ran; 11 polygons,
  5 numbered, 6 unidentified, 616.2 measured SF vs 1,322 scheduled Level-2
  SF, and 0/5 numbered polygons within +/-10%. This is a useful geometry
  failure packet, not training/eval/demo evidence. It is superseded by the
  complete-project diagnostic recorded in the next section.
- Added the locked process doc
  `docs/pilot/PROJECT_FIRST_EXECUTION_V1.md`, machine-readable packet
  `data/pilot_projects/24-06748-RNVS.project_packet_v1.json`, and fail-closed
  guard `scripts/validate_project_packet.py`. Strict validation must fail until
  every required primary view has a recorded geometry outcome.
- Architecture direction: hybrid, cheapest adequate route per confirmed
  viewport. Deterministic project assembly/viewport/scale/text/anchors first;
  clean named-layer geometry when available; ML segment semantics for flattened
  vectors; raster segmentation for scans; finish-boundary extraction separate
  from walls. Deterministic code retains polygonization, transforms, arithmetic,
  provenance, and confidence gates.
- Immediate sequence: confirm the four proposed-plan viewports -> create levels
  and canonical spaces from all 36 schedule rows -> link schedule/plan anchors
  -> baseline the unchanged engine on all four levels -> classify every failure
  -> fix deterministic residuals -> use ML only for measured ambiguous-boundary
  residuals -> freeze and run unchanged on a complete canary project.

## 24-06748 whole-project execution result (2026-07-14, Codex)
- Created/applied the machine-side project assembly: one plan set/document
  association, levels 01-04, 36 candidate space identities, four proposed
  plan-view regions, four region-geometry observations, and four level
  observations. Created zero human decisions, zero source links, and zero
  eligibility approvals. Plan-set, schedule-region/rows, and viewports still
  require human confirmation.
- Fixed the page-first default in `scripts/takeoff.py`: when an active document
  has multiple labeled `floor_plan` pages, `resolve_pages` now returns all of
  them in page order. It no longer ranks them by line richness and silently
  selects one. The explicit project-packet runner remains the authoritative
  complete-project path.
- Ran unchanged v4 on all required primary pages A101 p5, A102 p6, A103 p7,
  and A104 p8. Whole-project result: 20/36 scheduled identities found, 2/36
  exact numbered rooms within +/-10%, 16 missing identities, and 18
  unidentified polygons. Coverage is complete; geometry quality failed.
- Added auditable polygon PDF bounds plus an opt-in project viewport constraint.
  The constrained v4 rerun removed no candidates and changed no quality metric,
  proving viewport selection is not the dominant residual failure.
- Compared engines across the same complete project: v4 = 20 identified / 2
  accurate / 16 missing / 18 unidentified; existing model = 11 / 0 / 25 / 25;
  dual = 21 / 2 / 15 / 15. Keep v4 default, do not promote the existing model,
  and keep dual diagnostic-only. Dual does not improve accurate room quantity.
- Root residual: boundary semantics, not a single bad floor choice. Failures
  include merged small rooms, partial garages, exterior/adjacent-space leakage,
  open-zone divisions, and deck/finish boundaries that wall-only geometry does
  not encode.
- Added `scripts/grade_project_geometry.py`, per-run machine-readable/Markdown
  diagnostics, and
  `docs/pilot/24-06748-RNVS_GEOMETRY_DIAGNOSTIC_V1.md`. The next data artifact
  must be human-corrected geometry for every one of the 36 spaces with boundary
  type and plan/schedule source links. Train a revised semantic-boundary model
  only after that complete-project correction set exists; split eval by project.

## Geometry architecture reboot (2026-07-14, founder direction)
- Founder correctly rejected the framing that either v4 or the current ML model
  merely needed approval. Complete-project evidence shows both are unusable for
  quantities (2/36 vs 0/36 accurate numbered rooms). They remain diagnostic
  proposal sources only.
- Locked `docs/pilot/GEOMETRY_REBOOT_V1.md`: pivot from wall-segment
  classification to room/quantity-zone segmentation. First test is a
  point-prompted mask baseline using known room-label locations; the supervised
  target is in-domain instance/semantic segmentation with room, finish,
  exterior/deck, wall/obstruction, and ignore semantics. Deterministic code
  continues to own PDF transforms, snapping, scale, area math, and audits.
- Added `scripts/build_geometry_annotation_packet.py` and generated a 36-task
  complete-project packet. Printed schedule SF is reference evidence, never a
  polygon label. Every space—including missing rooms—requires a human outcome,
  boundary type, and PDF-coordinate polygon/open-zone/unresolved result.
- Cloud GPU work is gated: no RunPod spend until the reproducible input bundle,
  container/checkpoint, max runtime, output path, and budget cap are fixed.
  Experiment order is promptable zero-shot baseline -> supervised segmentation
  -> vector graph model only if exact-boundary residuals justify it. Promotion
  requires project-held-out improvement on all primary metrics and a second
  complete-project canary.
- Imported the viewport-constrained v4 diagnostic into V2 Geometry Review for
  A101-A104: run ids 4-7, machine predictions only, with zero human decisions
  and zero eligibility approvals. Updated run selectors to show page/sheet,
  actual engine, and run number. This is a correction queue, not approval.

## SAM test and project portfolio lock (2026-07-15, founder clarification)
- Clarified the responsibility split for a beginner-operable workflow: SAM
  proposes pixel masks from room-label point/box prompts; it does not establish
  plan scope, calculate SF, understand flooring rules, or attach materials.
  Deterministic PDF/vector code retains transforms, scale, edge snapping,
  polygon conversion, area math, and audits.
- `24-06748-RNVS` is the one complete smoke project. All four viewports and all
  36 scheduled spaces must receive SAM Small prompt variants (point-only,
  point+negative room labels, and point+rough box), with Large compared only
  after end-to-end plumbing passes. Save all candidates; never select a mask
  merely because its area resembles the schedule answer.
- The first gate is annotation utility: does the proposal reduce correction
  effort versus drawing from scratch? Agentic review may flag contamination,
  missing space, wrong view, and suspicious area, but agent agreement remains
  machine evidence. One project cannot promote a model to production.
- Portfolio lock: one smoke project -> three to four diverse complete
  development projects -> two untouched complete evaluation projects. Initial
  planning range is roughly 150-300 corrected room/quantity-zone masks. Split
  by project and plan revision; never leak floors/crops from one building
  across train and evaluation. `14-11290-NEWC` is a finish-join development
  case, not sealed SF truth without human geometry.
- RunPod is not 24/7 by default. Complete local preparation before spending:
  viewport renders, 36 prompts, coordinate transforms, pinned SAM container,
  result schema, budget/runtime cap, and cleanup. Use one temporary on-demand
  Pod for the smoke, retrieve and verify outputs, then terminate. If production
  is intermittent, use scale-to-zero Serverless Flex; an active worker is a
  later latency/business decision.
- No RunPod key is needed yet and no secret may be pasted into chat. When
  automation is ready, use a dedicated minimum-permission `RUNPOD_API_KEY`
  Codespaces secret. Start with a small prepaid balance and auto-pay disabled.
- Canonical details now live in `docs/pilot/GEOMETRY_REBOOT_V1.md`; project
  split rules are mirrored in `docs/pilot/PROJECT_FIRST_EXECUTION_V1.md` and
  `ESTIMATING_ROADMAP.md`.

## SAM smoke G0+G1 executed (2026-07-16 evening, Fable session)
- G0 package built + PASSED (agent): 4 viewports @24px/ft, 35/36 prompts
  (33 pdf_text, 2 visual_manual: 209A/211; 210=7SF closet explicit no_anchor),
  transforms round-trip 6.5e-13px, fake-mode dry run 421 checks PASS.
  Duplicate-anchor diagnosis: door tags share the room-number convention;
  rule = keep hit with "SF" token below, reject `| `-neighbor hits.
  Scripts: build_sam_smoke_bundle / sam_smoke_runner / verify_sam_smoke_results.
- G1 RAN on RunPod 3090 (~$0.15 total, pod terminated): SAM 2.1 Small AND
  Large, 35 rooms x 3 variants x 3 masks each. Results verified locally
  (results_gpu/, results_gpu_large/). OPS: Nick's new payment = NEW RunPod
  account (user_3GbOkxH..., $15 balance); dockerArgs boot STILL broken
  (2 pods crash-looped) -> SSH-PTY path; account proxy SSH denied (no
  registered pubkey on new acct) -> DIRECT ssh via pod public ip:port
  works (key ~/.ssh/runpod_ed25519 injected via PUBLIC_KEY env).
  deploy_sam_smoke.py (agent) + deploy_sam_smoke_lean.py; update
  SSH_ACCOUNT_SUFFIX before reusing proxy path.
- G1 VERDICT (visual, image rule): raw masks = confetti (holes at every
  stroke; point-only grabs the label tag itself). After deterministic
  cleanup (binary_closing+fill_holes+largest-component): closest-candidate
  DIAGNOSTIC vs schedule = 15/35 within 10%, 26/35 within 25% (Large).
  Visual: 209 M.BATH + 107 GARAGE = coherent wall-following rooms
  (trim-and-accept quality); 204 = right area WRONG shape (furniture
  meander, laundry bleed); several rooms garbage. Root cause: full-strip
  images downscaled by SAM to ~10px/ft -> walls ~1px. NEXT = G1b per-room
  crops at native resolution, same harness, ~$0.15.
- Editor BUILT (agent): /v2/annotate/[permit] — SVG polygon editor, new
  files only, append-only data/geometry_annotations/human/*.outcomes.jsonl,
  label-book outcomes/boundary types, proposal-preload hook
  (results/proposals_for_editor.json). Lint/tsc clean. NEEDS Nick visual
  sign-off (no approved mockup — functional pilot slice).
- Label book DRAFT at docs/pilot/GEOMETRY_LABEL_BOOK_V1_DRAFT.md — 10 rules
  each with proposed default + FOUNDER ANSWER: pending; Codex review queued.
- OPEN: Nick label-book answers; editor sign-off; G1b crop rerun; RunPod
  key was pasted in chat (Nick accepted risk, rotate at leisure); register
  ssh pubkey on new acct (updateUserSettings mutation needs String! fix).

## G1b crop rerun + 3-arm bake-off (2026-07-16 late, Fable session)
- G1b bundle (agent): 35 per-room crops from ORIGINAL PDF, 16.5-48 px/ft
  (median 33, longest side ~1000px = SAM native), per-task transforms,
  runner/verifier/review/deploy made bundle-aware (no fork, G0 defaults
  intact). Dry-run + QA PASS. bundle_g1b/, G1B_REPORT.md.
- G1b GPU run (~$0.15, pod jf4uvblse6vyyw, direct-ssh ship again, pod
  terminated): Small+Large on crops, both verified 421 checks PASS
  (NOTE: poll's default verify ran against the G0 bundle -> spurious dim
  errors; re-verify with --bundle bundle_g1b passes).
- SCOREBOARD (closest-candidate diagnostic vs schedule, after
  closing+fill_holes+largest-component cleanup): G1 full-strip Large =
  15/35 <=10%, 26 <=25%. G1b crops SMALL = 20/35 <=10%, 27/35 <=25%
  (Small BEATS Large on crops: 11/22 for Large). VISUAL: 204 now a
  true wall-following room shape (was the shape-failure case), 101
  correct incl. interior RR block carve-out but leaks through windows
  into landscaping (trimmable). Crops fix confirmed as the dominant lever.
  Results: results_gpu(_large)/ = G1b; results_gpu_g1_full(_large)/ = G1.
  Scoring artifacts: g1b_cleaned_best.json, qa_g1b/cleaned_*.png.
- ARM 3 launched (Nick's idea, in-house, no OpenAI key): 4 Opus vision
  agents (one per level) outline the same crops per the label book,
  polygon px + per-edge rationale + confidence ->
  data/sam_smoke/24-06748-RNVS/claude_vision/level_0*.json. Independent
  of SAM results by instruction. Pending completion -> convert to
  results-schema, same grader, 3-way review cards, winners ->
  proposals_for_editor.json for the /v2/annotate editor.
- Nick reframe (product insight, adopted): the bottleneck is not drawing
  speed but boundary KNOWLEDGE — proposals exist to teach where lines
  go; Nick learns over 5-10 projects; bulk-accept + stratified audit is
  the human gate (page-pilot pattern). Machine agreement stays evidence,
  never truth.

## Bake-off v1 verdict (2026-07-17 early, Fable session close)
- ARM 3 (Claude vision, Nick's idea) = primary proposal-engine candidate:
  one-shot 15/35 <=10% / 29/35 <=25% vs schedule, NO selection problem
  (SAM arms' better buckets require best-of-9 vs the answer key — product
  can't do that; SAM's own-score pick = 1/35). Crisp 4-7 vertex polygons
  on wall faces (107 GARAGE 0.4% err, 204 clean incl. diagonal wall);
  calibrated confidence (low-conf rooms ARE the failures: 305/306/307
  open-plan clipped by crops, 104, 209A). Full table + verdicts:
  data/sam_smoke/24-06748-RNVS/BAKEOFF_V1.md.
- SAM crops arm retained as independent cross-check (vision+SAM agreement
  = candidate auto-gate). SAM full-sheet retired. Small > Large on crops.
- Editor preload LIVE: results/proposals_for_editor.json = 35
  claude_vision_v1 polygons in PDF coords (transform validated 0.001pt).
  /v2/annotate/24-06748-RNVS should now offer them as starting shapes.
- Nick's approval-loop vision (proposals -> confidence gate -> Telegram
  card -> tap = append-only human decision -> retrain on RunPod) adopted
  as the product spine; spec draft owed:
  PROPOSAL_APPROVAL_LOOP_V1_DRAFT.md. Gate must be earned (cross-arm
  agreement + mechanical checks + measured precision), never model
  self-confidence.
- Session total spend ~$0.65 of $15. NEXT HUMAN GATES: label-book answers
  (+2 new Qs: elevator shafts, undrawn deck splits) + Codex review;
  editor visual sign-off; review arm-3 proposals in editor. NEXT DRIVER
  WORK: approval-loop spec; open-zone crops fix (level-viewport context
  for open plans); then dev-portfolio expansion per GEOMETRY_REBOOT_V1.
