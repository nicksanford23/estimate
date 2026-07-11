# Ops UI v1 — "Mission Control" (proposal, 2026-07-10)

*Internal dashboard for Nick + drivers: see the data machine, check the
models, and turn Nick's estimator eye into a scalable human-verification
tool. Lives in the same Next.js app under /ops. Reads the files/tables the
pipeline already writes — no new backend, no schema changes. Build AFTER
usage reset; ~1-2 agent-days.*

## Why
The pipeline's state lives in CSVs, JSONLs, Neon tables, and overlay
images only agents can see. Nick has personally caught two major errors
just by LOOKING (wrong-sheet false-passes, firm duplication). Give that
eye a tool: every screen below is both a visualization AND a check
surface, and every human verdict recorded is a training label.

## Screen A — The Funnel (front page)
Live counts through the pipeline stages, each clickable to its permit list:
  discovered → downloaded → harvested (has wall layers) → gate-passed →
  eyeball-confirmed → roster tiers (TRAIN_LAYERED / TRUTH_AREA / ...)
Sources: estimate.discovered_docs (Neon), download log CSV, layered_plans,
closeability_full, eyeball_verdicts, train_layered_roster, permit_status.
Plus two tickers: discovery %, downloader backlog. (Answers "how's the
machine doing" without asking Fable.)

## Screen B — Permit browser + detail
Table: permit, tier, verdict, firm cluster, metrics, dates. Detail page
per permit: its pages as thumbnails, overlay images (eyeball/probe
renders), verdict + reason history, links to /review/[permit] and the
takeoff guide. (Answers "what do we know about this building.")

## Screen C — Check queue (the killer feature)
The eyeball task as a UI: shows one overlay at a time (UNCLEAR permits,
borderline cases, regate candidates, model-vs-rules disagreements from
dual-engine runs), with CONFIRM / REJECT / UNSURE buttons + a reason
field. Writes append-only to eyeball_verdicts.csv (slice=nick). Keyboard:
y/n/u, arrows. Nick clearing 20 of these with his trade eye = higher
quality than any agent pass, and it's exactly the human-in-the-loop
pattern the product itself will use.

## Screen D — Model report card
Reads the probe artifacts (scoreboard.csv, probe30 results JSONs,
learning_curve, canary results): the three-level exam per model version
side by side (segment PR-AUC / rooms matched / answer-key scorecard vs
rules), learning curve chart, green-precision trend, canary status lights.
One page that answers "is the ML getting better" across probes. (Read the
dataviz skill before building charts.)

## Non-goals (v1)
No auth (it's local/dev), no writes except Screen C's append-only CSV, no
editing pipeline state, no mobile optimization (desktop tool).

## Build notes
Next.js server components reading files directly; Neon via the existing
env; images served from data/ via a small static route (data/ stays
gitignored). Screens A+B first (pure read), C second (the value), D last.
