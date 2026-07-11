# Estimate Agent Bridge

This repo-local MCP server lets either interactive client ask the other vendor
for an independent response:

- Codex receives `ask_claude`.
- Claude Code receives `ask_codex`.
- Both receive `consult_both` and `dual_page_label`.

The project registrations live in `.codex/config.toml` and `.mcp.json`.
Restart the client after configuration changes. Claude Code asks once whether
to approve the project-scoped MCP server.

## Typical prompts

From Codex:

```text
Use ask_claude to get Claude's independent review of this decision, then show
me both positions without silently merging them.
```

From Claude Code:

```text
Use ask_codex to get Codex's independent review of this decision, then show me
where you agree and disagree.
```

For two independent page labels:

```text
Use dual_page_label on data/path/to/rendered-page.png with page_ref "building/page".
```

`dual_page_label` copies the image into separate temporary workspaces, runs
Claude and Codex concurrently, and reveals neither output to the other before
both finish. It compares the primary category and each canonical flag. The raw
artifact is written to `data/agent_bridge/runs/`, which is gitignored.

For a V2 pilot page, use `page_ref` in the form `v2-page:<id>`. After both
workers finish, import the raw artifact explicitly:

```bash
python scripts/import_bridge_run.py data/agent_bridge/runs/<run-id>.json
```

The importer writes four machine observations per successful vendor and is
idempotent by run/vendor/claim. It creates no human decision or eligibility
approval. Page Review reads only `agent_bridge:claude` and
`agent_bridge:codex` observations; quarantined legacy suggestions remain hidden.

## Truth boundary

The bridge never writes Postgres rows. Agreement is recorded only as
`machine_cross_verified`; it is never human truth. A disagreement requires
human review. Even a complete agreement remains subject to the founder's audit
policy before it can be accepted for training or demo use.

## Development

```bash
cd tools/agent-bridge
npm install
npm test
```

Environment overrides:

- `AGENT_BRIDGE_CLAUDE_BIN`
- `AGENT_BRIDGE_CODEX_BIN`
- `AGENT_BRIDGE_CLAUDE_MODEL` (defaults to `sonnet`)
- `AGENT_BRIDGE_CODEX_MODEL` (defaults to the local Codex configuration)
- `AGENT_BRIDGE_CODEX_LABEL_REASONING_EFFORT` (label worker only; defaults to
  `medium` and is pinned on every invocation)
- `ESTIMATE_REPO_ROOT`
