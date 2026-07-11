# Claude Opus Handoff — Two-Building ML Pilot and Agent Bridge

Read `STATE.md`, `SCHEMA_V2.md`, `ML_TWO_BUILDING_PILOT_PLAN.md`, and
`docs/pilot/PAGE_LABEL_RUBRIC_V1.md` first. V2 is authoritative. Trusted
semantic truth remains zero except for fresh binding decisions Nick creates.

## Current MCP bridge

- Repo-local server: `tools/agent-bridge/`.
- Claude registration: `.mcp.json`, host=`claude`, exposes `ask_codex`,
  `consult_both`, `dual_page_label`, and `bridge_status`.
- Codex registration: `.codex/config.toml`, host=`codex`, exposes
  `ask_claude` plus the shared tools.
- `dual_page_label` gives Claude Sonnet and Codex the same rendered image in
  separate temporary read-only workspaces. Neither sees prior labels or peer
  output before committing. Codex label effort is pinned to medium.
- Raw artifacts land in ignored `data/agent_bridge/runs/`. Import with
  `python scripts/import_bridge_run.py <artifact>`; imports are idempotent and
  create machine observations only—never human decisions or eligibility.
- Bridge tests: `cd tools/agent-bridge && npm test` (7/7 at handoff).

## Completed smoke batch

Building A `26-10321-RNVN`, V2 pages 224–228, doc 9058456 pages 0–4.
Fresh label renders live under ignored `data/pilot_smoke/26-10321-RNVN/`.
All five have both vendors imported: 3 exact matches, 1 category disagreement,
1 flag-only disagreement; 40 machine observations, zero human decisions.
See `STATE.md` for exact categories and run history.

## Nick’s requested future architecture — not implemented

Nick has materially more Claude usage than Codex usage. The coordinator must
support asynchronous independent vendor queues, not require both vendors to run
at the same moment:

1. Create a frozen assignment/batch manifest (page id, image hash, rubric,
   extraction, assignment id) for 10/25/etc. pages.
2. Allow `claude-only` execution to get ahead, writing immutable raw Claude
   observations keyed by assignment. Do not expose them to Codex.
3. Allow `codex-only` catch-up hours/days later against the exact same frozen
   bundles. Codex must not see Claude output, decisions, or comparison state.
4. Form comparisons only after both committed outputs exist. Partial status is
   `awaiting_codex` or `awaiting_claude`, never match or truth.
5. Make retries new attempt records and retain failures. Choose the accepted
   machine attempt explicitly without deleting history.
6. Provide resumable worklists: pending-by-vendor, completed-by-vendor,
   comparison-ready, disagreement, audit, and human-confirmed.
7. Preserve current invariants: identical rubric/image hash, Codex medium,
   machine-only imports, quarantine/default-deny, Nick resolves disagreements,
   deterministic agreement audit, and no automatic human truth.
8. Design/spec this with Nick before implementation. Do not launch the
   remaining 37 Building-A pages merely because one vendor can run ahead.

## Immediate UX feedback from Nick

The existing right panel—with Claude/Codex category, confidence, reasoning,
flag differences, category picker, and flags—is useful and must remain visible.
Nick only needed a way to leave an audit and return to the card grid. Current
minimal behavior: the first page opens as before; `Back to pages` closes the
panel without saving; clicking any card reopens its full details. Do not replace
this with a separate comparison page or strip information from the panel.

## Next human step

Nick reviews the five smoke cards, resolves both disagreements, and audits the
amber match(es). Do not run the remaining 37 pages until he confirms the smoke
interaction and the asynchronous queue design direction.
