# Codex Status And Next Steps

Date: 2026-07-05

This note is a handoff summary of what Codex has done so far, what the current data shape looks like, and what I think should happen next.

## Current Direction

The practical goal is to build a better estimating dataset by first finding permits with good architectural/primary plan sets, downloading those intentionally, then letting Claude label pages from those permits.

I agree with the latest direction: do cheap discovery first, using permit/document metadata and filenames. Do not spend agent time or rendering time until we have a candidate list that is likely clean.

## What Has Been Done

### 1. Separate Codex workspace

All Codex scripts, notes, and outputs are being kept under:

- `codex_work/`

This is meant to avoid mixing Codex work with Claude's files and the rest of the repo.

### 2. Primary plan pilot wave

Codex previously used agent review to identify a first wave of good primary plan documents.

Final selected queue:

- `codex_work/outputs/download_queue_primary_plan_full.csv`

Downloaded and rendered:

- 49 permits
- 67 PDFs
- 1,864 rendered pages
- 1,701 pages with vector text

Run logs:

- `codex_work/outputs/targeted_download_run.csv`
- `codex_work/outputs/targeted_render_run.csv`

Important point: this was not only pure architectural plans. It was mostly primary plan documents: architectural, permit/construction document sets, stamped plan sets, and some interior/finish-oriented docs.

### 3. Labeling thoughts added

A Claude-facing labeling addendum was created here:

- `codex_work/notes/primary_plan_labeling_addendum.md`

Main idea: for this next dataset, page labels should preserve more evidence, not just a category. The labels should capture sheet title, visible evidence, confidence, and whether the page is actually useful for estimating finishes.

### 4. Cheap discovery started

A deterministic no-agent queue script was created:

- `codex_work/scripts/build_low_token_arch_queue.py`

It produced:

- `codex_work/outputs/low_token_arch_queue_150.csv`
- `codex_work/outputs/low_token_arch_queue_150.md`

That first version found 150 candidate docs, but the filter was too loose. It included useful plans, but also leaked in structural, mechanical, riser, state fire, certificate/release, response-letter, and exterior-only items.

After that, a stricter cheap metadata pass was run as an exploration step. It produced:

- `codex_work/outputs/low_token_arch_options_strict.csv`
- `codex_work/outputs/low_token_arch_options_review.csv`
- `codex_work/outputs/low_token_arch_options_summary.md`

That pass found:

- 341 strict-looking options across 341 permits
- 142 review options across 142 permits
- 49 already-completed primary-wave permits excluded

But the strict list still has some false positives. Examples include mechanical permit sets, response letters, state fire releases, certificates, structural-only sets, and exterior-only work.

## My Current Read

We do have enough raw permit/document metadata to keep moving. We do not yet have enough clean downloaded/labeled diversity for a good estimating model.

The earlier 49-permit / 67-PDF wave is useful, but it is still a pilot. The next step should be to add more permits deliberately, not just bulk download every PDF attached to a permit.

The biggest improvement is document-level triage before download:

- First identify likely architectural/primary plan docs from filenames and permit descriptions.
- Download only one or a few likely useful PDFs per permit.
- Render those.
- Label them.
- Then go back to the same permits and inspect their other documents to decide what supporting docs are worth adding.

This avoids wasting time on receipts, application forms, letters, review comments, trade-only sheets, and unrelated admin PDFs.

## What I Would Do Next

### Step 1: Tighten the cheap filter

Create or patch a repeatable script under `codex_work/scripts/` that outputs two buckets:

- `ready_to_sample`: strong architectural / primary plan candidates
- `needs_review`: mixed or ambiguous candidates

The filter should hard reject document names containing obvious junk signals:

- application
- receipt
- invoice
- fee
- email
- letter
- response
- review comments
- certificate
- release
- inspection
- report
- contract
- state fire
- fire marshal
- backflow
- comcheck
- riser
- shop drawing
- mechanical
- electrical
- plumbing
- MEP
- HVAC
- sprinkler
- fire alarm
- civil
- survey
- site plan
- structural
- foundation
- framing
- roof-only
- sign
- solar
- photo

The strict bucket should require strong positive signals like:

- architectural
- architecture
- arch drawings
- stamped architectural set
- construction documents
- CD set
- permit set
- approved plans
- RCC stamped
- HDLC/RCC stamped
- floor plan
- interior design
- finish plan
- finish schedule

I would not download the current raw 341 strict options yet. It is close, but still noisy.

### Step 2: Sample cheaply

After tightening, sample the top 25-30 rows manually from the CSV/summary. If the sample looks clean enough, then download 150.

No agents are needed for this first check unless the sample is ambiguous.

### Step 3: Download 150 more primary plan docs

Once the strict list is clean:

- download about 150 documents
- keep it to one selected PDF per permit at first
- preserve the queue CSV as the source of truth
- log download status

This should quickly increase permit diversity.

### Step 4: Render only the downloaded queue

Render the targeted 150 only, not the whole database.

Expected result if similar to the first wave:

- maybe 4,000-5,000 more pages
- many pages will have vector text
- enough volume for Claude to label a meaningful second wave

### Step 5: Claude labels the rendered set

Claude should label pages from these targeted plan sets with a richer schema.

At minimum, I would keep:

- `category`
- `sheet_title`
- `evidence`
- `confidence`
- `finish_relevance`
- `plan_scope`
- `page_usefulness`

The key thing is to avoid treating every architectural sheet as equally useful. For estimating, finish plans, schedules, enlarged plans, reflected ceiling plans, interior elevations, door/window schedules, and material legends matter more than cover sheets or general code sheets.

### Step 6: Revisit other docs on those same permits

After the architecture/primary plans are labeled, inspect the other documents attached to those same permits.

This is where we decide whether to add:

- finish-specific docs
- interior design packages
- specifications
- addenda
- revised sheets
- trade docs that affect finishes

That is better than downloading all docs upfront.

## My Recommendation

Do not launch more agents yet.

Use cheap deterministic filtering first, get a clean 150-permit candidate queue, then download/render that queue. Once those are rendered, Claude can label. Agents are more useful later for ambiguous cases and quality audit, not for the first metadata pass.

The next concrete Codex task should be:

1. Replace the loose low-token queue script with a stricter options script.
2. Produce `ready_to_sample` and `needs_review` CSVs.
3. Audit the first 25-30 rows for obvious junk.
4. If clean, download the top 150.

