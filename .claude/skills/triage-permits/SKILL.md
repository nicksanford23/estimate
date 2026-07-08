---
name: triage-permits
description: Sort permits into SF-pipeline tiers (GOLD/TRAIN/TRUTH/FLATTENED/DISMISS) using a cheap mechanical scan + agentic confirmation, and produce Model-1 page labels as a byproduct. Read when deciding which permits to invest in for square-footage work.
---

# Triaging permits for the square-footage pipeline

You decide, per permit, **what the product should do with it** — not "does
geometry solve every room." The output is a **tier** that routes the permit to
the right use, plus (as a byproduct of the same pass) Model-1 page labels.

Core principle: **auto-triage everything cheaply; hand-invest only in the tiers
worth it.** Most permits get scanned and parked, never hand-worked.

## The tiers (what each is FOR)

| tier | has | action |
|---|---|---|
| **GOLD** | wall CENTERLINE layers **on the floor plan** + a room-finish schedule with per-room area, rooms aligned | full end-to-end validation; rare, precious |
| **TRAIN** | wall layers on a floor plan (centerlines, not hatch) | free training data for the wall-segmentation model (flat render = input, wall layer = label) |
| **TRUTH** | a room-finish schedule with per-room area (+material) | answer key to grade geometry / the model — flattened is fine |
| **FLATTENED** | floor plans, no usable layers, no per-room SF | PARK — the future ML target, not worth hand-work now |
| **DISMISS** | no floor plans / no flooring scope (generator, site-only, demo-only, minimal-finish) | mark and move on |

**Key relaxation:** GOLD (both signals, aligned) is rare. You do NOT need it.
TRAIN-sources (layers) and TRUTH-sources (schedules) are **separate piles** —
layers teach the model on one set, schedules grade it on another. Collect each
independently; GOLD is a bonus.

## The per-permit pipeline (mechanical vs AGENTIC)

- **A. Metadata gate — MECHANICAL.** description + permit_class + code + sqft +
  doc list. Kill obvious non-flooring scope. NEWC/tenant-buildout/reno rank up.
- **B. Doc-selection — AGENTIC.** An agent reads the (messy) `documents.name`
  list + description and picks which doc(s) to download: the complete
  architectural set, plus any SEPARATE finish-schedule/spec doc. Names lie
  ("HDLC…Drawings" vs "Stamped and Approved Plans") — this needs judgment.
- **C. Download** the chosen doc(s), **D. render** (existing scripts).
- **D2. Signal scan — MECHANICAL (`scripts/triage.py`).** Per page: wall-
  centerline segs (layer-classed), floor-plan density, finish-schedule TEXT,
  candidate per-room-SF. Emits a **provisional** tier + the candidate schedule
  pages + candidate wall pages. NOTHING here is trusted as final.
- **E. Confirm + label — AGENTIC.**
  - `schedule-reader` (Sonnet vision) reads each candidate schedule page →
    confirms it is a real room-finish table with area and extracts
    room→(name, floor, base, area). This REPLACES regex SF parsing, which
    over-fires on occupant-load callouts and stray "N SF" annotations.
  - `page-labeler` agents label the plan-set pages (blind, per label-pages
    skill) → Model-1 data (keep + non-keep) AND flags the flooring pages.
  - For GOLD/TRAIN, confirm the wall segs are centerlines on a FLOOR PLAN
    (room-label density; not a legend/hatch/toilet-partition layer).
  - `label-adjudicator` (Opus) only on tier disputes.
- **F. Record** the confirmed tier + evidence to `data/triage/results.jsonl`
  (OUR file — never write the shared read-only permits/documents tables).

## Hard rules (do not bend)

- **Never trust a mechanical GOLD/TRUTH.** The scanner's SF is a CANDIDATE only;
  a `schedule-reader` (vision) must confirm it is a real per-room area table.
  (Verified failure: 23-05848's "9-room SF" was occupant-load noise; 24-22310's
  "layers" were toilet-partition hatch. The scan flags, the agent confirms.)
- **Schedule reading is VISION, not regex.** Regex cannot tell a room-finish
  table from egress callouts on a plan.
- **Layers must be CENTERLINES on the floor plan** — same page as the rooms,
  not a demo/legend/other sheet. Permit-level "has a wall layer somewhere" is
  not enough (verified: 16-17098/18-13316 layers were on non-floor-plan sheets).
- **Page labels are append-only** (label-pages rules). Corrections = new rows.
- **Don't trust sparse labels to judge flooring content** — big docs are
  under-labeled (8/109 seen). Judge by scanning the actual pages.
- **Store triage in `data/triage/`, not the shared tables.**

## Worker routing

- `schedule-reader` (Sonnet, vision): confirm + extract finish schedules.
- `page-labeler` / `label-reviewer` (Sonnet): page labels (see label-pages).
- `label-adjudicator` (Opus): tier disputes / hard confirmations only.
- Scripts (`triage.py`): all mechanical scanning.
- You (orchestrator): doc-selection judgment, spawn the agents, read results,
  set the final tier. Never hand-page a permit yourself.

## Storage schema (`data/triage/results.jsonl`, one line per permit)

```
{permit, tier, provisional_tier, floor_plan_pages:[...], wall_page:{page,segs,layers},
 schedule:{page, rooms:{num:{name,floor,base,area}}, total_sf} | null,
 model1_labeled: bool, notes, confirmed_by}
```

## Output of a triage run

A ranked worklist: the GOLD/TRAIN/TRUTH permits (hand-invest), and the
FLATTENED/DISMISS counts (parked). "Which permit next" becomes a query, not a
hand-search.
