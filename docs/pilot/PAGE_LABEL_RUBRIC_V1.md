# Pilot Page Label Rubric v1

Frozen for the two-building pilot. The executable taxonomy and prompt are in
`tools/agent-bridge/src/page-label.mjs` with version
`pilot-page-label-v1`.

- Inspect the rendered page image itself. Filenames, OCR, database rows, prior
  labels, and peer output are unavailable and must not determine the answer.
- Choose one primary category from the frozen 16-value taxonomy. Visible finish
  content wins over a generic floor-plan call on a genuinely mixed page.
- Judge all eight flags independently from visible evidence. Category agreement
  does not erase a flag disagreement.
- Record visible sheet number/title when readable, one evidence sentence, an
  honest 0-1 confidence, and concise uncertainty for mixed, illegible, or
  ambiguous pages.
- Failure to inspect the image is a worker failure, never a guessed label.
- Claude and Codex outputs are machine observations. Exact agreement is
  `machine_cross_verified`, not human truth. Disagreements require Nick review;
  agreements remain subject to the deterministic audit policy.
- No bridge run writes Postgres or creates a human decision.
