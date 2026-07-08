# Probe 22 — First validated takeoff on the GOOD path (14-11290 bank)

**Date:** 2026-07-08
**Script:** `scripts/probe22_bank_validated.py`

Layer geometry per room cross-checked against the independently-read printed
DIMENSIONS (vision fleet, probe15/16). Two methods from different inputs (vector
walls vs dimension text) agreeing = validated.

## Result
- **10 of 13 enclosed rooms VALIDATED** (agree ≤15%): 104,106,107,108,112,113,
  115,116,117,118. Tight on clean rooms: 106 +0%, 108 −3%, 113 −3%, 115 −1%,
  117 −4%, 118 −0%.
- 2 "check" (15-30%): 109 (+25%), 114 (+27%).
- 1 DISAGREE: 101 Vestibule (geom 31 vs dim 78, −60%) — the known rotated
  glass-walled fragment.
- 5 open (in blobs): Lobby/Tellers/Self-Service, Copy/Fax/Mortgage — open-plan,
  need finish lines to split.

Totals: enclosed 1,178 SF, open blob 1,540, grand total 2,719 vs 3,190 branch
GROSS = −15% (net/gross). Materials: Carpet 159 SY, Tile 311 SF, Resilient 240 SF.

## What it proves / caveat
"Geometry is exact when it closes" — demonstrated: wall geometry and printed
dimensions independently converge to a few percent on clean rooms. CAVEAT:
"validated" = two independent ESTIMATES agree, NOT checked vs a true SF schedule
(the bank has none). Strong evidence, not proof. The failures are exactly the known
hard cases (fragment + open plan), not the closed rooms.
