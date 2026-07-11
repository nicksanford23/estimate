# Codex Review - SF Triage Process

**Date:** 2026-07-08  
**Reviewed file:** `SF_TRIAGE_PROCESS_REVIEW.md`  
**Related files checked:** `.claude/skills/triage-permits/SKILL.md`,
`.claude/agents/schedule-reader.md`, `scripts/triage.py`

## Executive Summary

The direction is good. I would keep the core split:

```text
vision reads
geometry measures
ML finds walls
humans review uncertain rooms
```

The biggest thing to change is not the overall plan. It is the validation
discipline and the way the triage output is recorded. The current process is
right conceptually, but a few claims are too strong, and `scripts/triage.py`
still has implementation gaps that could make the tiers look more trustworthy
than they are.

The plan should become more conservative before external review:

- fewer "exact" claims,
- stricter definitions for `GOLD` and `TRUTH`,
- durable append-only triage output,
- explicit scope/revision alignment checks,
- clear failure-mode labels that become future training data.

## What I Like And Would Keep

### 1. The Core Division Of Labor

Keep this:

```text
vision reads text/tables/dimensions
geometry computes area
ML classifies wall/finish pixels or linework
human confirms low-confidence output
```

That is the right architecture. Vision models should not be treated as rulers.
They are useful for reading schedule rows, room labels, dimensions, and human
evidence. The actual quantity should come from geometry once scale and boundaries
are known.

### 2. TRAIN And TRUTH As Separate Piles

This is the most important strategic fix in the document.

`GOLD` permits, where the same aligned floor plan has both usable wall layers and
per-room SF truth, are rare. Requiring every useful permit to be GOLD would stall
the project.

Keep this separation:

| Pile | What It Gives Us |
|---|---|
| TRAIN | wall/door/finish masks from layered PDFs |
| TRUTH | per-room material/SF answer keys from schedules |
| GOLD | rare full validation cases |

This is sound. The model can learn walls from one set of permits and be graded on
another, as long as the held-out split is by permit and the grading set has real
room-level truth.

### 3. Mechanical Scan First, Agent Confirmation Second

The A-F triage pipeline is a good operating model:

```text
metadata gate
doc selection
download/render
mechanical signal scan
agent confirmation
record tier/evidence
```

This prevents wasting agent time on every document while still avoiding the bad
failure mode where regex promotes junk into `TRUTH`.

### 4. Schedule-Reader As The TRUTH Gate

Keep `schedule-reader`. The occupant-load false positive is exactly why regex
cannot be the gate for `TRUTH`.

The correct rule is:

```text
regex can nominate schedule pages
vision must confirm schedule pages
```

### 5. The Per-Room Product Action State Machine

This is the product framing we want:

```text
auto_quantity
open_zone_split
geometry_review
vision_correct_or_redraw
scale_review
material_review
no_geometry
```

That is better than asking whether every room became a perfect polygon. The app
needs to decide what action to take next, not pretend all uncertainty is the same
kind of failure.

## What I Do Not Like / Main Risks

### 1. "Geometry Is EXACT" Is Too Strong

The document says CAD-layer geometry is exact when the room closes. That is too
strong for external review.

Better wording:

```text
CAD-layer geometry can be accurate when the correct boundary closes and
scale/scope are verified.
```

Why: even with good layers, we can still be wrong because of scope mismatch,
finish boundary vs wall boundary, missing glass/storefront semantics, wrong
scale, wrong page, or wrong revision.

### 2. TRUTH Is Under-Specified

Right now `TRUTH` means there is a per-room SF finish schedule. That is not quite
enough.

`TRUTH` should require:

- real room-finish or room schedule table,
- area column or clear room-level SF values,
- room numbers/names that map to the floor plan,
- same floor/area/scope,
- compatible revision/date,
- enough rows to grade more than a trivial fragment.

Otherwise we can have a real schedule but still grade the wrong plan.

### 3. GOLD Needs Stricter Alignment Checks

`GOLD` should not just be:

```text
wall layers + per-room SF schedule
```

It should be:

```text
wall centerline layers on the same floor plan
plus per-room SF schedule
plus room-number alignment
plus same scope/floor/revision
```

Without that, a permit can look GOLD while actually mixing different pages,
phases, revisions, or floors.

### 4. The Triage Script Overwrites Results

`scripts/triage.py` writes `data/triage/results.jsonl` with `"w"`, so each run
can overwrite previous triage records.

That conflicts with the append-only data-factory principle.

Change this to either:

```text
append with run_id/timestamp
```

or:

```text
write data/triage/runs/<run_id>.jsonl
and maintain a latest pointer/report
```

### 5. Floor Plan Pages Lose Doc Identity

The script returns only page indexes for `floor_plan_pages`. If a permit has
multiple documents, page `3` is ambiguous.

Use:

```json
{"doc_id": 1494156, "page_index": 3}
```

everywhere.

### 6. Append-Only Labels Need Resolution Logic

The triage script left-joins page labels. Since labels are append-only, a page can
have first-pass, review, and adjudicated rows.

Before triage trusts category labels, it needs a resolved-label view:

```text
adjudicate > review > first-pass
or latest trusted source by priority
```

Otherwise old labels can duplicate pages or conflict with newer corrections.

### 7. "Floor-Plan Density" Is Claimed But Not Really Implemented

The review doc says `triage.py` scans floor-plan density. The current script
mostly uses:

- existing labels,
- wall segment count,
- schedule regex,
- per-room SF regex candidate count.

Either add real floor-plan density features or remove that claim.

### 8. Proxy Wording Is Risky

The acquisition section mentions rotating proxies. Even with good intent, that
can read like bypassing site limits.

For an external review, I would replace it with:

```text
Use a rate-limited, resumable crawler; pursue bulk access/export if possible;
stop on 429/CAPTCHA and keep request logs.
```

## What I Would Change

### 1. Rename `FLATTENED`

`FLATTENED` describes the PDF condition, not the product use.

Better names:

- `MODEL_TARGET`
- `FUTURE_ML_TARGET`
- `UNSOLVED_FLAT_PLAN`

Recommended:

```text
MODEL_TARGET
```

### 2. Split TRUTH Into Two States

Use:

| Tier | Meaning |
|---|---|
| `TRUTH_AREA` | room/material schedule includes per-room SF |
| `MATERIAL_ONLY` | finish schedule exists but no area column |

`MATERIAL_ONLY` is still valuable. It can validate material assignment, but not
geometry accuracy.

### 3. Add `HAND_CALIBRATION`

We need a small human-measured set no matter what.

Recommended:

```text
5-10 permits or 50-100 rooms
manually checked for scale, room boundary, material, and SF
```

This is not for training volume. It is for calibration and sanity-checking claims.

### 4. Add A Validation Discipline Section

Before saying anything about accuracy, require:

- held-out permits only,
- room-level area error,
- material-level quantity error,
- total net SF vs gross sanity,
- count of auto-accepted vs reviewed vs redrawn,
- separate reporting for schedule truth vs dimension agreement,
- no mixing of bank-style dimension validation with true SF schedule validation.

Suggested rule:

```text
No accuracy claim unless every number has a named ground-truth source.
```

### 5. Add A Download Policy

The repo has tens of thousands of undownloaded docs. Bulk download is the wrong
move.

Recommended policy:

```text
reviewed queue -> download 25-50 docs -> render -> triage -> choose permits
```

Never download huge raw filename-regex candidates directly unless they are
sampled or reviewed.

### 6. Add Failure-Mode Taxonomy

Every non-green room should log a failure mode.

Recommended starting taxonomy:

| Failure Mode | Likely Fix |
|---|---|
| `missed_wall` | wall model/rule |
| `bad_wall_classification` | wall model |
| `door_gap_bad_close` | geometry close rule |
| `open_zone` | finish-boundary model or human split |
| `storefront_glass` | storefront/door semantics |
| `service_core_corridor` | zoning/confidence classifier |
| `scale_mismatch` | scale validator |
| `schedule_scope_mismatch` | schedule/page grouping |
| `material_only_no_area` | material join only |
| `no_room_labels` | OCR/labeling fallback |
| `legend_box_false_room` | confidence/filter rule |

These labels are what later reduce agentic work.

## What I Would Delete Or Soften

### Delete / Rewrite The Proxy Line

Do not put proxy language in an external strategy doc. It distracts from the real
technical plan and creates avoidable risk.

### Soften "Never Hand-Page A Permit Yourself"

The skill says the orchestrator should never hand-page a permit. That is too
absolute.

Better:

```text
Do not manually label at scale. Manual inspection is allowed for calibration,
debugging, and adjudication examples.
```

### Soften Exactness And Runtime Coverage Claims

Avoid:

```text
exact
most files
full automation
```

Prefer:

```text
validated on clean closures
expected to improve coverage
assisted takeoff
```

## What Confused Me

### 1. "Read-Only Neon" Versus "We Write Our Own Tables"

The doc says Neon is read-only for us, then says we write `document`, `page`, and
`page_label`.

Clarify:

```text
Source tables are read-only: estimate.permits and estimate.documents.
Pipeline tables are writable: estimate.document, estimate.page, estimate.page_label.
```

### 2. TRUTH Does Not Automatically Mean Geometry Can Be Graded

A real schedule with areas is useful, but only if the rooms align to the plan
being measured.

Add explicit alignment checks.

### 3. The Runtime Pipeline Still Depends On Model 1

The doc says Model 1 is paused, but the runtime pipeline starts with Model 1.

Better:

```text
Model 1 training is paused. Page labels are still being collected through triage,
and runtime page filtering can start rule/agent-assisted until Model 1 is resumed.
```

### 4. Data Numbers Are Snapshots

The doc should label all counts as snapshots with date/source. These numbers
change when inventory scripts run.

## Implementation Fixes I Would Make Soon

### Fix `scripts/triage.py`

Recommended changes:

1. Add `--out` and `--append` options.
2. Add `run_id` and `created_at`.
3. Store `doc_id` with every page reference.
4. Use resolved labels, not raw append-only label rows.
5. Preserve candidate pages even if agent confirmation fails.
6. Include `provisional_reason` and `rejected_reason`.
7. Avoid deleting downloaded PDFs if they are already local/cache-needed, or make
   that behavior explicit.
8. Emit both machine JSONL and a human-readable markdown summary.

### Improve The Triage Result Schema

Suggested schema:

```json
{
  "run_id": "2026-07-08T19-30-00Z",
  "permit": "14-11290-NEWC",
  "provisional_tier": "TRAIN",
  "confirmed_tier": "TRAIN",
  "tier_confidence": "medium",
  "evidence": {
    "floor_plan_pages": [{"doc_id": 1494156, "page_index": 3}],
    "wall_pages": [{"doc_id": 1494156, "page_index": 3, "segs": 4964}],
    "schedule_candidates": []
  },
  "schedule": null,
  "failure_modes": [],
  "needs_agent": ["layer_centerline_confirm"],
  "confirmed_by": "codex",
  "notes": "Layer path useful for training; no per-room SF truth."
}
```

### Add A "Next Permit Selection" Score

For choosing what to inspect next, score permits by:

```text
has floor plans
has finish/material schedule
has per-room area
has layers
has scale
building type diversity
manageable page count
not already overrepresented
```

That turns "what do we do next?" into a query.

## Recommended Revised Tier System

| Tier | Meaning | Use |
|---|---|---|
| `GOLD_ALIGNED` | same-scope floor plan has wall layers and aligned per-room SF schedule | full validation |
| `TRAIN_LAYERED` | floor plan has usable wall centerline layers | wall/door/finish mask training |
| `TRUTH_AREA` | schedule has per-room area and material | geometry/model grading |
| `MATERIAL_ONLY` | schedule has materials but no area | material assignment validation |
| `MODEL_TARGET` | floor plans exist but no layers/truth | future flattened-plan inference |
| `DISMISS` | no useful floor/flooring scope | skip |

This is more explicit than `GOLD/TRAIN/TRUTH/FLATTENED/DISMISS` while preserving
the same idea.

## Suggested Next Operating Plan

1. Download/render a small reviewed batch, not raw candidates.
2. Run mechanical triage.
3. Confirm schedule candidates with vision.
4. Pick 3 permits:
   - one `TRAIN_LAYERED`,
   - one `TRUTH_AREA`,
   - one `MODEL_TARGET`.
5. Run the room/product-action loop on the best candidate.
6. Log every non-green room with failure mode and evidence.
7. After 3-5 permits, decide whether the main bottleneck is:
   - wall detection,
   - finish-boundary splitting,
   - schedule extraction,
   - scale validation,
   - room/schedule alignment,
   - confidence routing.

## My Final Take

The plan is fundamentally good. The main danger is not that the architecture is
wrong. The danger is that weak evidence gets promoted into strong claims.

The right posture is:

```text
Use agents to find and label uncertainty.
Use scripts for repeatable measurement.
Use schedules and hand checks as ground truth.
Use ML only where enough labeled data exists.
Sell assisted takeoff first, not full automation.
```

If we make the tiering and validation stricter, this becomes a credible process
for both short-term demos and long-term model training.
