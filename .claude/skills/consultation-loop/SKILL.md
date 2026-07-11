---
name: consultation-loop
description: The Nick-carries-context Claude↔GPT consultation process — rounds, blind cross-review, Nick as tiebreaker, terse final-lock rounds. Use for any big design/architecture decision (produced the V2 constitution, review screen, arbitration fix). Written 2026-07-11 (Fable).
---

# The consultation loop

Nick manually carries context between Claude (driver) and GPT (outside
counsel). No API link — he pastes. This produced SCHEMA_V2 (3+ rounds),
the review screen, and the arbitration fix. Use it for decisions big
enough that one model's blind spots are a real risk.

## The round structure
1. Driver writes a POSITION DOC (design, schema, plan) — self-contained,
   numbered sections, so GPT can attack it without our repo context.
2. Nick pastes it to GPT → GPT critiques/counter-proposes → Nick pastes
   the response back.
3. Driver evaluates PER-COMPONENT on merits (no-context-bias rule:
   adopt what's genuinely better and say so; reject with reasons; never
   soften "wrong" to "interesting"). Produce the amended doc + a
   numbered verdict list (ADOPTED / REJECTED-because / MODIFIED).
4. Repeat. Nick is TIEBREAKER on judgment calls — give him the decision
   framed in plain terms (teaching skill) with a recommendation.

## Blind cross-review variant (for analyses, not designs)
When both models analyze the same artifact (e.g. Togal teardown): each
produces its analysis WITHOUT seeing the other's, THEN cross-exchange
and converge. Prevents anchoring. Never read the other model's take
first if a blind pass is planned.

## Final-lock rounds
Near convergence, switch to TERSE rounds: numbered deltas only, each
round ends with an explicit "LOCKED: … / STILL OPEN: …" list. When open
hits zero, fold into the governing doc with a version bump (SCHEMA_V2
v1.x pattern) and mark it LOCKED with date. Locks are then governed by
the spec-driven-dev skill (drift callouts).

## Rules
- Version every round's artifact (v1.1, v1.2…) — commits are the trail.
- GPT gets no authority by default; neither does the driver's earlier
  position. Components win on merits.
- Log founder questions raised mid-round in the clarifications log
  (V2_CLARIFICATIONS.md pattern); fold at checkpoints.
