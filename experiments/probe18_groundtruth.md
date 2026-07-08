# Probe 18 — We DO have per-room ground truth (finish schedules with area)

**Date:** 2026-07-08
**Script:** `scripts/probe18_find_groundtruth.py` (parallel, 16 workers)
**Follows:** the "we're flying blind, no ground truth" conclusion — now overturned.

## Finding
Scanned 393 schedule / life-safety / finish / cover pages across 60 docs for
"<number> SF" area tokens + schedule headers. **73 candidate area-table pages
across 36 unique permits.** Two sources of per-room ground truth in OUR OWN data:
- **Room Finish Schedules with an AREA column** (the gold — per-room floor area
  AND floor material AND base, with a checkable total).
- **Life-safety occupant-load tables** (area per space; often gross/zoned — weaker).

## Confirmed by eye — `26-05332-NEWC` p19 (Curran Rd Townhouses)
A full "Room Finish Schedule": Room #, Room Name, **Floor (VF-1)**, Base (RB-1),
Wall, Ceiling, Ceiling Height, **Area (SF)**, Comments — 36 rooms (units A-D),
per-room areas (27, 207, 164, 24, 162 SF...), **total 5,278 SF**. This is a
complete takeoff answer key sitting in a permit we already have.

## Why it matters
All session we couldn't PROVE accuracy — no ground truth. It was in our own data.
**We can now measure per-room geometry error on ~36 permits without the flooring
company.** (The flooring co's takeoffs still add volume + per-material quantities —
additive, not required.)

## Impact on the data plan
Highest-value permits = floor plan AND a finish-schedule/area table (self-
validating). Tag for "has area schedule" when scraping/downloading; those go first.

## Caveats (stay honest)
- Some hits are life-safety occupant loads (gross/zoned), not per-room floor area —
  verify per source.
- 26-05332 is a townhouse (repeated units) = Probe 3's hard case for geometry, AND
  it's a flattened PDF (no wall layers — verify log: wall_segs=0). So it's a TOUGH
  first validation, on the weaker rules geometry path. Good — we want to see failure
  against a real answer key.

## Candidate ground-truth permits (area-table pages, from the scan)
25-11774, 26-05332, 24-06233, 20-29653, 18-13316, 22-37867, 24-06748, 24-29895,
24-35172, 23-24514, 25-16244, 16-17098, 17-35150, 22-26329, 19-21978, 24-26713,
24-17262, 25-19247, 24-22310 (24-26713 & 24-22310 ALSO have confirmed wall layers).
