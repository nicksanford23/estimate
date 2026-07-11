---
name: improvement-loop
description: The standing machine — data funnel, fix-grade loop, engine ladder, decision gates, pod ops, failure survival. Read when taking over the project or deciding what to work next. Written 2026-07-09 (Fable) so any driver continues mid-stride.
---

# The improvement loop (the machine that makes the product better)

> V2 NOTE (2026-07-11): SCHEMA_V2.md now governs identities, claims,
> decisions, datasets; this skill's funnel/fix-grade/gates content still
> stands. A full V2 rewrite is DEFERRED until after the ML-architecture
> session (its outputs — model portfolio, per-model gates — are the new
> content). orchestrate-pipeline is deprecated into here: its surviving
> rules — Sonnet workers/Opus judgment/scripts-for-mechanical routing,
> twin builds for important specs, throttle-by-asking, keep-list changes
> as versioned keep_policy edits (SCHEMA_V2 §14), agent labels are
> machine_observations never human_decisions — are already reflected in
> §6 and SCHEMA_V2.

One question rules everything: **what fraction of real buildings can we take
off automatically, and how accurately?** Every work item must either raise
that number or measure it more honestly. If a proposed task does neither,
don't do it.

Product frame: ASSISTED takeoff. Rooms get product actions, not just areas:
`auto_quantity | geometry_review | open_zone_split | vision_correct_or_redraw`.
The one unforgivable failure is CONFIDENT-BUT-WRONG (silent bid error).
Flagging a room for review is success, not failure.

## 1. The data funnel (runs mostly without tokens)

```
DISCOVERY -> DOWNLOAD -> HARVEST -> CLOSEABILITY -> TIERS -> TAKEOFF+GRADE
```

1. **Discovery** (one-time bulk done ~2026-07-11; then top-ups): enumerate
   One Stop doc lists -> `estimate.discovered_docs` (ours). Politeness is
   sacred: the portal caps BURSTS (~90-180 permits) regardless of pace;
   ~50-min cooldowns are normal rhythm, not failure. NEVER crawl search
   pages from download jobs. Progress: `SELECT count(DISTINCT permit_num)
   FROM estimate.discovered_docs`.
2. **Download**: `scripts/select_batch.py` (junk-filename filter) +
   `scripts/download_batch.py` (direct GetDocument by doc_id — never
   rate-limited; %PDF check BEFORE any R2 PUT; HEAD-check, never overwrite).
   Regenerate candidates from Neon, not stale CSVs.
3. **Harvest** (`scripts/harvest_layered_full.py`, resumable via .seen):
   which pages carry named CAD wall layers -> `data/triage/layered_plans.csv`.
4. **Closeability** (`scripts/scan_closeability_full.py`): do those walls
   actually polygonize into rooms? THE gate. Segment counts and eyeballing
   both over-count (proven: 25-33341 `.3D`, 19-00670 confetti). Only the
   assembled-rooms test is load-bearing.
5. **Tiers** (triage-permits skill): GOLD_ALIGNED / TRAIN_LAYERED /
   TRUTH_AREA / MATERIAL_ONLY / MODEL_TARGET / DISMISS on the
   `pipeline.py` board.
6. **Takeoff + grade** (`scripts/takeoff.py run|grade|scoreboard`): the
   crank. Reproduces bank bit-identical + 26-10321 exactly (acceptance
   tests in `experiments/takeoff_harness.md`). Every run appends to the
   scoreboard — the product metric over time.

## 2. The fix-grade loop (how the engine improves)

Protocol per turn (proven 3x on 2026-07-09: probes 26 -> 27 -> 28):

1. **Grade** against answer keys (`data/triage/truth_area/*.json` — per-room
   SF ±0.02% vs printed totals; treat as truth) using the standing grader
   (`scripts/probe28_regrade.py` lineage / `takeoff.py grade`).
2. **Taxonomy**: bucket every failure by NAMED cause, ranked by SF impact.
   Fix by impact, never by hunch.
3. **One targeted fix**, as a NEW engine version/flag (`geometry_vN.py`).
   Never mutate probe scripts or prior engines — they are records and
   baselines. Append-only applies to code history too.
4. **Re-grade** same pages, same protocol + BOTH canaries (see §3).
5. **Commit + writeup** (`experiments/probeNN_*.md`) including dead ends.
   A documented dead end saves the next session from re-trying it.

Engine ladder + results (182 addressable rooms, 4 truth permits):

| engine | change | missed | med err | fabricated SF |
|---|---|---|---|---|
| v1 (probe2b) | baseline | 71% | 73% | 7.6k |
| v2 (`geometry_v2.py`) | density-gated 3.25ft gap closer + cavity filter | 33% | 31% | 18.8k |
| v3 (`geometry_v3.py`) | anchor-cluster kill + cross-unit flags | 33% | 31% | 4.0k (-79%) |
| v4 (`geometry_v4.py`) | proximity continuity (probe 29, verify result) | — | — | — |

Known dead ends (do NOT retry): naive ungated 4.5ft closer (explodes on
dense pages); cheap blob re-split via arcs-only (0/59 — the closer is the
only thing closing those regions); cavity SHAPE filter beyond ~31% of junk
SF (the rest is other-building blobs — anchor-cluster handles those).
Known cost to manage: anchor-cluster falsely kills fragmented same-building
rooms (~13% of killed SF) -> must route to review, never silent-discard.

## 3. Canaries and honesty rules

- **Canaries** (must never regress, run every engine change): bank
  14-11290 doc 1494156 p3 (layer path, >=13 rooms) and hotel 17-35590
  doc 3523243 p9 (dense page that caused the original explosion).
- Legacy grades and keys below are diagnostic history until requalified under
  the V2 eligibility ledger; they cannot promote an engine or support a demo.
- Grade PRODUCT ACTIONS (probe 23), not polygons-per-label: open-plan
  merges whose member rooms sum within tolerance are correct grouping —
  but a whole-floor collapse that nets out is MERGE_SUSPECT, not success.
- Negative results get written up with the same care as wins.
- Eval splits by frozen conservative leakage group with whole plan sets,
  buildings, revisions, and design families together; never by page.
- A number is only trustworthy against an answer key or two independent
  methods agreeing. Say which one you have.
- Verify inherited claims against raw data before repeating them (twice on
  2026-07-09 a stale over-generalization steered strategy until Nick's
  domain intuition caught it: "only 2 usable layered permits" — biased
  slice; "geometry needs layers" — conflated layer path with rules path).

## 4. Decision gates (the "if X do Y" table)

- **ML training run v2** — GATE: >=15 clean (closeability-passing) layered
  permits across distinct firms. ACTION: retrain vector wall classifier
  (probe 25 harness is the baseline: PR-AUC 0.11 held-out at 2-3 firms —
  the number to beat), hold out >=5 permits, grade BOTH segment PR-AUC and
  downstream rooms-vs-truth via `takeoff.py grade`. PROMOTE into the
  pipeline iff held-out downstream beats rules v-latest on flattened
  permits. GPU pod ~$1-2. Plot score vs #permits (learning curve): still
  climbing -> get more data; flat -> engineer.
- **Download round N** — GATE: `estimate.discovered_docs` has >=500 new
  plan-like rows. ACTION: select/download/funnel (all scripts exist).
- **Golden hunt** — standing: `scan_area_schedules` every new batch;
  schedule-reader confirms; target >=10 TRUTH_AREA and the first
  GOLD_ALIGNED (usable layers + area schedule, same plan).
- **Model 1 retrain** — GATE: labeled multi-firm corpus ~2x rung-2c.
  Frozen split_v1 rules apply. Byproduct labels come from triage.
- **Demo readiness** — GATE: takeoff.py scoreboard shows >=10 permits with
  majority-auto_quantity rooms and zero confident-wrong. ACTION: web
  guides per permit = demo inventory.

## 5. Pod/ops playbook (hard-won 2026-07-09)

- CPU pods via `scripts/deploy_pod.py` pattern (REST create; GraphQL
  dockerArgs broken on this account). cpu3c: 2 vCPU $0.06/hr, 8 vCPU
  $0.24/hr. `volumeInGb` REQUIRES `volumeMountPath` or the pod never boots.
- Pods have python3=3.8 but pip installs to python3.11 — ALWAYS run
  `python3.11` explicitly.
- Ship code via presigned R2 GET URLs or direct scp (pod curl can't sign
  SigV4). Results come back as R2 keys under `claude-repo/*` (the %PDF
  rule guards `docs/` only).
- **"Pod created" != "pod working": demand output rows within 15 minutes
  or terminate.** Verify termination (pods list). Size pods so jobs take
  30-60 min; setup overhead eats anything shorter.
- `scripts/pod_watch.py` (keep running detached): 10-min checks on pod
  billing, output freshness, discovery liveness -> WARN lines in
  `data/triage/pod_watch.log`.
- Session limits kill agents mid-flight but NEVER the machinery: detached
  (`setsid nohup`) scripts + append-only outputs survive; resume agents
  from transcript via SendMessage. Design every long job this way:
  resumable, append-only, progress on disk, self-terminating.
- Long unattended crawls: supervisor script + breaker + strike rules +
  self-termination + status table in Neon (`estimate.discovery_runs`).

## 6. Role split (unchanged, works)

Big model (Fable/Opus): design, diagnosis, taxonomy reading, gate
decisions, reviewing worker output. Sonnet workers: every defined task
(probes, scans, extraction, builds) with tight specs + acceptance tests +
honesty bar in the prompt. Scripts/pods: everything mechanical. If the big
model is doing bulk work, the orchestration is wrong. Workers that go
quiet get checked (output files, not promises); fresh narrow-mission agent
beats a tired 150k-token one for rescue jobs.

## 6a. Cross-vendor dual verification (Nick, 2026-07-11 — standing)

For labeling and any important analysis: TWO independent isolated workers
from different vendors (Claude Sonnet + Codex). Agreement → machine
CROSS-VERIFIED tier (bulk-accept eligible, never auto-confirmed; audit
5–10% of agreements — correlated errors are real). Disagreement → Nick
final; there is no third-agent adjudicator in the two-building pilot. Nick
reviews all disagreements himself. Single-agent output is machine-candidate
evidence only. The V2 pilot
labeling done before 2026-07-12 is DISTRUSTED and quarantined (see
ML_ROADMAP §8.2) — re-run under this protocol.

## 6b. Labeling waves (folded from orchestrate-pipeline, 2026-07-11)

When Model-1 page labeling resumes after the pilot safety gate: assignment files of ≤80 page ids per
worker run (hard cap — context rot past that), built by SQL (rendered ∩
unlabeled), ordered by PROJECT VALUE per Nick's 2026-07-05 priority:
GOLD BAND first (permits with 10-80 rendered pages = product-matched
tenant build-outs), boost on tenant/build-out/interior/renovation/
restaurant/retail/suite descriptions or finish vocab in text; 1-9-page
permits allowed when keep-dense but never as eval packets; >150-page
mammoths deferred, train-side only. SIBLING RULE: a permit with floor
plans but zero finish pages → check its other docs for interior|finish|ID
filenames, queue that single doc. Each page goes through the neutral isolated
Claude/Codex coordinator; Nick reviews all disagreements and the deterministic
stratified agreement audit. Outputs append as machine_observations only, never
human_decisions. Keep-list changes are versioned keep_policy edits
(SCHEMA_V2 §14), never relabeling.

## 7. Where everything lives

- State/plan: `STATE.md` (append-only log; update before ending a session).
- Probe records: `experiments/probeNN_*.md` (never rewrite history).
- Truth: `data/triage/truth_area/*.json`. Board: `pipeline.py board`.
- Funnel outputs: `data/triage/*.csv`. Takeoffs: `data/takeoff/`.
- Shared raw (READ): Neon `permits`+`documents`, R2 `docs/{doc_id}.pdf`.
  Ours (WRITE): `estimate.*` NEW tables only, local `data/`.
- Watchdog log: `data/triage/pod_watch.log`.
