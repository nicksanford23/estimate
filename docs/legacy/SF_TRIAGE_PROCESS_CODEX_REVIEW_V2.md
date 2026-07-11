# Codex Review - SF Triage Process v2

**Date:** 2026-07-08  
**Reviewed file:** `SF_TRIAGE_PROCESS_REVIEW.md` v2  
**Also checked:** `.claude/skills/triage-permits/SKILL.md`, `scripts/triage.py`

## Bottom Line

This v2 is much stronger than the first version. It fixed the biggest problems:

- softened the "geometry is exact" language,
- split `TRUTH` into better tiers,
- added `GOLD_ALIGNED`,
- made ML vector-first instead of U-Net-only,
- added validation discipline,
- added measurement-boundary risk,
- added small-batch download policy,
- updated `scripts/triage.py` to append with `run_id`, resolved labels, and
  `{doc_id, page_index}` references.

I would use this as the working strategy doc. It is now credible enough to guide
the next batch of downloads/triage. I would still clean up a few mismatches before
external review.

## What Is Now Good

### 1. The Changelog Is Honest

The v2 changelog clearly says what changed and why. That helps because the project
has been revising quickly, and the doc now admits that counts are snapshots.

### 2. The Tier System Is Much Better

The new tiers are the right direction:

```text
GOLD_ALIGNED
TRAIN_LAYERED
TRUTH_AREA
MATERIAL_ONLY
MODEL_TARGET
DISMISS
```

This fixes the old ambiguity around `TRUTH` and `FLATTENED`. It also correctly
states that `TRUTH_AREA` is area truth, not final bid truth.

### 3. Vector-First ML Is The Right Pivot

This is probably the most important v2 improvement.

If most PDFs are still vector linework but just lost layer names, then a
vector/graph segment classifier is the first bet. It is more data-efficient than
raster segmentation and plugs into the existing geometry pipeline more directly.

The right framing is:

```text
vector classifier for vector PDFs
raster segmentation only for true scans
benchmark both, but do not start with raster by default
```

### 4. Validation Discipline Is Now Explicit

The green-precision framing is good. For assisted takeoff, the key question is:

```text
When the system says "this room is safe to auto-quantity," is it actually safe?
```

That matters more than average error across all attempted rooms.

### 5. Measurement Boundary Is Finally First-Class

Calling out centerline vs inside-face is important. Flooring quantity is not
structure quantity. This should stay in the doc.

### 6. `scripts/triage.py` Actually Improved

The script now has:

- append-only output,
- `run_id`,
- `{doc_id, page_index}` page refs,
- resolved-label priority,
- provisional tiers with `?`,
- human-readable run summaries.

That matches the v2 direction much better than the previous script.

## Remaining Issues To Fix

### 1. The Doc Still Mentions "Floor-Plan Density"

The v2 changelog says the unimplemented density claim was dropped, but the doc
still says the mechanical scan uses "floor-plan density" in Section 3.

The skill also still says this.

Current reality in `scripts/triage.py` is closer to:

```text
resolved labels
wall segment count
schedule text
candidate per-room SF regex
```

Fix the wording to avoid promising an unbuilt density model.

### 2. Runtime Pipeline Still Says "Exact" For CAD Layers

The product pipeline still says:

```text
has CAD layers? -> grab wall layer (exact, ~18%)
```

That conflicts with the improved language earlier in the doc. Change it to:

```text
has QA'd CAD layers? -> use wall/door/finish layers as high-confidence boundaries
```

### 3. Runtime Pipeline Still Says "Wall-Segmentation Model"

The ML section correctly changed to vector-first, but the runtime pipeline still
says:

```text
flattened? -> wall-segmentation model
```

Better:

```text
layerless vector PDF -> vector boundary classifier
true scan -> raster segmentation fallback
```

### 4. "Flattened 82%" Is Now Ambiguous

Earlier "flattened" meant "no useful layer names." In v2, we now distinguish:

- layerless vector PDFs,
- true raster scans.

The doc should define that clearly. Otherwise people will think the 82% are
scanned images, which is not what we mean.

Suggested wording:

```text
82% are layerless/flattened-by-layer-name, but most still contain vector linework.
Only a small slice are true raster scans.
```

### 5. Specific Decisions Section Is Stale

Section 7 says resolved items are marked, but the questions are still the old
questions and no visible marks are applied.

I would rewrite Section 7 as actual open questions:

1. How much hand calibration before the meeting?
2. What is the first vector classifier baseline?
3. What is the threshold for green auto-quantity?
4. Do we attempt finish-boundary detection now or leave open zones human-split?
5. Which building types must be represented before any accuracy claim?

### 6. `MATERIAL_ONLY` Needs A Clear Confirmation Rule

The tier exists now, but the pipeline should say exactly how a candidate becomes
`MATERIAL_ONLY`.

Recommended rule:

```text
schedule-reader returns is_schedule=true and has_area_column=false
=> confirmed_tier = MATERIAL_ONLY
```

Right now that is implied, not explicit enough.

### 7. `scripts/triage.py` Resolves Label Source, But Not Same-Source Recency

The script resolves labels by source priority:

```text
adjudicate > review > first-pass
```

Good. But if two labels have the same source for the same page, it keeps whichever
appears first. If the table has timestamps or ids, use the newest/highest id
within the same source priority.

### 8. `confirmed_tier` Is Still Not Written By A Confirmation Step

The script now emits provisional records. Good. But the doc should name the
second step that appends or updates the confirmed record after `schedule-reader`
and layer confirmation.

We need either:

```text
data/triage/results.jsonl contains provisional and confirmed records separately
```

or:

```text
provisional records live in one file; confirmed tier report is another file
```

Right now the schema has `confirmed_tier`, but the operational flow for setting it
is not fully defined.

### 9. Centerline Offset Needs An Implementation Plan

The doc correctly says centerline polygons overcount. The next step is to define
the first practical approximation:

```text
infer wall thickness from parallel wall pairs where available
fallback to standard partition thickness by wall type
report area before/after offset
flag tiny rooms as offset-sensitive
```

Otherwise "inside-face offset" becomes another known issue without a path.

## What I Would Keep Exactly

- The v2 tier names.
- Separate TRAIN and TRUTH piles.
- Vector-first ML framing.
- Green precision as primary product metric.
- HAND_CALIBRATION requirement.
- Download policy: reviewed queue -> 25-50 docs -> render -> triage.
- Failure-mode taxonomy.
- The warning that bid truth still comes from the flooring company.

## What I Would Change Before External Review

1. Remove the remaining "floor-plan density" wording.
2. Replace "exact" in the runtime pipeline.
3. Replace "wall-segmentation model" with "vector boundary classifier / raster
   fallback."
4. Define "flattened" as layerless vector vs true scan.
5. Rewrite Section 7 as current open questions, not old questions.
6. Add the explicit `MATERIAL_ONLY` confirmation rule.
7. Add a paragraph on how provisional triage becomes confirmed triage.

## Recommended Next Move

Use this v2 process to run the next small batch:

```text
download 25-50 reviewed docs
render them
run scripts/triage.py
confirm schedule candidates
pick one TRAIN_LAYERED, one TRUTH_AREA, one MODEL_TARGET
run the room action loop on the best one
```

Do not widen to huge raw candidate downloads yet. The process is now good enough
to drive a controlled batch, and the controlled batch will tell us whether the
new tier system is actually separating useful permits.

## Final Take

v2 is a real improvement. It is no longer just an optimistic ML plan. It is now a
usable operating plan with explicit validation gates.

The remaining work is mostly consistency and operational closure:

```text
make the doc match the script
make provisional-to-confirmed triage explicit
make vector-first language consistent everywhere
start running small batches
```

I would proceed with this plan after the cleanup above.
