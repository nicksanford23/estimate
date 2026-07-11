# Fable's final-days agenda (Nick's priorities, recorded 2026-07-11)

*~2 days of Fable left. Rule: spend Fable time on what Opus can't do as
well; leave clearly-specced execution for later drivers.*

## 1. Housekeeping restart (first, cheap)
- STATE.md updating LAPSED during the V2 design sprint — resume the
  discipline; write the catch-up entry (V2 constitution, image loop,
  four approved screens).
- Memory files: refresh (V2 era, consultation loop, Nick's working style).
- Repo cleanup for V2: mark what's legacy/obsolete, what carries forward.

## 2. Skills audit = the retirement manual for Opus
Go through every skill: keep / kill / rewrite for V2. Priorities:
- improvement-loop: rewrite for V2 (stages, claims, pilot protocol).
- orchestrate-pipeline: largely superseded — fold survivors into
  improvement-loop.
- design-loop: add the image-interrogation step (proved itself) + the
  consultation loop.
- NEW skill: consultation-loop — the Nick-carries-context Claude↔GPT
  process: rounds, blind cross-review, Nick as tiebreaker, terse
  final-lock rounds. This produced the review screen, arbitration fix,
  and the V2 constitution.
- NEW skill: spec-driven-dev + drift-guard — everything builds from a
  locked spec; when conversation starts drifting from a lock, the driver
  MUST say explicitly "we are drifting from X, this changes Y — confirm?"
  (ADHD support; course changes allowed but always conscious).
- NEW skill: teaching — explain-like-a-teacher standard for Nick:
  connect every piece of work to how it affects the models and product
  (e.g., last night's confusion: "we trained a model and plugged the
  file into the geometry script" should have been taught up front).

## 3. Togal teardown (blind protocol)
- GPT's analysis already exists (do NOT show Fable first).
- Give Fable transcript+timestamps only → Fable requests screenshots →
  produces independent analysis → THEN cross-exchange files, converge.
- Outputs: what to implement, what to do differently, gaps where we can
  out-flooring them, anything that changes current data engineering NOW.

## 4. Pilot + amendments
Run first 2-3 of the pilot 10 through the thin V2 build; fold
clarifications; amend SCHEMA_V2 as reality teaches.

## 5. THE MAIN EVENT: ML architecture deep work (Fable-critical)
- Define the full model portfolio + how scripts connect: is takeoff.py
  the right shape (one orchestrator calling per-model components) or
  split into per-stage scripts each pairing with its model? Design the
  target architecture explicitly.
- For EACH model: inputs, outputs, training data source (which confirmed
  claims), eval harness, promotion gate.
- HONEST DATA-SUFFICIENCY CALLS (Nick's explicit demand): no bias toward
  what we already have — if a model needs 300 confirmed schedules and we
  have 50, SAY SO before we build, with the acquisition path and cost.
  Set ourselves up to succeed, not to discover shortfalls after weeks.
- Consultation rounds with GPT on the ML plan (same loop), then write it
  as the successor-proof ML roadmap.
- Design implementation (screens→code) deliberately LEFT for Opus — easy
  with locked specs + images; ML judgment is what leaves with Fable.

## Standing notes
- Nick's usage rhythm: 5h windows; plan heavy Fable work at window starts.
- Nick runs effort low for routine loops, high for design/judgment turns.

## 5b. Demo-data requirement analysis (added 2026-07-11)
Scheduled Fable+GPT consultation: how many buildings/plans do we
REALISTICALLY need per model for a market-credible demo vs Togal?
- Togal trained on millions of generic plans pre-LLM-era; we have: free
  CAD-layer labels, LLM-assisted labeling, ONE trade (flooring), and the
  correction flywheel. Quantify how far "sharper, narrower" actually
  goes vs raw scale — the learning-curve question, answered with
  numbers per model (boundary, table-parser, page classifier, viewport).
- Output: per-model data targets + acquisition path + honest "not
  enough yet" flags (Nick's no-bias rule). Defines when demo is credible.
