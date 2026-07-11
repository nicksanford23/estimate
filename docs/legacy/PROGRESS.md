# Flooring Estimator — Progress Report
*Covering 2026-07-04 (the day the pipeline went from plan to first trained models)*

## The mission
Build the data engine and Model 1 for a commercial flooring estimating app:
upload a plan set → the pages that matter for flooring (floor plans, finish
plans, finish schedules, demo plans) float to the top. Later moonshot:
auto-suggested room boundaries for square-footage takeoff.

---

## 1. What got built (the pipeline)

| Stage | What exists now |
|---|---|
| **Discovery** | Shared Neon Postgres: 12,106 NOLA permits, 34k+ document filenames (Nick's scrape, auto-syncing) |
| **Screening** | Filename screener: 33k names → 2,272 plan-like docs across ~1,100 permits (junk regex kills invoices/emails/MEP-only sets) |
| **Download** | 2,258 PDFs (99.4%) in shared R2 bucket `nola-permit-docs`, keyed `docs/{doc_id}.pdf`, every file validated `%PDF`. Bucket = the "downloaded" flag for both repos |
| **Render** | 220-doc diverse sample (1 doc per permit, largest file) → ~5,900 page PNGs at 1568px + per-page vector TEXT extracted to `data/pagetext/` |
| **Label** | 2,756 pages labeled by agent fleet into 16 categories (v2 schema below), stored append-only in Neon `estimate.page_label` |
| **Embed** | 5,420 pages × 3 vision backbones (CLIP ViT-L/14, SigLIP B/16, DINOv2 ViT-B/14) on a RunPod 4090; `data/embeddings/base2_*.npz` |
| **Train/Eval** | Two independently-written sweep pipelines (Sonnet + Opus twin builds); 18-model bake-off completed; leaderboard in `data/experiments_opus.csv` |

**Infrastructure decisions that stuck:** SQLite → Neon Postgres mid-day
(concurrent agents kept hitting lock storms); all queries via `scripts/db.sh`;
speed-as-core-tenet written into CLAUDE.md (parallelize, GPU over CPU, small
spend over slow paths); data/ never in git; secrets in gitignored `.env`.

**RunPod lessons (cost ~$0.75 total):** `volumeMountPath` is mandatory or the
pod never boots; community machines sometimes rent but never start (boot
watchdog now auto-hops); the pod image's curl can't sign R2 requests —
presigned URLs are the reliable pattern; >1GB uploads need multipart (boto3).

---

## 2. The agent system

Three-tier design, each tier a permanent definition in `.claude/agents/`:

1. **page-labeler** (Sonnet) — looks at each page IMAGE, judges category +
   confidence + observations. Blind: never sees existing labels. Hard cap
   ~80 pages per run (context rot beyond that was proven yesterday).
2. **label-reviewer** (Sonnet) — blind-then-compare second opinion on
   low-confidence/flagged/audit pages. *(Defined; first big run pending.)*
3. **label-adjudicator** (Opus) — settles labeler↔reviewer disagreements.
   *(Defined; runs after reviewer tier.)*

**Runs completed:** 1 pilot (50 pages) + 4 wave-1 + 8 wave-2 + ~4 wave-3/4
agents ≈ **17 labeling runs, ~1,600 new pages today** on top of yesterday's
1,165. Waves 2+ were *targeted*: aimed at the 59 documents whose extracted
text contains finish vocabulary ("finish schedule", LVT/VCT/CPT) — that's
what multiplied the scarcest class (finish_schedule: ~3 → 24).

**The manual compounds:** the pilot + fleet feedback produced 9 rule
additions to the `label-pages` skill — hybrid-sheet policy (over-keep
anything with finish content), new `life_safety` category, content-beats-
sheet-number, broadened mep (T/AV/VT/FS sheets), roof plans → other, legend
sheets → specs_notes, duplicate flagging, honest-confidence norms, Postgres
mechanics. Every future worker inherits these automatically.

**Label schema (v2, locked):** category, confidence, sheet_title, 5 yes/no
observations (scale, finish codes, table, room labels, dimensions),
flag_reason, evidence (one sentence). `keep` is always DERIVED from category
— never hand-set. Labels are append-only; corrections are new rows.

## 3. Labeling results (2,756 pages, all 16 categories hit)

| Category | n | | Category | n |
|---|---|---|---|---|
| mep | 615 | | schedule_other | 78 |
| elevation_section | 388 | | site_plan | 76 |
| detail | 374 | | cover_index | 52 |
| **floor_plan** ✅ | **235** | | life_safety | 36 |
| reflected_ceiling | 170 | | **finish_schedule** ✅ | **24** |
| other | 157 | | **demo_plan** ✅ | **22** |
| structural | 153 | | **finish_plan** ✅ | **129** |
| specs_notes | 146 | | | |

- **Keep pages: 410 (14.9%)** — matches the ~80/20 junk reality of plan sets
- Pilot vs yesterday's labels: **82% category agreement** (15-way); most
  disagreements adjacent (detail↔floor_plan) — reviewer-tier material
- Recurring findings: hybrid sheets are common (~25% flagged in some docs);
  duplicates confirmed at every level (within-doc repeats, cross-doc
  resubmittals) — dedup handled by embedding similarity, eval split by permit
- Known cleanups pending: 18 harmless duplicate rows (lock-retry era), a few
  self-corrected keep values (append-only corrections in place), labeler-B
  rows still in legacy SQLite awaiting delta-copy

## 4. Model 1, rung 1 — what we tested and what happened

**Setup:** 3 embedding backbones × 3 cheap heads (logistic regression, MLP,
XGBoost) × 2 framings (16-class-then-collapse vs direct binary keep) = 18
candidates. Eval on held-out **permits** (never split by page/doc — revision
leakage), near-duplicates collapsed in eval. Benchmark = the business rule:
**never miss finish pages; false positives are cheap.**

**Result: not shippable yet.** Best candidate (DINOv2 + logreg + collapse):
finish-page recall 0.365 @ default threshold; forcing 100% finish recall
requires keeping ~86% of all pages. All 18 candidates similar or worse.

**Diagnosis (verified, not vibes):**
- Embeddings are *healthy*: nearest-neighbor same-category rate 0.711 vs
  0.10 chance; same-keep rate 0.898. The signal exists.
- But neighborhoods are dominated by same-document pages: the space
  organizes *within* a project and doesn't yet transfer *across* permits —
  and per-permit eval demands exactly that transfer.
- Root causes: (a) backbones see 224px thumbnails where every schedule
  looks like "a table" — the discriminating detail is in the WORDS on the
  page; (b) keep-class examples concentrated in too few permits.

## 5. Rungs going forward (ordered by conviction, from the diagnosis)

| Rung | What | Why it should work | Cost |
|---|---|---|---|
| **2. Text features** *(next)* | TF-IDF/keyword features from `data/pagetext/` (already extracted for every page, production-legit) concatenated with embeddings; same cheap heads | A sheet whose text says "FINISH SCHEDULE" or "LVT-1" is nearly self-labeling; text is exactly what the thumbnail can't see | Free, ~1 hr worker time |
| **2b. Permit diversity** | Resume labeling waves prioritizing NEW permits (w4/w5 files pre-cut in scratchpad) | Cross-project transfer is the measured failure; diverse projects attack it directly | Sonnet usage |
| **3. Sharper eyes** | Tiled higher-res embeddings (3×3 crops + full page, same GPU flow) | Recovers detail lost at 224px; only if 2+2b plateau | ~$1 GPU |
| **4. Fine-tune** | LoRA/fine-tune a small ViT end-to-end on our labels | Last resort; needs more labels to avoid memorizing | ~$5-20 GPU |

After any rung clears the bar (near-zero missed finish pages, tolerable
false-positive rate): **corpus triage** — winner scores all ~90k pages in
the bucket (~$1-3 GPU), agents re-check only what it's unsure about, retrain.
That's the flywheel that makes labeling 10× cheaper from then on.

## 6. Next-session checklist
1. Rung-2 text-feature sweep (worker-built per PLAN spec; Fable reviews
   results + updates diagnosis)
2. Rerun fixed Sonnet sweep (`scripts/train_sweep.py`) → cross-check
   leaderboards between the two implementations
3. Delta-copy legacy SQLite → Neon (labeler-B labels + post-cutover
   rendered pages), archive `data/estimate.db`
4. Resume labeling: new-permit waves + reviewer tier + Opus adjudication +
   `data/review_queue.csv` for human spot-checks
5. Retrain → if benchmark clears, corpus triage; else rung 3

## 7. Where everything lives
- **Rules/state:** `CLAUDE.md` (standing rules) · `STATE.md` (living memory)
  · `PLAN.md` (plan of record) · this file (narrative report)
- **Skills:** `.claude/skills/label-pages/`, `.claude/skills/review-labels/`
- **Agents:** `.claude/agents/{page-labeler,label-reviewer,label-adjudicator}.md`
- **Scripts:** `download_r2.py`, `render_pages.py`, `embed_gpu.py` +
  `embed_remote.sh`, `train_sweep.py` (Sonnet), `train_sweep_opus.py` (Opus),
  `migrate_to_neon.py`, `db.sh`
- **Data:** Neon `estimate.*` (documents/pages/labels) · R2 `nola-permit-docs`
  (PDFs at `docs/`, embeddings + archives at `claude-repo/`) · local
  `data/pages`, `data/pagetext`, `data/embeddings`, `data/experiments*.csv`
- **Costs to date:** RunPod ≈ $0.75 (balance $16.25) · R2 ≈ $0 (free tier
  edge) · Neon free tier
