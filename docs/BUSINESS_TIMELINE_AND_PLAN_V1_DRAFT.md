# Timeline to pitchable + business plan — v1 DRAFT

Written 2026-07-18 (Claude Fable). DRAFT for founder + Codex review — the
numbers here are reasoned estimates from first principles, not promises.
Assumes current working pattern (founder part-time, AI-driven builds,
usage-window constraints) and the locked process as the engine.

## Part 1 — First-principles timeline to "pitchable"

### What "pitchable to a few companies" minimally means

A live demo where a flooring contractor watches THEIR OWN plan set (or one
like theirs) travel: upload → pages → scale proof → surfaces measured to
the inch with proof images → human confirm → square footages by material →
export. Plus honest quality stats from 3+ completed buildings. NOT
required: our own trained model (rented AI + measurement is the engine;
the model is a cost/speed upgrade on the roadmap slide — Codex concurs).

### The math from where we stand (2026-07-18)

| Ingredient | Status | Remaining effort |
|---|---|---|
| Locked process + measuring gate | DONE | — |
| Building 1 measured (Baronne) | DONE, queue pending founder | 1 founder session (~1 hr) |
| Buildings 2-3 (bank, Calhoun) through gate | drafts done; gate is scripted | ~2 machine days + 2 founder sessions |
| Repair loop on flagged edges | scripts exist; needs the loop run | ~2-3 machine days interleaved |
| S10 estimating stub (materials × surfaces → takeoff export) | not built; conventional software | ~3-5 build days |
| Workbench → demo-grade UI pass (one design round, founder-approved) | functional slice exists | ~2-4 build days |
| Quality stats packet (edge-acceptance, deviation, coverage per building) | data exists; assembly trivial | ~1 day |

**Estimate: pitch-ready in ~3-5 weeks calendar** at the current cadence
(the long pole is founder sessions + usage windows, not build capacity).
Aggressive-but-possible: 2 weeks if founder does 4-5 review sessions and
we run machine work nightly.

**Trained geometry model v1: ~4-8 weeks** — gated by eligible surfaces
(need ~150 across 2+ projects; expect ~60-90 from the first three
buildings → 2-3 more buildings through the line), then a ~$5-20 training
bakeoff. Deliberately AFTER first pitches; it strengthens follow-ups.

### Biggest schedule risks (named, honest)

1. Founder review throughput (the only irreplaceable resource).
2. Scanned plan sets (no vectors → reviewer-drawn references; slower path
   is designed but unexercised).
3. A new building class breaking an assumption (mitigated: pick diverse
   buildings 4-6 deliberately).

## Part 2 — Business plan sketch

### Positioning

**"Measured takeoffs with receipts, for commercial flooring."** Not
"AI magic" — every number traceable to a proof image and a confirmed wall
line. The wedge vs. Togal/Kreo (GC-oriented, whole-building, trust-us AI):
we are trade-specific (flooring first), evidence-first, and human-in-loop
by design — a sub can hand our takeoff packet to a GC and defend it.

### ICP (first customers)

Commercial flooring subcontractors bidding from GC invitations: estimating
teams of 1-5, doing 5-40 takeoffs/month, each takeoff 2-8 manual hours.
Pain: bid volume is win volume; takeoff hours cap bid volume.

### Offer + pricing (v1 hypotheses to test in pilots)

- Design-partner phase: free/cheap for 3-5 subs in exchange for plan sets,
  feedback, and case-study rights. THEIR plan sets also feed the data moat.
- Paid v1: per-seat SaaS $300-500/mo OR per-project credits (~$30-75 per
  takeoff) — test both; credits likely convert easier at small shops.
- Enterprise (later): multi-seat + API + priority turnaround.

### Goals ladder (calendar from pitch day)

- +30 days: 3-5 design partners actively submitting plan sets.
- +90 days: 8-12 paying seats/accounts; first defensible case study
  ("took a 6-hour takeoff to 40 minutes, GC accepted the packet").
- +6 months: $8-15k MRR, 100% logo retention among actives, eligible-data
  counter in the thousands of surfaces (the compounding asset).

### Valuation framing (honest, not hype)

- Value drivers in order: (1) the verified-geometry data moat — nobody
  else has per-edge human-confirmed floor-plan truth with provenance; (2)
  a working evidence-first product in a real trade; (3) revenue.
- Pre-seed reality for a solo founder with working vertical AI + early
  design partners: raises commonly land $500k-1.5M on $5-10M caps. With
  early revenue + case studies, seed conversations ($1.5-3M on $12-20M)
  become plausible. These are market-typical ranges, not predictions.
- Bootstrap path is genuinely viable given near-zero COGS until model
  training scales — fundraise for speed, not survival. Decision point
  belongs AFTER first paying customers, when leverage is highest.

### The moat, stated once

Every customer project that flows through the human gate adds verified
surfaces nobody else has. The product gets faster/cheaper (models replace
rented AI) while the dataset gets deeper — classic data flywheel, but with
provenance strong enough to defend in a bid dispute. That is the asset a
buyer or investor is actually pricing.

## Review asks

- Founder: gut-check pricing, ICP, and the goals ladder against trade
  reality; mark what feels wrong.
- Codex: attack the timeline math and the valuation framing; name missing
  risks.
