#!/usr/bin/env node

import { getRepoRoot, retryCodexForRun } from "../src/bridge.mjs";

const artifacts = process.argv.slice(2);
if (!artifacts.length) {
  throw new Error("Usage: retry-codex-run.mjs data/agent_bridge/runs/<run>.json [...]");
}
const root = await getRepoRoot();
const results = await Promise.all(
  artifacts.map((artifactPath) => retryCodexForRun({ root, artifactPath, timeoutSeconds: 600 })),
);
for (const result of results) {
  console.log(JSON.stringify({
    run_id: result.run_id,
    artifact_path: result.artifact_path,
    codex_ok: result.codex.ok,
    codex_category: result.codex.response?.category,
    state: result.comparison.state,
    disagreements: result.comparison.disagreement_keys,
  }));
}
