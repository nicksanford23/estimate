---
name: label-pages
description: Classify construction plan-set page images into the 15-category flooring taxonomy and write v2 page_label rows. Used by page-labeler agents.
---

# Labeling plan-set pages (v2 schema)

You label pages of construction plan sets for a flooring-estimating model.
Work ONLY on the pages assigned in your prompt. Judge the page IMAGE — open
it with the Read tool and look at it. The title block (bottom/right edge)
is a hint, never the verdict; drawing content decides.

## Categories (exact strings)

| category | you're looking at |
|---|---|
| floor_plan | dimensioned architectural plan of building interior (walls, doors, rooms) |
| finish_plan | plan showing floor/finish materials via hatches, finish tags (LVT-1, CPT-1), legend |
| finish_schedule | the room-finish TABLE (room → floor/base/wall materials) |
| demo_plan | demolition plan (existing walls dashed/hatched for removal) |
| reflected_ceiling | ceiling plan (light fixtures, ceiling grid, RCP in title) |
| furniture_plan | furniture/equipment layout on a plan |
| site_plan | building exterior/site: parking, landscaping, property lines |
| elevation_section | exterior/interior elevations, building sections, wall sections |
| detail | enlarged construction details, callouts, assemblies |
| schedule_other | non-finish tables: door/window/hardware schedules |
| structural | framing/foundation plans, S-sheets, rebar, beams |
| mep | any other-discipline engineering/equipment sheet: mechanical, electrical, plumbing, fire (M/E/P/FP), technology/AV/low-voltage/security (T-series), elevators/escalators (VT), foodservice equipment (FS/K) |
| life_safety | code/egress plans: occupant-load & exit-capacity tables, egress paths hatched over a floor plan (LS/G-series) |
| cover_index | cover sheet, drawing index, general project info sheet |
| specs_notes | dense text: specifications, general notes, code summaries |
| other | anything else (photos, forms, maps, illegible) |

Common confusions: finish_plan vs floor_plan → finish_plan iff finish
materials/tags/hatching are the page's POINT. A floor plan that merely has
room names is floor_plan. RCP looks like a floor plan → check for ceiling
grid/fixtures. Furniture plan vs floor plan → furniture is the subject vs
walls/dimensions the subject.

Rules from the pilot:
- HYBRID sheets (two drawing types side-by-side, e.g. plan + finishes plan,
  FFE + RCP): pick the category of the dominant/most-detailed drawing —
  but if EITHER half is finish/flooring content, pick that keep category
  (over-keeping is cheap, missing finishes is not). Always set
  flag_reason='hybrid: X + Y'.
- Content beats sheet number: an all-text sheet is specs_notes even if
  numbered S000/A000. A sheet titled RCP whose drawing is actually furniture
  → furniture_plan + flag.
- life_safety exists — don't force egress/code plans into floor_plan.
- Roof plans (plan view of the roof) → other, note "roof plan" in evidence.
- Legend/abbreviation/symbol reference sheets → specs_notes.
- If a page is clearly the same sheet you already labeled from another
  document, label it normally + flag_reason='possible duplicate'. Don't hunt
  for duplicates; embedding dedup handles that at scale.

## Per page, record

- `category`, `confidence` (0–1, honest — a 0.5 you're unsure of beats a
  fake 0.9; ambiguous/illegible → low confidence)
- `sheet_title`: title-block sheet number + name ("A-101 FIRST FLOOR PLAN"),
  NULL if unreadable
- Observations (0/1): `scale_visible` (written scale or scale bar),
  `finish_codes_visible` (tags like LVT-1/CPT-2/RB-1/VCT), `table_present`
  (any table/grid), `room_labels_visible` (room names or numbers),
  `dimensions_visible` (dimension strings)
- `flag_reason`: NULL normally; a short phrase when something needs review
  ("blurry scan", "hybrid plan+schedule sheet", "rotated 90°")
- `evidence`: ONE sentence tying the call to what you saw

## Mechanics

Database: Neon Postgres, accessed ONLY via `scripts/db.sh "SQL"` (from
/workspaces/estimate). It prints rows pipe-separated. Batch several INSERTs
in one db.sh call. Never touch data/estimate.db (legacy).

Work in batches of 10. For each assigned page:
1. `./scripts/db.sh "SELECT image_path FROM page WHERE id=<id>"` — then Read the image.
2. INSERT (append-only — NEVER UPDATE/DELETE):
```sql
INSERT INTO page_label (page_id, source, category, keep, confidence,
  sheet_title, scale_visible, finish_codes_visible, table_present,
  room_labels_visible, dimensions_visible, flag_reason, evidence)
VALUES (?, '<source from your prompt>', ?,
  CASE WHEN ? IN ('floor_plan','finish_plan','finish_schedule','demo_plan')
       THEN 1 ELSE 0 END,
  ?, ?, ?, ?, ?, ?, ?, ?, ?);
UPDATE page SET status='labeled' WHERE id=?;
```
   (run via scripts/db.sh with literal values inlined; keep=derived, never
   judged separately. Site plans are NEVER keep=1. Escape single quotes in
   text values by doubling them.)
3. Do NOT read existing page_label rows — label blind.
4. Stop at 80 pages total even if more are assigned; report what's left.

Report at the end: pages labeled, category counts, flags raised.
