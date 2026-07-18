# Model roadmap by station — v1 DRAFT

Written 2026-07-18 (Claude Fable). For founder + Codex review. Governing
rules: FULL_PROCESS_LOCKED.md (T-LOOP/M1-LOOP: bakeoffs not coronations;
150-surface exploratory gate; sealed exams one-use; models deploy as
replaceable engines behind unchanged gates).

Principle for every station: **script the mechanical part, model the
judgment part, and only model it once verified data exists.** Stations
that are pure math NEVER get models (scale arithmetic, snapping,
measuring, topology, area math) — code is already perfect there.

## S4 — the Drafter (THE model; first and biggest prize)

- Job: crop + anchor point → first-draft outline polygon.
- Candidates for the bakeoff: (a) **SAM 2.1 fine-tune** (prompt-point
  segmentation; harness ALREADY BUILT — frozen encoder, decoder
  retrained; fits our anchor→mask pipeline exactly); (b) **Mask2Former-
  style** semantic/instance model (whole-floor, multi-class room/deck/
  stair/shaft output; see data/training/MASK2FORMER_ALTERNATIVE.md for
  trigger conditions); (c) baseline to beat: rented vision + snap.
- Data: training-eligible surfaces (per-edge confirmed). Gate: ≥150
  across ≥2 projects → exploratory only. Splits by project AND design
  family. Cost: ~$5-20/run on RunPod (runbook written, caps enforced).
- Metrics: edge-acceptance rate at the measuring gate (primary — the
  gate IS the judge), mask IoU + boundary F1 (diagnostic), founder
  fix-time per surface. Promotion per locked T-LOOP rules only.
- Why smaller than it sounds: the model only needs good FIRST DRAFTS —
  precision belongs to snap + gate forever. Draft-model + exact math
  beat a do-everything model in every audit this week.

## S1 — the Page Router (Model 1; second, cheap, low-risk)

- Job: page image (+ extracted text) → type/phase/level + confidence.
- Architecture: image classifier fine-tune (ViT/EfficientNet class) or
  CLIP-embedding + head, PLUS text features (TF-IDF/keywords) — the old
  rung-2 lesson says text carries huge signal when present; router
  combines both.
- Data: page labels verified as projects flow (S1 statuses + founder
  fixes). Legacy ~2,900 labels are UNVERIFIED (trust reset) — salvage
  path: sample-audit to measure noise → weak_train tier only.
- Metric that matters: FALSE NEGATIVES on important pages (missing a
  floor plan is the only real sin; extra pages passing = fine).
  Deploys ONLY as reversible routing assistant; never deletes pages.
- Cost: ~$1-5. Start once ~10 projects have verified routing.

## S2 — Roster/Schedule Reader (third)

- Job: schedule page → structured rows (room, name, finish, area-if-
  printed) with cell provenance.
- Now: rented LLM reads + human confirms (cheap, accurate enough at
  pilot volume). Later: fine-tuned document model (Donut/table-
  transformer class) when volume makes per-page LLM cost/latency matter.
  Trigger: >50 schedules/month or LLM error rate measured >2%.

## S1.5 / S1.7 — Plan-map + Scale

- Stay script + rented-vision fallback + human countersign. Possible
  tiny helper models later (scale-note detector, sheet-title reader) —
  LOW priority; the deterministic cross-check (measure a printed
  dimension) is the real trust and never changes.

## S5 — the Critic (last to modelize, deliberately)

- Job: draft + crop → per-edge verdicts.
- Stays rented AI the longest: independence from the Drafter matters
  most here, and every critic label (agree/reject per edge, later
  confirmed by gate + human) accumulates as free training data.
- Eventually: a pair-input model (image + drawn edge → verdict) distilled
  from that history. Trigger: thousands of gate-adjudicated edge
  verdicts on record. Until then, modelizing the critic would just
  launder the Drafter's blind spots.

## S5.5 reference nomination (inside the gate)

- The candidate-line chooser is currently heuristics (wall-pair
  detection, chase guard). If reviewer-correction data shows systematic
  misses, a small ranking model (features: geometry + ink context →
  which candidate is the room-facing line) can assist NOMINATION ONLY —
  confirmation stays with the reviewer per the constitution.

## S10 — Estimating

- No ML. Policy engine + pricing tables + templates. Ever. Auditability
  is the product here.

## Order of investment (locked to value)

1. **S4 Drafter** — the moat; everything waits on its data gate.
2. **S1 Router** — cheap win, exercises the whole T-LOOP machinery
   safely first.
3. **S2 Reader** — when volume demands.
4. **S5 Critic / S5.5 ranker** — only after adjudicated-edge history is
   deep.

## Review asks

- Codex: challenge the S4 candidate list and the S5-last ordering;
  propose any missing station-model.
- Founder: none of this needs decisions today — it activates station by
  station as each data gate opens.
