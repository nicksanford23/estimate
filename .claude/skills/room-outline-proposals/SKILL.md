---
name: room-outline-proposals
description: Generate machine room-outline proposals for a complete project (crops -> Claude-vision polygons + optional SAM cross-check -> editor preload) and route them to human review. The proposal factory feeding geometry training data. Written 2026-07-17 (Fable) after the 24-06748-RNVS bake-off.
---

# Room-outline proposal pipeline

Turns a complete project plan set into per-room outline PROPOSALS loaded
into the /v2 annotate editor. Proposals are machine observations — Nick's
editor confirmation is the only thing that makes training truth. Never
skip that sentence when explaining status.

## Proven results (24-06748-RNVS, BAKEOFF_V1.md)

Claude-vision one-shot: 29/35 rooms within 25% of schedule (15 within
10%), crisp 4-7 vertex wall-face polygons, calibrated confidence. SAM 2.1
Small on the same crops: different failure modes, useful as independent
cross-check only (its own score cannot select; full-sheet feeding is
retired). Cost: vision ≈ subscription tokens; SAM ≈ $0.15 GPU.

## Pipeline (per project)

0. PREREQS: complete project packet per PROJECT_FIRST_EXECUTION_V1
   (active revision, all primary level plans, schedule capability, one
   viewport bbox per level, room roster). Missing members are visible
   blockers. Roster comes from the schedule when one exists, else from
   room-label text on the plans. All of it machine-observed until Nick
   confirms.
1. ANNOTATION PACKET: scripts/build_geometry_annotation_packet.py
   --permit <P> (or equivalent) -> one required task per scheduled space.
2. ANCHORS: room-label text coords from the PDF (fitz words) whitelisted
   by roster, INSIDE the proposed-plan viewport only. Disambiguation rule
   (proven): room tag = hit with "SF" token directly below; reject hits
   whose right neighbor is "|" (door tags share the numbering
   convention). Labels not in text (graphics) -> place visually (agent
   Reads the render, iterates crops until confident) and mark
   anchor_provenance=visual_manual; unplaceable -> status=no_anchor,
   never silently dropped.
3. CROPS: scripts/build_sam_smoke_bundle_g1b.py pattern — per-room crop
   from the ORIGINAL PDF (fitz clip), longest side ~1000px, px_per_ft
   recorded per task, transforms with round-trip self-test (<0.01pt).
   KNOWN GAP: open-plan zones get clipped by room-sized crops (305/306/
   307 failure) — for rooms suspected open (no enclosing walls near
   anchor), use the full level viewport as the crop instead.
4. VISION ARM (primary): one Opus agent per level, background, parallel.
   Prompt contract (copy from the 2026-07-16 session): Read each crop,
   apply GEOMETRY_LABEL_BOOK rules R1-R11, output ordered polygon in
   ORIGINAL image pixels (note the Read tool's display-scaling line),
   outcome, per-edge boundary_notes, confidence 0-1. IGNORE printed SF
   (hard rule: the answer must not shape the proposal). Unjudgeable ->
   unresolved + null polygon. Agents must NOT read any SAM results
   (independence). Output: claude_vision/level_XX.json.
5. SAM CROSS-CHECK (optional, ~$0.15): deploy_sam_smoke.py deploy
   --bundle <crops> + poll. OPS: dockerArgs is broken (pods crash-loop);
   pod boots stock image + PUBLIC_KEY env; account proxy ssh needs the
   pubkey registered on the CURRENT account — else ship via the pod's
   DIRECT public ip:port (query pod runtime ports; key
   ~/.ssh/runpod_ed25519). Poll auto-terminates; verify with --bundle
   <crops> (default bundle gives spurious dim errors). Cleanup for
   comparison: binary_closing(9x9) + fill_holes + largest component.
6. VALIDATE + LOAD: convert polygon px -> PDF via the per-task transform
   (pdf = px/zoom + crop_origin_pdf); VALIDATE against each task's
   anchor_px/anchor_pdf pair (<0.1pt or stop). Write
   results/proposals_for_editor.json {task_id: {code, proposal_source,
   machine_proposal: true, polygon_pdf, outcome_suggestion, confidence,
   boundary_notes}}. The /v2/annotate/[permit] editor offers these as
   starting shapes.
7. HUMAN GATE: Nick reviews per room in the editor (accept / drag-fix /
   redraw / unresolved). Saves append to
   data/geometry_annotations/human/<permit>.outcomes.jsonl — that file is
   the training truth, nothing upstream of it.

## Confidence routing (for the approval loop)

Earned, never felt: agent self-confidence alone is NOT a gate. Candidate
auto-queue signal = vision confidence >=0.7 AND SAM-cleaned mask agrees
within tolerance AND mechanical checks pass (closed, contains own label,
no neighbor overlap, sane area). Everything else -> editor queue.
Calibrate against Nick's audit outcomes before trusting any threshold.

## Hard rules (inherited, non-negotiable)

- Machine agreement = evidence, never truth. No proposal, however good,
  becomes training data without Nick's explicit editor/tap decision.
- Printed schedule SF: diagnostic AFTER prediction only. Never selects a
  candidate, never sizes a prompt/box/polygon.
- Projects, not pages: run complete plan sets; every level gets an
  outcome. Splits stay project-disjoint (GEOMETRY_REBOOT_V1 ladder).
- Max ~80 rooms per vision agent; one level per agent is the proven unit.
- Label book gaps found mid-run (new trade question) -> flag for the
  founder list, mark affected rooms unresolved; never invent a rule.
