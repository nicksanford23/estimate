import assert from "node:assert/strict";
import { chmod, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const SERVER = resolve(HERE, "../src/server.mjs");

const label = {
  category: "floor_plan",
  flags: ["dimensions_visible", "room_labels_visible"],
  sheet_number: "A101",
  sheet_title: "FIRST FLOOR PLAN",
  confidence: 0.9,
  evidence: "Visible rooms, walls, doors, and dimensions.",
  uncertainty: "",
  image_inspected: true,
};

async function fakeCli(directory, name, vendor) {
  const path = join(directory, name);
  const script = `#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
const args = process.argv.slice(2);
if (args.includes("--version")) {
  console.log("${vendor}-fake 1.0");
  process.exit(0);
}
let input = "";
try { input = readFileSync(0, "utf8"); } catch {}
const label = ${JSON.stringify(label)};
if ("${vendor}" === "claude") {
  const structured = args.includes("--json-schema");
  console.log(JSON.stringify({ type: "result", is_error: false, result: structured ? JSON.stringify(label) : "claude:" + input, structured_output: structured ? label : undefined }));
} else {
  const outputFlag = args.includes("--output-last-message") ? "--output-last-message" : "-o";
  const outputIndex = args.indexOf(outputFlag);
  const structured = args.includes("--output-schema");
  if (structured && !args.includes('model_reasoning_effort="medium"')) {
    console.error("Codex label worker reasoning effort was not pinned to medium");
    process.exit(2);
  }
  writeFileSync(args[outputIndex + 1], structured ? JSON.stringify(label) : "codex:" + input);
}
`;
  await writeFile(path, script, "utf8");
  await chmod(path, 0o755);
  return path;
}

async function connect(host, root, claudeBin, codexBin) {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [SERVER, "--host", host],
    stderr: "pipe",
    env: {
      ...process.env,
      ESTIMATE_REPO_ROOT: root,
      AGENT_BRIDGE_CLAUDE_BIN: claudeBin,
      AGENT_BRIDGE_CODEX_BIN: codexBin,
    },
  });
  transport.stderr?.on("data", (chunk) => process.stderr.write(chunk));
  const client = new Client({ name: "agent-bridge-test", version: "1.0.0" });
  await client.connect(transport);
  return { client, transport };
}

function toolText(result) {
  return JSON.parse(result.content.find((item) => item.type === "text").text);
}

test("host-specific tools are exposed in both directions", async () => {
  const root = await mkdtemp(join(tmpdir(), "bridge-mcp-root-"));
  const bins = await mkdtemp(join(tmpdir(), "bridge-mcp-bin-"));
  const claudeBin = await fakeCli(bins, "claude-fake", "claude");
  const codexBin = await fakeCli(bins, "codex-fake", "codex");

  for (const [host, expected, absent] of [
    ["codex", "ask_claude", "ask_codex"],
    ["claude", "ask_codex", "ask_claude"],
  ]) {
    const { client } = await connect(host, root, claudeBin, codexBin);
    try {
      const names = (await client.listTools()).tools.map((tool) => tool.name);
      assert(names.includes(expected));
      assert(!names.includes(absent));
      assert(names.includes("consult_both"));
      assert(names.includes("dual_page_label"));
    } finally {
      await client.close();
    }
  }
});

test("dual_page_label keeps machine outputs separate and writes no truth", async () => {
  const root = await mkdtemp(join(tmpdir(), "bridge-label-root-"));
  const bins = await mkdtemp(join(tmpdir(), "bridge-label-bin-"));
  const claudeBin = await fakeCli(bins, "claude-fake", "claude");
  const codexBin = await fakeCli(bins, "codex-fake", "codex");
  await writeFile(join(root, "page.png"), "fake image bytes");
  const { client } = await connect("codex", root, claudeBin, codexBin);
  try {
    const result = await client.callTool({
      name: "dual_page_label",
      arguments: { image_path: "page.png", page_ref: "test-page", timeout_seconds: 30 },
    });
    const payload = toolText(result);
    assert.equal(payload.outputs.claude.ok, true);
    assert.equal(payload.outputs.codex.ok, true);
    assert.equal(payload.outputs.codex.reasoning_effort, "medium");
    assert.equal(payload.comparison.state, "machine_cross_verified");
    assert.equal(payload.comparison.human_truth, false);
    assert.equal(payload.database_writes, false);
    assert.equal(payload.trusted_semantic_truth, false);
    const saved = JSON.parse(await readFile(join(root, payload.artifact_path), "utf8"));
    assert.equal(saved.run_id, payload.run_id);
  } finally {
    await client.close();
  }
});
