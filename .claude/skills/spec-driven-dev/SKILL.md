---
name: spec-driven-dev
description: Everything builds from a locked spec; when conversation drifts from a lock the driver MUST call it out explicitly ("we are drifting from X, this changes Y — confirm?"). ADHD support — course changes allowed, always conscious. Read before any build or design conversation. Written 2026-07-11 (Fable).
---

# Spec-driven development + drift guard

## The locks (what counts as a spec)
- **SCHEMA_V2.md** — the constitution. Amended only via version bump
  after consultation/clarification, never by drive-by edits.
- **design_specs/*_APPROVED.png** — approved images ARE the UI spec for
  every build pass. "Thin" = unpolished implementation OF the approved
  layout, never a different layout (hard rule, design-loop skill).
- **Skills** — process locks. **keep_policy / display_policy** —
  versioned config, never relabeling.
- Locked decisions inside docs ("LOCKED", version headers, STATE.md
  decisions Nick signed off).

## The drift guard (the point of this skill)
Nick has ADHD; conversations wander productively — but silent drift from
a lock burns him. THE RULE: the moment the current direction contradicts
or reshapes a locked artifact, STOP and say explicitly:

> "We are drifting from [lock X]. This changes [Y]. Confirm we're
> changing course, or should we park this?"

Then either (a) he confirms → amend the lock properly (version bump,
note in the clarifications log) and continue, or (b) park it as a
backlog line. Never just build the drifted thing. Course changes are
ALLOWED — unconscious ones are not.

## Build protocol
1. Every build prompt cites its spec (approved image path + SCHEMA_V2
   section). No spec → write one or get the lock first.
2. Builder agents get the spec, not a paraphrase.
3. Driver reviews output AGAINST THE SPEC before Nick sees it.
4. Reality teaching us the spec is wrong → that's a drift callout too,
   in reverse: name it, amend the lock, then build.
