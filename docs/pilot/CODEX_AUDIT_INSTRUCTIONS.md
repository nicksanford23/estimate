# Codex task: independent blind audit of 600 Baronne room outlines

Tell Codex: "Read docs/pilot/CODEX_AUDIT_INSTRUCTIONS.md and do what it says."

## The task

You are a BLIND independent auditor of room-outline quality for permit
`24-06748-RNVS` (600 Baronne St). Your verdicts will be compared against two
other independent reviewers to surface disagreements — independence is the
entire point.

## Hard rules

1. Do NOT read `data/sam_smoke/24-06748-RNVS/inspection/edge_inspection.json`,
   `INSPECTION_REPORT.md`, or `CLAUDE_BLIND_AUDIT_V1.md` until AFTER you have
   written your own complete verdicts.
2. Never judge an outline by printed square footage or area agreement — judge
   only where the lines sit relative to the drawing.

## Materials

- Rules: `docs/pilot/GEOMETRY_LABEL_BOOK_V2_DRAFT.md` — Layer-A observable
  geometry (room-facing wall face; threshold segments at door openings;
  deck/exterior edges; never a crop border as a wall; obstructions recorded,
  not policy-judged; stairs are specialty surfaces; structured unresolved
  reasons).
- Current-best polygon per room:
  `data/sam_smoke/24-06748-RNVS/inspection/repaired_proposals.json` where the
  room appears there, else
  `data/sam_smoke/24-06748-RNVS/results/proposals_for_editor.json`.
- Rendered inspection images (current polygon, numbered edges):
  `data/sam_smoke/24-06748-RNVS/inspection/inspect_<code>.png`. For the
  repaired rooms, verify the image reflects the repaired polygon; if stale,
  re-render with `scripts/edge_inspect_render.py`.
- Per-room crops: `data/sam_smoke/24-06748-RNVS/bundle_g1b/crop_<code>.png`;
  transforms in `bundle_g1b/tasks.json`.

## Procedure

For EACH of the 35 rooms: look at the current polygon on its crop and judge
EVERY edge against Layer-A. Zoom into any edge you are unsure about (enlarged
sub-crops; `scripts/edge_inspect_render.py --edge CODE:IDX` renders single-edge
strips). An un-zoomed "looks fine" is how errors slip through. Give room 304
explicit documented attention (the founder specifically doubts it).

Per-room verdict: `perfect | minor_issue | wrong | needs_founder`, plus one
line per issue naming the edge and the needed correction.

Then a SYSTEMIC HOLES section: recurring error patterns, label-book rule gaps,
approach risks (door thresholds, deck edges, closet/alcove splits, what the
per-room crops systematically hide).

## Output

Write `docs/pilot/CODEX_OUTLINE_AUDIT_24-06748_V1.md`: per-room table
(code, verdict, issues) + systemic holes. ONLY AFTER writing it, read the
prior inspector's `edge_inspection.json` and append a short agree/disagree
table (rooms where your verdict differs, with reasoning).

Constraints: no GPU, no installs, no git commits, no Postgres writes. Write
only your audit file and any re-rendered inspection images.
