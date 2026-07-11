import assert from "node:assert/strict";
import { mkdir, mkdtemp, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { parseJsonOutput, resolveProjectFile } from "../src/bridge.mjs";
import { comparePageLabels } from "../src/page-label.mjs";

const baseLabel = {
  category: "floor_plan",
  flags: ["dimensions_visible", "room_labels_visible"],
  sheet_number: "A101",
  sheet_title: "FIRST FLOOR PLAN",
  confidence: 0.9,
  evidence: "Visible room plan, doors, walls, and dimensions.",
  uncertainty: "",
  image_inspected: true,
};

test("comparePageLabels reports exact per-claim agreement without human truth", () => {
  const result = comparePageLabels(baseLabel, { ...baseLabel });
  assert.equal(result.state, "machine_cross_verified");
  assert.equal(result.all_claims_agree, true);
  assert.equal(result.human_truth, false);
  assert.equal(result.claims.length, 9);
});

test("comparePageLabels exposes each disagreement", () => {
  const result = comparePageLabels(baseLabel, {
    ...baseLabel,
    category: "finish_plan",
    flags: ["dimensions_visible", "scale_visible"],
  });
  assert.equal(result.state, "machine_disagreement");
  assert.deepEqual(result.disagreement_keys.sort(), ["category", "room_labels_visible", "scale_visible"]);
  assert.equal(result.requires_human_review, true);
});

test("resolveProjectFile rejects symlink escapes", async () => {
  const root = await mkdtemp(join(tmpdir(), "bridge-root-"));
  const outside = await mkdtemp(join(tmpdir(), "bridge-outside-"));
  await mkdir(join(root, "inside"));
  await writeFile(join(outside, "secret.txt"), "nope");
  await symlink(join(outside, "secret.txt"), join(root, "inside", "escape.txt"));
  await assert.rejects(() => resolveProjectFile(root, "inside/escape.txt"), /escapes the project root/);
});

test("parseJsonOutput accepts a final JSON line after harmless output", () => {
  assert.deepEqual(parseJsonOutput('notice\n{"ok":true}\n'), { ok: true });
});
