---
name: triage-permits
description: Sort permits into SF-pipeline tiers (GOLD_ALIGNED / TRAIN_LAYERED / TRUTH_AREA / MATERIAL_ONLY / MODEL_TARGET / DISMISS) using a cheap mechanical scan + agentic confirmation, and produce Model-1 page labels as a byproduct. Read when deciding which permits to invest in for square-footage work.
---

# Triaging permits for the square-footage pipeline

You decide, per permit, **what the product should do with it** — not "does
geometry solve every room." The output is a **tier** that routes the permit to
the right use, plus (as a byproduct of the same pass) Model-1 page labels.

Core principle: **auto-triage everything cheaply; hand-invest only in the tiers
worth it.** Most permits get scanned and parked, never hand-worked.

## The tiers (what each is FOR)

| tier | requires | action |
|---|---|---|
| **GOLD_ALIGNED** | wall CENTERLINE layers on the floor plan that PASS the closeability gate **+** a per-room area schedule **+** room numbers that map to that plan **+** same scope/floor/revision | full end-to-end validation; rare |
| **TRAIN_LAYERED** | wall centerline layers on a floor plan (centerlines, not hatch/demo/legend) that PASS the polygonize-quality/closeability gate (`scripts/scan_closeability.py`) — segment count alone is NOT the test (see below) | training data (flat render = input, layer linework = weak label — QA'd, not gospel) |
| **TRUTH_AREA** | a room-finish/room schedule with a per-room AREA column, rows that map to the plan | grade geometry area — but note it is *area* truth, not final *bid-quantity* truth |
| **MATERIAL_ONLY** | a room-finish schedule with materials but NO area column | validate material assignment only (not geometry) |
| **MODEL_TARGET** | floor plans, no usable layers, no per-room SF | PARK — the future flattened-plan ML target |
| **DISMISS** | no floor plans / no flooring scope | mark and move on |

**Key relaxation:** GOLD_ALIGNED (both signals, aligned) is rare. You do NOT need
it. TRAIN_LAYERED (layers) and TRUTH_AREA (schedules) are **separate piles** —
layers teach the model on one set, schedules grade it on another. Collect each
independently; GOLD is a bonus. (Bid-quantity truth — after exclusions, thresholds,
waste, alternates — comes only from a flooring company, never from a permit.)

**Alignment is not optional for GOLD/TRUTH.** A real schedule can still grade the
WRONG plan if its rooms belong to a different floor/phase/revision. Confirm the
schedule's room numbers appear on the floor plan being measured before trusting it.

**A wall-segment count is necessary but NOT sufficient for TRAIN_LAYERED/
GOLD_ALIGNED (probe 24 finding).** `.3D`-solid wall layers can clear a segment-
count threshold (thousands of tiny fragments) and still fail to polygonize a
single real room, while a clean 2D centerline layer with far fewer segments
closes cleanly. Run the actual snap→polygonize and score the OUTPUT
(`scripts/scan_closeability.py`: room-band polygon count, footprint coverage,
largest-polygon fraction) before calling a permit LAYERED. See
`experiments/probe24_two_permit_takeoff.md`.

## The per-permit pipeline (mechanical vs AGENTIC)

- **A. Metadata gate — MECHANICAL.** description + permit_class + code + sqft +
  doc list. Kill obvious non-flooring scope. NEWC/tenant-buildout/reno rank up.
- **B. Doc-selection — AGENTIC.** An agent reads the (messy) `documents.name`
  list + description and picks which doc(s) to download: the complete
  architectural set, plus any SEPARATE finish-schedule/spec doc. Names lie
  ("HDLC…Drawings" vs "Stamped and Approved Plans") — this needs judgment.
- **C. Download** the chosen doc(s), **D. render** (existing scripts).
- **D2. Signal scan — MECHANICAL (`scripts/triage.py`).** Per page: resolved
  page label (floor_plan/finish_schedule/etc. — one category per page by source
  priority), wall-centerline segment count (layer-classed), finish-schedule TEXT
  match, candidate per-room-SF regex. Emits a **provisional** tier + the
  candidate schedule pages + candidate wall pages. This is signal-based, not a
  floor-plan-density model (there is no density model — `triage.py` says so at
  the top of the file). NOTHING here is trusted as final.
- **D3. Closeability gate — MECHANICAL (`scripts/scan_closeability.py`).** For
  any permit whose provisional tier rests on wall segments, actually run
  snap→polygonize on the wall layer and score the output rather than trusting
  the segment count. A permit that clears the segment threshold but fails to
  polygonize into real rooms is NOT TRAIN_LAYERED (probe 24: `.3D`-solid layers
  pass the count test and still close nothing).
- **E. Confirm + label — AGENTIC.**
  - `schedule-reader` (Sonnet vision) reads each candidate schedule page →
    confirms it is a real room-finish table with area and extracts
    room→(name, floor, base, area). This REPLACES regex SF parsing, which
    over-fires on occupant-load callouts and stray "N SF" annotations.
  - `page-labeler` agents label the plan-set pages (blind, per label-pages
    skill) → Model-1 data (keep + non-keep) AND flags the flooring pages.
  - For GOLD/TRAIN, confirm the wall segs are centerlines on a FLOOR PLAN
    (room-label density; not a legend/hatch/toilet-partition layer) AND that
    D3's closeability gate passed — segment count alone does not confirm TRAIN.
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
- **A wall-segment count is not the LAYERED test — closeability is.** Score the
  actual snap→polygonize output (`scripts/scan_closeability.py`), not just
  `n_segs >= threshold` (verified: 25-33341's `.3D`-solid wall layer clears the
  segment count and still fails to close a single real room — see
  `experiments/probe24_two_permit_takeoff.md`).
- **Page labels are append-only** (label-pages rules). Corrections = new rows.
  Before triage trusts a page category, resolve to ONE label per page by source
  priority: `adjudicate > review > first-pass` (a page can have all three rows).
- **Don't trust sparse labels to judge flooring content** — big docs are
  under-labeled (8/109 seen). Judge by scanning the actual pages.
- **Every page reference carries `{doc_id, page_index}`** — a bare page index is
  ambiguous when a permit has multiple docs.
- **Measurement boundary matters.** Flooring SF is measured to the INSIDE wall
  face; layer/geometry polygons come from wall CENTERLINES → a systematic
  overcount, worse in small rooms. Offset polygons inward by ~half the wall
  thickness before quoting finish area. Layer walls are near-ground-truth for
  *classification*, not automatically the *flooring measurement boundary*.
- **Store triage in `data/triage/` (APPEND-only, run_id per record), not the
  shared tables.** All counts are snapshots — date them.

## Worker routing

- `schedule-reader` (Sonnet, vision): confirm + extract finish schedules.
- `page-labeler` / `label-reviewer` (Sonnet): page labels (see label-pages).
- `label-adjudicator` (Opus): tier disputes / hard confirmations only.
- Scripts (`triage.py`): all mechanical scanning.
- You (orchestrator): doc-selection judgment, spawn the agents, read results,
  set the final tier. Don't manually LABEL at scale — but manual inspection is
  fine (and expected) for calibration, debugging, and adjudication examples.

## Storage schema (`data/triage/results.jsonl`, APPEND-only, one line per run×permit)

```json
{"run_id":"2026-07-08T19-30-00Z","permit":"14-11290-NEWC",
 "provisional_tier":"TRAIN_LAYERED?","confirmed_tier":"TRAIN_LAYERED","tier_confidence":"medium",
 "floor_plan_pages":[{"doc_id":1494156,"page_index":3}],
 "wall_page":{"doc_id":1494156,"page_index":3,"segs":4964,"layers":["09-MTL STUD WALLS"]},
 "schedule":{"doc_id":null,"page":null,"truth_type":"unknown","rooms":[],"total_sf":null},
 "needs_agent":["layer_centerline_on_floorplan_confirm"],"failure_modes":[],
 "confirmed_by":"opus","notes":"snapshot; layer path useful for training; no per-room SF truth"}
```

## Failure-mode taxonomy (log one per non-green room → becomes a training target)

| failure_mode | likely fix |
|---|---|
| `missed_wall` / `bad_wall_classification` | wall/boundary model |
| `door_gap_bad_close` | geometry close rule |
| `open_zone` | finish-boundary model or human split |
| `storefront_glass` | storefront/door semantics |
| `service_core_corridor` | zoning / confidence classifier |
| `scale_mismatch` | scale validator |
| `schedule_scope_mismatch` | schedule↔page grouping/alignment |
| `material_only_no_area` | material join only |
| `no_room_labels` | OCR/labeling fallback |
| `legend_box_false_room` | confidence/filter rule |

## Validation discipline (mandatory — we have over-claimed before)

- Split by permit, never by page. Freeze an eval set before tuning; don't inspect
  eval failures while changing rules.
- **No accuracy claim unless every number names its ground-truth source**
  (schedule SF vs dimension agreement vs hand-measured — never mixed).
- Report by room-type (enclosed / open-zone / restroom-core / corridor /
  rotated-glass) AND by file-type (scanned / vector / layered) — never one global
  number without the failure mix.
- **Primary metric = green precision:** when the system marks a room
  auto/accepted, how often is it actually right? For assisted takeoff that beats
  average SF error. Report accepted-only, accepted+check, and all-attempted
  separately. Keep a small `HAND_CALIBRATION` set (5–10 permits / 50–100 rooms
  hand-measured) as the honest yardstick.

## Download policy (don't bulk-pull)

Reviewed queue → download 25–50 docs → render → triage → choose permits. Never
mass-download raw filename-regex candidates. Acquisition is a rate-limited,
resumable crawler that stops on 429/CAPTCHA and keeps request logs.

## Output of a triage run

A ranked worklist: the GOLD_ALIGNED / TRAIN_LAYERED / TRUTH_AREA permits
(hand-invest), MATERIAL_ONLY (material validation), and the MODEL_TARGET / DISMISS
counts (parked). "Which permit next" becomes a query, not a hand-search.
