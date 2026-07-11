---
name: diagnose-model
description: First-principles diagnosis of a model training run — decompose inputs/outputs, verify with measurements, name the binding constraint, order the fix. Run after every sweep/eval.
---

# Diagnosing a training run (first-principles playbook)

You are the highest-judgment model available. Your job after any sweep is
NOT to summarize the leaderboard — it is to find the **binding constraint**
(the one thing most limiting performance) and prescribe the cheapest fix
that attacks it. Every claim must be tied to a number you measured, not a
vibe. Write conclusions into STATE.md when done.

## Step 0 — The learnability test (always first)
Ask: could a competent human do this task given EXACTLY the model's inputs
(e.g. a 224px thumbnail — not the full-res page you can see)? 
- Human could → the information is present; failure is ingredients/data.
- Human couldn't → the model never had a chance; fix the INPUTS first
  (resolution, text, context), more data won't help.

## Step 1 — Rule out plumbing bugs BEFORE interpreting numbers
Bugs masquerade as "the model is weak." Cheap checks, in order:
1. **Join integrity**: n(labeled ∩ embedded) ≈ expected? dtype mismatches
   (string vs int ids) silently produce empty joins.
2. **Leakage check**: features fit on train only? split by frozen conservative
   leakage groups with whole plan sets/buildings and related revisions/design
   families together? Suspiciously HIGH numbers are
   a bug symptom too.
3. **Threshold sanity**: if binary and multiclass behave like opposites, or
   metrics jump between ~0 and ~1 at threshold 0.5, it's probability
   calibration / class-imbalance artifacts — evaluate across thresholds
   before concluding anything.
4. **Cross-check**: if two independent implementations exist, do they agree
   within noise? Disagreement = bug hunt, not diagnosis.

## Step 2 — Locate the failure with the signal probes
- **Nearest-neighbor probe** (is the representation healthy?): NN
  same-category rate vs chance. Healthy space + weak classifier = the
  failure is generalization or heads, not features.
  - Refine: recompute NN excluding same-document/same-permit neighbors.
    Big drop = the space organizes within-project but doesn't TRANSFER —
    a diversity problem, not a feature problem.
- **Per-class breakdown**: which classes fail? Scarce classes failing =
  data scarcity; confusable pairs failing (finish_plan↔floor_plan) =
  resolution/feature blindness; everything failing = plumbing or inputs.
- **Error reading**: pull 10-20 actual misclassified pages and LOOK at
  them (Read tool). Ask of each: was the label right? could I tell from
  the model's input? what feature would have disambiguated?

## Step 3 — Name the binding constraint (pick ONE)
data-bug | input-blindness (model can't see the signal) | label-noise |
class-scarcity | distribution-shift (train permits ≠ eval permits) |
calibration/threshold | genuinely-hard-task

## Step 4 — Prescribe by cost order
Cheapest fix that attacks the named constraint:
1. threshold/calibration change (free)
2. derived-feature or rule change (free)
3. new features from data we already have (hours)
4. more labels, TARGETED at the failing slice — new permits for shift,
   rare classes for scarcity (agent-time)
5. better inputs (higher-res embeddings; ~$1 GPU)
6. bigger model / fine-tune (last; needs the most data)
Never prescribe a fix for a constraint you didn't demonstrate.

## Step 5 — Write it down
Append to STATE.md: the numbers, the named constraint, the evidence for it,
the prescribed fix, and what result would confirm/refute the fix worked.
A diagnosis that isn't written down will be re-derived at full price.

## V2/reset truth gate

Before interpreting any metric, inventory every linked label, extraction,
answer key, geometry run, and decision. Require effective purpose-specific
eligibility for every item; absence is denial. Legacy and unaudited machine
semantics may be used only in an explicitly named `diagnostic_weak` snapshot
and cannot support promotion, sufficiency, demo, or architecture decisions.

## Worked example (rung 1, 2026-07-04 — real)
Leaderboard: best finish_recall@0.5 = 0.365; 100% finish recall only at
fp≈0.86. Step 0: human at 224px CANNOT reliably tell finish_schedule from
door schedule → input-blindness suspected. Step 1: joins verified (2,584
matched). Step 2: NN same-category 0.711 vs 0.10 chance → representation
healthy; neighbors mostly same-document → transfer gap; scarce classes
(24 finish_schedule) concentrated in few permits. Step 3: binding
constraint = input-blindness + distribution-shift, NOT model choice.
Step 4: prescribed rung 2 (text features from pagetext/ — data we already
had) + labeling NEW permits; explicitly deferred fine-tuning. Step 5:
written to STATE.md ("Rung-1 results + Fable diagnosis").
