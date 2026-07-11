#!/usr/bin/env node

import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const SERVER = resolve(HERE, "../src/server.mjs");
const ROOT = process.env.ESTIMATE_REPO_ROOT || resolve(HERE, "../../..");

function parseToolResult(result) {
  const text = result.content.find((item) => item.type === "text")?.text;
  if (!text) throw new Error("MCP tool returned no text result");
  if (result.isError) throw new Error(text);
  return JSON.parse(text);
}

async function callOppositeVendor(host, tool, marker) {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [SERVER, "--host", host],
    cwd: ROOT,
    env: { ...process.env, ESTIMATE_REPO_ROOT: ROOT },
    stderr: "inherit",
  });
  const client = new Client({ name: "estimate-agent-bridge-live-smoke", version: "1.0.0" });
  await client.connect(transport);
  try {
    const result = await client.callTool(
      {
        name: tool,
        arguments: {
          prompt: `This is a connection smoke test. Reply with exactly ${marker} and nothing else.`,
          context_files: [],
          timeout_seconds: 180,
        },
      },
      undefined,
      { timeout: 190_000 },
    );
    const payload = parseToolResult(result);
    if (!payload.ok) throw new Error(`${payload.vendor} failed: ${payload.error}`);
    if (!String(payload.response).includes(marker)) {
      throw new Error(`${payload.vendor} response did not include ${marker}`);
    }
    return payload;
  } finally {
    await client.close();
  }
}

const claude = await callOppositeVendor("codex", "ask_claude", "BRIDGE_CLAUDE_OK");
const codex = await callOppositeVendor("claude", "ask_codex", "BRIDGE_CODEX_OK");

console.log(
  JSON.stringify(
    {
      ok: true,
      claude: {
        model: claude.model,
        duration_ms: claude.duration_ms,
        response: claude.response,
      },
      codex: {
        model: codex.model,
        duration_ms: codex.duration_ms,
        response: codex.response,
      },
    },
    null,
    2,
  ),
);
