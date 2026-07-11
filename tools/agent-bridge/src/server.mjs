#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import {
  askClaude,
  askCodex,
  bridgeStatus,
  consultBoth,
  dualPageLabel,
  getRepoRoot,
} from "./bridge.mjs";

function parseHost(argv) {
  const index = argv.indexOf("--host");
  const host = index >= 0 ? argv[index + 1] : null;
  if (host !== "codex" && host !== "claude") {
    throw new Error("Usage: server.mjs --host codex|claude");
  }
  return host;
}

function jsonResult(value) {
  return {
    content: [{ type: "text", text: JSON.stringify(value, null, 2) }],
  };
}

function errorResult(error) {
  return {
    content: [
      {
        type: "text",
        text: error instanceof Error ? error.message : String(error),
      },
    ],
    isError: true,
  };
}

function registerSafeTool(server, name, config, handler) {
  server.registerTool(name, config, async (input) => {
    try {
      return jsonResult(await handler(input));
    } catch (error) {
      return errorResult(error);
    }
  });
}

const ConsultationInput = z.object({
  prompt: z.string().min(1).max(30_000),
  context_files: z.array(z.string().min(1)).max(20).optional().default([]),
  timeout_seconds: z.number().int().min(30).max(900).optional().default(300),
});

const PageLabelInput = z.object({
  image_path: z.string().min(1),
  page_ref: z.string().min(1).max(500),
  timeout_seconds: z.number().int().min(30).max(900).optional().default(300),
});

async function main() {
  const host = parseHost(process.argv.slice(2));
  const root = await getRepoRoot();
  const server = new McpServer(
    { name: "estimate-agent-bridge", version: "0.1.0" },
    {
      instructions:
        "Use the opposite-vendor consultation tool when the user asks for that vendor's independent view. Use consult_both only when two independent responses are useful. dual_page_label creates machine observations only; it never creates human truth or writes to Postgres.",
    },
  );

  registerSafeTool(
    server,
    "bridge_status",
    {
      description:
        "Check that both local vendor CLIs are installed. This does not spend model tokens or access the database.",
      inputSchema: z.object({}),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true },
    },
    () => bridgeStatus({ root, host }),
  );

  if (host === "codex") {
    registerSafeTool(
      server,
      "ask_claude",
      {
        description:
          "Ask a fresh read-only Claude Sonnet worker for an independent response. The worker cannot edit the repo and does not share this conversation unless it is included in the prompt.",
        inputSchema: ConsultationInput,
        annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false },
      },
      ({ prompt, context_files, timeout_seconds }) =>
        askClaude({ root, prompt, contextFiles: context_files, timeoutSeconds: timeout_seconds }),
    );
  } else {
    registerSafeTool(
      server,
      "ask_codex",
      {
        description:
          "Ask a fresh ephemeral read-only Codex worker for an independent response. The worker cannot edit the repo and does not share this conversation unless it is included in the prompt.",
        inputSchema: ConsultationInput,
        annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false },
      },
      ({ prompt, context_files, timeout_seconds }) =>
        askCodex({ root, prompt, contextFiles: context_files, timeoutSeconds: timeout_seconds }),
    );
  }

  registerSafeTool(
    server,
    "consult_both",
    {
      description:
        "Run fresh read-only Claude and Codex consultations concurrently and return their responses separately without merging or declaring agreement.",
      inputSchema: ConsultationInput,
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false },
    },
    ({ prompt, context_files, timeout_seconds }) =>
      consultBoth({ root, prompt, contextFiles: context_files, timeoutSeconds: timeout_seconds }),
  );

  registerSafeTool(
    server,
    "dual_page_label",
    {
      description:
        "Have Claude and Codex independently inspect the same rendered page image in separate temporary workspaces, compare category and flags after both commit, and save a raw machine-only run artifact under ignored data/. It never writes labels or truth to Postgres.",
      inputSchema: PageLabelInput,
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false },
    },
    ({ image_path, page_ref, timeout_seconds }) =>
      dualPageLabel({
        root,
        host,
        imagePath: image_path,
        pageRef: page_ref,
        timeoutSeconds: timeout_seconds,
      }),
  );

  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Node 24 can exit before the first initialize message unless stdin is
  // explicitly kept in flowing mode. A stdio MCP server lives exactly as
  // long as its parent client's input stream.
  process.stdin.resume();
  await new Promise((resolveInputClosed) => {
    process.stdin.once("end", resolveInputClosed);
    process.stdin.once("close", resolveInputClosed);
  });
  await server.close();
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack : String(error));
  process.exitCode = 1;
});
