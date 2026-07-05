---
name: sf-extraction
description: Square-footage extraction from vector floor plans (Route A) — the pipeline, known failure modes and counters, verification standards, probe protocol. Read before any SF/geometry work.
---

# Square footage from vector plans (Route A)

The product moment: floor plan in → room polygons + SF + confidence out.
The one unforgivable failure is a CONFIDENT-BUT-WRONG area (silent bid
error). A missing suggestion is fine; a wrong number is not. When in doubt,
output nothing and say why.

## Pipeline (per page)
1. GEOMETRY SOURCE: the ORIGINAL PDF from R2 (docs/<onestop_doc_id>.pdf),
   via fitz page.get_drawings(). NEVER the rendered PNG.
2. DOMINANT ANGLE: histogram all segment angles (mod 90 deg); the modal
   angle is the building's rotation. All wall filtering is relative to it.
3. WALL CANDIDATES: segments/thin-fill-rects aligned to dominant angle
   (+/-2 deg) or its perpendicular, length > ~2% page width, stroke width
   in the thick clusters. Both strokes AND thin filled rects count.
4. HATCH SUPPRESSION: drop sets of >=4 near-identical parallel segments at
   regular spacing (<0.6% page width apart) — hatches repeat, walls don't.
5. GAP CLOSING: snap endpoints within tolerance; close openings narrower
   than ~4.5 ft (doors). Door-swing arcs (quarter circles) mark doorways —
   their chord is a closable gap.
6. POLYGONIZE: shapely polygonize over the cleaned wall graph; drop
   slivers (<15 sqft) and the page-border polygon.
7. SCALE: parse the scale note from pagetext ("1/8\" = 1'-0\"" etc → feet
   per PDF point = (12/denominator_inches)/72 ... compute carefully).
   MANDATORY SELF-AUDIT: find >=1 printed dimension string (e.g. 24'-6")
   in the page text, locate its extents/leader in geometry if possible,
   or at minimum sanity-check: does the largest room come out
   30-10,000 sqft and the building footprint within 2x of the permit's
   recorded sqft (public.permits.sqft) when present? Scale that fails
   audit → NO OUTPUT for the page, verdict 'scale_unverified'.
8. OUTPUT per page: JSON rooms [{polygon_pts, sqft, confidence}], total
   SF, scale used, audit status + an overlay PNG (polygons filled
   semi-transparent, SF printed in each room) for human grading.

## Known failure modes (probe-1 verified) and counters
- Rotated buildings (8-45 deg off axis) → step 2 fixes; never assume
  page-axis alignment.
- Hatch tick-marks read as hundreds of walls → step 4.
- Door gaps prevent room closure → step 5.
- Enlarged-detail pages masquerade as floor plans (bathroom blowups) →
  check sheet title for ENLARGED/DETAIL; scale differs; flag, don't sum
  into building totals.
- Scanned/flattened pages (~1 in 6): get_drawings returns ~nothing →
  verdict 'raster', out of Route A scope; never guess.
- Multiple plans on one sheet: polygonize clusters separately; report
  per-cluster.

## Verification standard (every probe, every build)
Numbers are graded against the DRAWING'S OWN dimension strings: pick 3+
rooms, compute width/length from printed dimensions, compare to polygon
math. Report per-room % error. A run without this grading table is
incomplete. Overlay PNGs accompany every result — humans grade pictures,
not stats.

## Probe ladder (state lives in STATE.md)
- Probe 1 DONE: vectors exist 5/6, naive filter 2/6, fixes identified.
- Probe 2: full pipeline on the 2 GOOD pages → first graded SF numbers.
- Probe 3: pipeline across 15-20 floor plans, different permits →
  coverage table (% pages workable, error distribution).
- Then: design the production stage-4 build + which parts need ML
  (wall-vs-line judgment) vs stay rules.

Artifacts live in data/probe1/, data/probe2/, ... Scripts in scripts/
(probe_vector_walls.py is the probe-1 base). Orchestrator reviews every
probe verdict before the next rung.
