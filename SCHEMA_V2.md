# V2 Schema & Process Constitution (draft for GPT confirmation, 2026-07-10)

*Synthesis of the two-round consultation (founder + Claude + GPT). This is
the contract the workbench, pipeline, and all model training build on.
Operating principle (locked): preserve the source; version every
derivation; attach human verification to specific claims; build datasets
only from named, traceable claims.*

## 0. Conventions
- Postgres (Neon, our schema) = source of truth for identities, decisions,
  links. Object storage (R2) = immutable artifacts, content-addressed
  (sha256 in key or manifest). CSV/JSONL = exports only. Parquet for bulk
  per-page words/segments/cells. GeoJSON-style JSON for polygons/regions.
- Human decisions are APPEND-ONLY. Current truth = latest decision per
  claim, resolved by view, never by UPDATE.
- Machine output is a candidate. Human decision is best-current-truth
  (never "gold"; blind audits + disagreement review stay).
- Nothing expensive fires on confirmation; confirmation marks ELIGIBLE and
  a queued job runs, versioned and retryable.

## 1. Identity tables
- **design_family**(id, name, notes) — same drawings across permits;
  membership via page/region similarity; used for train/test splits and
  leakage control. Permits are never collapsed operationally, only linked.
- **building**(id, permit_num, address, city_description, design_family_id,
  notes) — a permit may map to >1 building (bldg A/D/F case); a building
  belongs to exactly one permit record for ops purposes.
- **document**(id, onestop_doc_id, building_id nullable, permit_num,
  filename, filed_date, sha256, kind_hint, supersedes_document_id nullable)
  — revisions link to what they supersede.
- **page**(id, document_id, pdf_page_index, printed_page_no nullable,
  sheet_number nullable, sheet_title nullable, width_pt, height_pt,
  render_artifact_id, sha256_render, phash) — sheet_number/title carry
  extraction_source + confidence; human-confirmed values live in
  human_decision rows targeting the page.
- **region**(id, page_id, kind: plan_viewport|schedule_table|legend|
  detail|other, bbox_pdf_units, rotation=0, proposed_by, status) —
  rectangles only in pilot. Machine proposes (multi-clue: whitespace,
  linework density, titles, label clusters); human Approve / Redraw /
  Use-full-page.

## 2. Extraction (two levels, versioned)
- **extraction**(id, page_id, level: base|semantic, extractor_name,
  extractor_version, config_hash, created_at, status: active|superseded|
  defective, manifest_json) — never overwritten; new versions sit beside
  old; datasets pin exact extraction ids.
  - BASE (at ingestion, pre-confirmation): render PNG, words+bboxes
    (parquet), normalized vector segments w/ layer attrs (parquet),
    page dims + transform, layer names.
  - SEMANTIC (post page+region confirmation, queued): confirmed page type,
    sheet no/title, region geometry + transforms, schedule cell grid
    (text+bbox+row/col, parquet) for schedule regions, room-label anchors
    for plan regions; links to the exact base extraction used.
- Crops are NOT stored permanently: region coords + page render + transform
  regenerate them; hot crops cached only.

## 3. Claims & decisions
- **machine_observation**(id, target_type: page|region|schedule_row|
  polygon|document, target_id, claim_type, value_json, source: model|
  heuristic|agent, source_version, confidence, created_at).
- **human_decision**(id, target_type, target_id, claim_type, value_json,
  actor, decided_at, taxonomy_version, blind boolean, note) — one generic
  append-only table for all screens. Examples of claim_type: page_category,
  page_flags, sheet_number, region_approval, schedule_row, room_verdict,
  page_geometry_verdict, run_verdict, dataset_eligibility, identity_link.
- Page labeling = ONE primary category (small taxonomy) + independent
  boolean FLAGS (contains_floor_plan, contains_finish_schedule,
  contains_legend, contains_area_table, multiple_viewports, enlarged_plan,
  flooring_scope, geometry_candidate). keep/drop stays DERIVED, shown
  read-only with its reason.
- **taxonomy_version**(id, name, created_at, spec_json) +
  **taxonomy_map**(from_version, from_label, to_version, to_label,
  kind: rename|merge|split) — splits route affected old decisions into a
  review queue; old decisions never rewritten.

## 4. Structured schedule truth (Rooms & Finishes)
- **schedule_row**(id, region_id, row_index, room_number, room_name,
  floor_material, base, area_sf nullable, source_cells_json,
  extraction_id) — machine-extracted; each field confirmable via
  human_decision rows; confirmed rows form the room roster + answer keys.
  Cell-level (image crop coords ↔ confirmed value) pairs = table-parser
  training data.

## 5. Geometry
- **geometry_run**(id, region_id, run_no, manifest_json, created_at,
  status) — manifest freezes: source pdf hash, extraction ids + artifact
  hashes, boundary engine/model name + model-file hash, feature version,
  geometry code version + commit, full config/thresholds, layer-norm map
  version, scale value/units/evidence, transform, gap rules, filters,
  seed, container/dep versions, output artifact hashes.
- **polygon_prediction**(id, run_id, geom_json, room_label_match nullable,
  area_sf, product_action, flags_json).
- **geometry_annotation**(id, target: run|page|polygon, target_id,
  verdict, correction_json nullable, actor, created_at, note) — verdict
  vocab: page {usable|partial|unusable|wrong_viewport|wrong_scale};
  room {correct|missed|merged|split|fake|wrong_label|open_zone|
  boundary_fix}; run {approved_training|approved_eval|diagnostic|rejected}.
  correction_json stores ORIGINAL + CORRECTED geometry, action (add|remove|
  move|split|merge|redraw|relabel), failure_type, affected segment ids,
  label/material before+after; splits/merges keep links to ALL affected
  polygon ids. Founder traces snap to nearby vectors; Claude reviews the
  diff (dual sign-off), diagnosis feeds the failure taxonomy.

## 6. Datasets & models
- **artifact**(id, r2_key, sha256, bytes, kind, created_at) — immutable.
- **dataset_snapshot**(id, name, purpose, created_at, code_commit,
  manifest_artifact_id) — manifest lists exact decision ids, extraction
  ids, region ids, artifact hashes, exclusions (incl. CONFIRMED NEGATIVES,
  which are first-class training data).
- **model_version**(id, name, dataset_snapshot_id, training_config_json,
  model_artifact_id, created_at) + **evaluation_run**(id, model_version_id,
  dataset_snapshot_id, metrics_json, report_artifact_id).
- Splits are by design_family, never by permit/page.

## 7. Computed, never stored
Current stage per building; Work Queue lane membership; current accepted
label per page; tier/capability badges; keep/drop; ready-for-geometry;
ready-for-dataset. All are views over decisions so stored state can't
drift. Stages are parallel evidence tracks (labels track, schedule track,
geometry track), not one strict ladder.

## 8. Workbench IA (locked from round 1-2)
Global: Work Queue (lanes = blocking stage) · Buildings (library, search
by address/name) · Datasets · Models · Pipeline (ops health only).
Building: Summary · Source Files · Page Review (labels+flags+sheet no+
regions) · Rooms & Finishes (source image beside extracted table) ·
Geometry Review (run card / canvas toggles / plain-language issue queue /
exception-first) · Activity (meaning-changing events only; machine noise
grouped; overrides carry a short reason). Customer takeoff preview lives
behind a separate "product preview" link.

## 9. Pilot protocol (10 diverse buildings)
Bank 14-11290 (layered simple) · 26-10321 (layered office) · 13-44121
(refile family + revisions) · 13-27145 St. Andrew's (multi-viewport
hybrid) · 24-06748 (area truth + known geometry failure) · 26-05332
(flattened + 68-room key) · 20-29653 (multi-unit truth) · 25-33341 (known
.3D failure) · 1 dense retail/restaurant from roster · 1 never-seen-firm
new arrival. Blind-label ~10% sample before machine suggestions shown;
random re-review of a small % of human decisions; founder confusion gets
logged as process defects. Schema/process may be revised through building
10 — nothing locks after building 1.

## 10. Build slices
S1: identity tables + backfill from legacy (permits/documents/page_label/
verdicts CSVs) + thin Page Review & Region confirm on V2. S2: Rooms &
Finishes + semantic extraction queue. S3: Geometry Review + correction
capture. S4: dataset snapshots + model report card on V2. Legacy tables
remain read-only sources; nothing deleted.
