---
name: label-pages
description: Independently classify rendered construction-plan page images under the frozen V2 pilot rubric and emit machine observations only.
---

# Labeling plan-set pages — V2/reset policy

SCHEMA_V2.md and `docs/pilot/PAGE_LABEL_RUBRIC_V1.md` govern. For the
two-building pilot, use only the neutral `dual_page_label` coordinator. Do not
run a labeling wave until the coordinator smoke gate is explicitly opened.

## Hard boundaries

- Inspect the isolated rendered IMAGE. Do not read OCR, filenames, database
  labels, legacy artifacts, prior worker output, or the peer worker output.
- Use the frozen executable rubric in
  `tools/agent-bridge/src/page-label.mjs` (`pilot-page-label-v1`).
- Emit structured worker output only. Agent labels are
  `v2.machine_observation` candidates, never `v2.human_decision` rows.
- Never write `estimate.page_label`, update page status, derive binding truth,
  or modify an old row. The bridge itself writes only a raw run artifact and
  declares `database_writes=false`.
- Exact Claude/Codex agreement is machine cross-verification only. A
  disagreement requires Nick review; an agreement remains audit-eligible.
- Quarantined or unqualified evidence is denied from snapshots by default.

## Worker routing

- Claude page worker: Sonnet, isolated read-only image workspace.
- Codex page worker: configured Codex model, isolated read-only image
  workspace, reasoning effort pinned to `medium` by the bridge.
- Both receive the same image, hash, rubric version, and schema. Neither sees
  the other's result before both commit.

## Output and reporting

The required output is category, eight independent flags, sheet number/title,
confidence, evidence, uncertainty, and `image_inspected=true`. Compare category
and every flag independently. Report run IDs, rubric version, image hash,
vendor/model/reasoning metadata, failures, and per-claim disagreements. Never
report machine agreement as human truth.
