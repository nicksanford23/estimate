# Implementation Handoff

## Current Context
- Branch: `impl-plan-codex`.
- This is a documentation-only handoff. Do not change runtime code from this
  file alone.
- Codex-owned work stays under `codex_work/` unless explicitly promoted later.
  That includes exploratory scripts, probe outputs, notes, and scratch reports.
  Do not create new Codex probe scripts under repo-level `scripts/` or source
  modules under `src/estimate/` during this branch's exploration phase.
- The active database direction is Neon Postgres, schema `estimate.*`.
  `data/estimate.db` is legacy/read-only context unless someone explicitly
  assigns a migration or delta-copy task.
- Existing docs still contain Model 1 / v1 language. Treat that work as useful
  background, not the next implementation target.

## Decision
Park Model 1 for now. Keep it as a conservative page-triage utility that can
over-keep pages and reduce obvious junk. Do not spend time polishing a Model 1
demo, tuning presentation, or chasing fancy classifier work until the next
pipeline probes exist.

The implementation direction is now: find enough pages, then group them, scale
them, and only then inspect geometry feasibility.

## Immediate Sequence
1. Stage 2: grouping baseline and evaluator.
2. Stage 3: scale probe.
3. Stage 4: geometry probe only.

Do these in order. Stage 4 should stay a feasibility probe until Stage 2 and
Stage 3 have measured outputs.

## Codex-Only File Layout
- `codex_work/scripts/` - exploratory probe scripts.
- `codex_work/outputs/` - generated JSONL/CSV/Markdown probe outputs.
- `codex_work/notes/` - additional scratch analysis.

Suggested probe names:
- `codex_work/scripts/probe_grouping.py`
- `codex_work/scripts/probe_scale.py`
- `codex_work/scripts/probe_geometry.py`

## First-Pass Definitions of Done

### Stage 2: Group Pages Into Areas/Floors
- A deterministic baseline groups relevant pages from the same permit/set into
  floor or area packets using sheet number, sheet title, page text, and simple
  rules.
- An evaluator exists and reports page-to-group accuracy on held-out/eval
  packets, plus packet-level misses that are easy to inspect.
- The run has stable inputs and can be repeated without reshuffling eval data.
- The output names the common failure modes, especially ambiguous sheet titles,
  duplicate revisions, mixed buildings, and missing/weak text.

### Stage 3: Establish Scale Per Plan Page
- A probe parses common scale notes from page text, such as architectural
  scale strings, into a usable PDF-units-to-feet conversion.
- The probe cross-checks parsed scale against at least one printed dimension
  where available and flags mismatches instead of silently trusting the parse.
- Results are reported on a small, explicit set of vector floor-plan pages with
  denominators: parsed, verified, failed, and no-scale-found.
- No ML is required for the first pass.

### Stage 4: Geometry Probe Only
- Run `fitz`/PDF drawing extraction on a small sample of labeled floor-plan
  pages from original PDFs, not rendered PNGs.
- Report whether walls appear as clean vector linework, flattened drawings, or
  mixed/noisy geometry.
- Include a few inspectable examples with counts of drawings, candidate lines,
  and obvious blockers such as xrefs, heavy hatch, or rasterized sheets.
- Stop at the feasibility verdict. Do not build polygonization, wall ML, or UI
  flows in this pass.

## Risks
- Cross-permit generalization is still weak; avoid declaring success from one
  large or familiar permit.
- Eval stability matters. Do not revive split logic that changes membership as
  more permits are labeled.
- Text coverage and OCR/vector text quality will vary by document.
- Duplicate revisions and whale permits can distort metrics if not capped or
  evaluated deliberately.
- Stage 4 may prove many PDFs are flattened or too noisy for a vector-first
  geometry route.

## Non-Goals
- No SQLite-first work.
- No Model 1 demo polish.
- No new fancy classifier, fine-tuned ViT, or segmentation model yet.
- No end-to-end estimate UI.
- No room polygonization before the Stage 4 feasibility readout.
- No production claims without evaluator outputs and clear denominators.

## Notes For Claude
- Start with Stage 2 and Stage 3 probes. They are the next implementation
  targets.
- Do not begin fancy model work until Stage 2 grouping and Stage 3 scale probes
  exist and have measured results.
- Keep Model 1 conservative: it is page triage, not the product.
- If a task mentions SQLite, verify whether it is truly a legacy delta-copy
  task before touching it. Default active storage is Neon Postgres.
