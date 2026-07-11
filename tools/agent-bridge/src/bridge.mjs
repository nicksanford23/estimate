import { createHash, randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import {
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  realpath,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { basename, dirname, extname, isAbsolute, join, relative, resolve } from "node:path";
import { tmpdir } from "node:os";

import {
  PAGE_LABEL_JSON_SCHEMA,
  PAGE_LABEL_RUBRIC_VERSION,
  PageLabelSchema,
  buildPageLabelPrompt,
  comparePageLabels,
} from "./page-label.mjs";

const MAX_CAPTURE_BYTES = 2 * 1024 * 1024;
const EMPTY_MCP_CONFIG = '{"mcpServers":{}}';
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp", ".gif"]);

function elapsedMs(startedAt) {
  return Math.round(Number(process.hrtime.bigint() - startedAt) / 1_000_000);
}

function errorText(error) {
  return error instanceof Error ? error.message : String(error);
}

function stderrSummary(stderr) {
  const clean = stderr.trim();
  return clean.length > 4000 ? clean.slice(-4000) : clean;
}

export async function getRepoRoot(explicitRoot = process.env.ESTIMATE_REPO_ROOT || process.cwd()) {
  return realpath(resolve(explicitRoot));
}

function isInside(root, candidate) {
  const rel = relative(root, candidate);
  return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

export async function resolveProjectFile(root, requestedPath) {
  if (typeof requestedPath !== "string" || requestedPath.trim() === "") {
    throw new Error("File path must be a non-empty string");
  }
  const candidate = resolve(root, requestedPath);
  const actual = await realpath(candidate);
  if (!isInside(root, actual)) {
    throw new Error(`Path escapes the project root: ${requestedPath}`);
  }
  const info = await stat(actual);
  if (!info.isFile()) {
    throw new Error(`Path is not a file: ${requestedPath}`);
  }
  return { absolute: actual, relative: relative(root, actual) };
}

export async function resolveProjectFiles(root, requestedPaths = []) {
  return Promise.all(requestedPaths.map((requestedPath) => resolveProjectFile(root, requestedPath)));
}

export function parseJsonOutput(text) {
  const trimmed = text.trim();
  if (!trimmed) throw new Error("Worker returned no JSON output");
  try {
    return JSON.parse(trimmed);
  } catch {
    const lines = trimmed.split(/\r?\n/).reverse();
    for (const line of lines) {
      try {
        return JSON.parse(line);
      } catch {
        // Continue to the preceding line.
      }
    }
  }
  throw new Error("Worker output was not valid JSON");
}

export async function runProcess(command, args, options = {}) {
  const {
    cwd,
    input = "",
    timeoutMs = 300_000,
    env = process.env,
    maxCaptureBytes = MAX_CAPTURE_BYTES,
  } = options;

  return new Promise((resolveRun, rejectRun) => {
    const child = spawn(command, args, {
      cwd,
      env,
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let capturedBytes = 0;
    let timedOut = false;
    let outputExceeded = false;
    let settled = false;

    const hardKill = () => {
      if (!child.killed) child.kill("SIGKILL");
    };
    const timeout = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
      setTimeout(hardKill, 2000).unref();
    }, timeoutMs);

    const capture = (target, chunk) => {
      capturedBytes += chunk.length;
      if (capturedBytes > maxCaptureBytes) {
        outputExceeded = true;
        child.kill("SIGTERM");
        setTimeout(hardKill, 2000).unref();
        return target;
      }
      return target + chunk.toString("utf8");
    };

    child.stdout.on("data", (chunk) => {
      stdout = capture(stdout, chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr = capture(stderr, chunk);
    });
    child.on("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      rejectRun(error);
    });
    child.on("close", (code, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolveRun({ code, signal, stdout, stderr, timedOut, outputExceeded });
    });

    child.stdin.on("error", () => {});
    child.stdin.end(input);
  });
}

function consultationPrompt(prompt, files) {
  const fileText = files.length
    ? `\n\nProject files explicitly relevant to this request:\n${files.map((file) => `- ${file.relative}`).join("\n")}`
    : "";
  return `Act as an independent cross-vendor consultant. Analyze the request yourself. You may read the listed project files and other directly relevant repository files, but do not edit files, run write operations, or delegate to another model. Do not inspect secrets or prior agent outputs unless the request explicitly requires them.\n\nRequest:\n${prompt}${fileText}`;
}

function workerFailure(vendor, startedAt, error, stderr = "") {
  return {
    vendor,
    ok: false,
    duration_ms: elapsedMs(startedAt),
    error: errorText(error),
    ...(stderrSummary(stderr) ? { stderr: stderrSummary(stderr) } : {}),
  };
}

function workerSuccess(vendor, startedAt, response, metadata = {}) {
  return {
    vendor,
    ok: true,
    duration_ms: elapsedMs(startedAt),
    response,
    ...metadata,
  };
}

function claudeResponse(wrapper) {
  if (wrapper?.is_error) {
    throw new Error(wrapper.result || wrapper.error || "Claude returned an error");
  }
  if (wrapper?.structured_output !== undefined) return wrapper.structured_output;
  if (wrapper?.result !== undefined) return wrapper.result;
  return wrapper;
}

function structuredObject(value) {
  if (typeof value === "string") return parseJsonOutput(value);
  if (value && typeof value === "object") return value;
  throw new Error("Structured worker result was not an object");
}

export async function askClaude({ root, prompt, contextFiles = [], timeoutSeconds = 300 }) {
  const startedAt = process.hrtime.bigint();
  const model = process.env.AGENT_BRIDGE_CLAUDE_MODEL || "sonnet";
  try {
    const files = await resolveProjectFiles(root, contextFiles);
    const run = await runProcess(
      process.env.AGENT_BRIDGE_CLAUDE_BIN || "claude",
      [
        "-p",
        "--model",
        model,
        "--effort",
        "high",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "Read,Glob,Grep",
        "--allowed-tools",
        "Read,Glob,Grep",
        "--strict-mcp-config",
        "--mcp-config",
        EMPTY_MCP_CONFIG,
      ],
      {
        cwd: root,
        input: consultationPrompt(prompt, files),
        timeoutMs: timeoutSeconds * 1000,
      },
    );
    if (run.timedOut) throw new Error(`Claude timed out after ${timeoutSeconds}s`);
    if (run.outputExceeded) throw new Error("Claude exceeded the bridge output limit");
    if (run.code !== 0) {
      throw new Error(`Claude exited with code ${run.code}${run.signal ? ` (${run.signal})` : ""}`);
    }
    const response = claudeResponse(parseJsonOutput(run.stdout));
    return workerSuccess("claude", startedAt, response, { model });
  } catch (error) {
    return workerFailure("claude", startedAt, error);
  }
}

export async function askCodex({ root, prompt, contextFiles = [], timeoutSeconds = 300 }) {
  const startedAt = process.hrtime.bigint();
  const model = process.env.AGENT_BRIDGE_CODEX_MODEL || null;
  const scratch = await mkdtemp(join(tmpdir(), "estimate-codex-consult-"));
  const outputPath = join(scratch, "last-message.txt");
  try {
    const files = await resolveProjectFiles(root, contextFiles);
    const args = [
      "exec",
      "--ephemeral",
      "--sandbox",
      "read-only",
      "--cd",
      root,
      "--color",
      "never",
      "-c",
      "mcp_servers.estimate_agent_bridge.enabled=false",
      "--output-last-message",
      outputPath,
    ];
    if (model) args.push("--model", model);
    args.push("-");
    const run = await runProcess(process.env.AGENT_BRIDGE_CODEX_BIN || "codex", args, {
      cwd: root,
      input: consultationPrompt(prompt, files),
      timeoutMs: timeoutSeconds * 1000,
    });
    if (run.timedOut) throw new Error(`Codex timed out after ${timeoutSeconds}s`);
    if (run.outputExceeded) throw new Error("Codex exceeded the bridge output limit");
    if (run.code !== 0) {
      throw new Error(
        `Codex exited with code ${run.code}${run.signal ? ` (${run.signal})` : ""}: ${stderrSummary(run.stderr)}`,
      );
    }
    const response = await readFile(outputPath, "utf8");
    return workerSuccess("codex", startedAt, response.trim(), {
      model: model || "configured_default",
    });
  } catch (error) {
    return workerFailure("codex", startedAt, error);
  } finally {
    await rm(scratch, { recursive: true, force: true });
  }
}

export async function consultBoth(options) {
  const [claude, codex] = await Promise.all([askClaude(options), askCodex(options)]);
  return {
    claude,
    codex,
    combined_by_bridge: false,
    note: "Independent responses are returned separately; the calling agent or human compares them.",
  };
}

async function runClaudePageLabel({ workspace, imageFilename, timeoutSeconds }) {
  const startedAt = process.hrtime.bigint();
  const model = process.env.AGENT_BRIDGE_CLAUDE_MODEL || "sonnet";
  try {
    const run = await runProcess(
      process.env.AGENT_BRIDGE_CLAUDE_BIN || "claude",
      [
        "-p",
        "--model",
        model,
        "--effort",
        "high",
        "--output-format",
        "json",
        "--json-schema",
        JSON.stringify(PAGE_LABEL_JSON_SCHEMA),
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "Read",
        "--allowed-tools",
        "Read",
        "--strict-mcp-config",
        "--mcp-config",
        EMPTY_MCP_CONFIG,
      ],
      {
        cwd: workspace,
        input: buildPageLabelPrompt(imageFilename),
        timeoutMs: timeoutSeconds * 1000,
      },
    );
    if (run.timedOut) throw new Error(`Claude timed out after ${timeoutSeconds}s`);
    if (run.outputExceeded) throw new Error("Claude exceeded the bridge output limit");
    if (run.code !== 0) {
      throw new Error(`Claude exited with code ${run.code}: ${stderrSummary(run.stderr)}`);
    }
    const raw = structuredObject(claudeResponse(parseJsonOutput(run.stdout)));
    const label = PageLabelSchema.parse(raw);
    return workerSuccess("claude", startedAt, label, { model });
  } catch (error) {
    return workerFailure("claude", startedAt, error);
  }
}

export async function runCodexPageLabel({ workspace, imageFilename, timeoutSeconds }) {
  const startedAt = process.hrtime.bigint();
  const model = process.env.AGENT_BRIDGE_CODEX_MODEL || null;
  const reasoningEffort = process.env.AGENT_BRIDGE_CODEX_LABEL_REASONING_EFFORT || "medium";
  if (!new Set(["minimal", "low", "medium", "high", "xhigh"]).has(reasoningEffort)) {
    return workerFailure(
      "codex",
      startedAt,
      new Error(`Unsupported Codex label reasoning effort: ${reasoningEffort}`),
    );
  }
  const schemaPath = join(workspace, "output-schema.json");
  const outputPath = join(workspace, "last-message.json");
  try {
    await writeFile(schemaPath, `${JSON.stringify(PAGE_LABEL_JSON_SCHEMA, null, 2)}\n`, "utf8");
    const args = [
      "exec",
      "--ephemeral",
      "--sandbox",
      "read-only",
      "--skip-git-repo-check",
      "--cd",
      workspace,
      "--image",
      join(workspace, imageFilename),
      "--output-schema",
      schemaPath,
      "--output-last-message",
      outputPath,
      "--color",
      "never",
      "-c",
      `model_reasoning_effort=${JSON.stringify(reasoningEffort)}`,
    ];
    if (model) args.push("--model", model);
    args.push("-");
    const run = await runProcess(process.env.AGENT_BRIDGE_CODEX_BIN || "codex", args, {
      cwd: workspace,
      input: buildPageLabelPrompt(imageFilename),
      timeoutMs: timeoutSeconds * 1000,
    });
    if (run.timedOut) throw new Error(`Codex timed out after ${timeoutSeconds}s`);
    if (run.outputExceeded) throw new Error("Codex exceeded the bridge output limit");
    if (run.code !== 0) {
      throw new Error(`Codex exited with code ${run.code}: ${stderrSummary(run.stderr)}`);
    }
    const raw = parseJsonOutput(await readFile(outputPath, "utf8"));
    const label = PageLabelSchema.parse(raw);
    return workerSuccess("codex", startedAt, label, {
      model: model || "configured_default",
      reasoning_effort: reasoningEffort,
    });
  } catch (error) {
    return workerFailure("codex", startedAt, error);
  }
}

async function sha256File(path) {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

async function writeRunArtifact(root, runId, artifact) {
  const outputDir = join(root, "data", "agent_bridge", "runs");
  await mkdir(outputDir, { recursive: true });
  const finalPath = join(outputDir, `${runId}.json`);
  const tempPath = join(outputDir, `.${runId}.tmp`);
  await writeFile(tempPath, `${JSON.stringify(artifact, null, 2)}\n`, "utf8");
  await rename(tempPath, finalPath);
  return relative(root, finalPath);
}

export async function dualPageLabel({
  root,
  host,
  imagePath,
  pageRef,
  timeoutSeconds = 300,
}) {
  const image = await resolveProjectFile(root, imagePath);
  const extension = extname(image.absolute).toLowerCase();
  if (!IMAGE_EXTENSIONS.has(extension)) {
    throw new Error(`Rendered page must be PNG, JPEG, WebP, or GIF: ${image.relative}`);
  }

  const runId = randomUUID();
  const claudeWorkspace = await mkdtemp(join(tmpdir(), "estimate-label-claude-"));
  const codexWorkspace = await mkdtemp(join(tmpdir(), "estimate-label-codex-"));
  const imageFilename = `page${extension}`;

  try {
    await Promise.all([
      copyFile(image.absolute, join(claudeWorkspace, imageFilename)),
      copyFile(image.absolute, join(codexWorkspace, imageFilename)),
    ]);
    const [claude, codex] = await Promise.all([
      runClaudePageLabel({ workspace: claudeWorkspace, imageFilename, timeoutSeconds }),
      runCodexPageLabel({ workspace: codexWorkspace, imageFilename, timeoutSeconds }),
    ]);

    const comparison =
      claude.ok && codex.ok
        ? comparePageLabels(claude.response, codex.response)
        : {
            state: "worker_failure",
            all_claims_agree: false,
            human_truth: false,
            requires_human_review: true,
            claims: [],
            disagreement_keys: [],
          };
    const artifact = {
      schema_version: "agent-bridge-run-v1",
      run_id: runId,
      created_at: new Date().toISOString(),
      triggered_from: host,
      task: "dual_page_label",
      page_ref: pageRef,
      image: {
        project_path: image.relative,
        sha256: await sha256File(image.absolute),
      },
      rubric_version: PAGE_LABEL_RUBRIC_VERSION,
      isolation: {
        separate_workspaces: true,
        prior_labels_available: false,
        peer_output_available_before_commit: false,
      },
      outputs: { claude, codex },
      comparison,
      database_writes: false,
      trusted_semantic_truth: false,
    };
    const artifactPath = await writeRunArtifact(root, runId, artifact);
    return { ...artifact, artifact_path: artifactPath };
  } finally {
    await Promise.all([
      rm(claudeWorkspace, { recursive: true, force: true }),
      rm(codexWorkspace, { recursive: true, force: true }),
    ]);
  }
}

export async function retryCodexForRun({ root, artifactPath, timeoutSeconds = 600 }) {
  const artifactFile = await resolveProjectFile(root, artifactPath);
  const artifact = parseJsonOutput(await readFile(artifactFile.absolute, "utf8"));
  if (artifact.task !== "dual_page_label" || !artifact.outputs?.claude?.ok) {
    throw new Error("Retry requires a dual-page artifact with a completed Claude result");
  }
  const image = await resolveProjectFile(root, artifact.image?.project_path);
  if ((await sha256File(image.absolute)) !== artifact.image.sha256) {
    throw new Error("Source image hash no longer matches the failed run");
  }
  const extension = extname(image.absolute).toLowerCase();
  const workspace = await mkdtemp(join(tmpdir(), "estimate-label-codex-retry-"));
  const imageFilename = `page${extension}`;
  try {
    await copyFile(image.absolute, join(workspace, imageFilename));
    const codex = await runCodexPageLabel({ workspace, imageFilename, timeoutSeconds });
    const priorAttempts = artifact.outputs.codex_attempts ?? [];
    artifact.outputs.codex_attempts = [...priorAttempts, artifact.outputs.codex];
    artifact.outputs.codex = codex;
    artifact.comparison = codex.ok
      ? comparePageLabels(artifact.outputs.claude.response, codex.response)
      : {
          state: "worker_failure",
          all_claims_agree: false,
          human_truth: false,
          requires_human_review: true,
          claims: [],
          disagreement_keys: [],
        };
    artifact.retry_updated_at = new Date().toISOString();
    const finalPath = join(root, artifactPath);
    const tempPath = `${finalPath}.tmp`;
    await writeFile(tempPath, `${JSON.stringify(artifact, null, 2)}\n`, "utf8");
    await rename(tempPath, finalPath);
    return { run_id: artifact.run_id, artifact_path: artifactPath, codex, comparison: artifact.comparison };
  } finally {
    await rm(workspace, { recursive: true, force: true });
  }
}

async function commandStatus(vendor, command) {
  const startedAt = process.hrtime.bigint();
  try {
    const run = await runProcess(command, ["--version"], { timeoutMs: 10_000 });
    const version = `${run.stdout}\n${run.stderr}`.trim().split(/\r?\n/)[0] || "unknown";
    return {
      vendor,
      available: run.code === 0,
      version,
      duration_ms: elapsedMs(startedAt),
    };
  } catch (error) {
    return {
      vendor,
      available: false,
      error: errorText(error),
      duration_ms: elapsedMs(startedAt),
    };
  }
}

export async function bridgeStatus({ root, host }) {
  const [claude, codex] = await Promise.all([
    commandStatus("claude", process.env.AGENT_BRIDGE_CLAUDE_BIN || "claude"),
    commandStatus("codex", process.env.AGENT_BRIDGE_CODEX_BIN || "codex"),
  ]);
  return {
    server: "estimate-agent-bridge",
    version: "0.1.0",
    host,
    root,
    claude,
    codex,
    database_access: false,
    trusted_semantic_count_created: 0,
  };
}
