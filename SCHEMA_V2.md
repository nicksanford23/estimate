# V2 Schema & Process Constitution — v1.1 (GPT-approved pending 6 amendments, now incorporated)

*Founder + Claude + GPT, three consultation rounds, 2026-07-10. Locked
principle: sources are immutable; extractions, regions, and geometry are
versioned; human decisions explicitly supersede earlier decisions; logical
spaces connect plan labels, schedules, and polygons; dataset eligibility is
purpose-specific; training and evaluation use frozen leakage-safe snapshots.*

## 0. Conventions
- Postgres (Neon, ours) = identities, decisions, links. R2 = immutable
  artifacts, content-addressed. CSV/JSONL = exports only. Parquet for bulk
  words/segments/cells. GeoJSON-style JSON for geometry.
- Human decisions APPEND-ONLY with explicit supersession (see §4).
- Machine output = candidate. Human decision = best current truth (blind
  audits + sampled re-review stay; humans err too).
- Confirmation marks ELIGIBLE; queued versioned jobs do the work (§9).

## 1. Identity (amended: permit ≠ building ≠ plan-set)
- **permit**(id, permit_num, city_description, city_sqft, filed/issued
  dates, address_raw) — the city record, verbatim, clearly theirs.
- **building**(id, name, address, firm_id nullable, notes) — physical
  building, independent of any one permit.
- **permit_building**(permit_id, building_id, role) — MANY-TO-MANY
  (v1.2): one permit can cover several buildings; one building accrues
  permits over time.
- **level**(id, building_id, name, ordinal) — floor/wing context (v1.2):
  Room 101 repeats across levels/units; spaces attach to a level.
- **plan_set**(id, building_id, revision_label, effective_date, notes) —
  a coherent submission/revision: "these floor plans + this schedule +
  this addendum were valid together." Geometry runs and datasets point at
  plan_set revisions, not loose documents.
- **plan_set_document**(plan_set_id, document_id, role).
- **document**(id, onestop_doc_id, permit_id, filename, filed_date,
  sha256, kind_hint, supersedes_document_id nullable).
- **page**(id, document_id, pdf_page_index, printed_page_no nullable,
  width_pt, height_pt, sha256_source_page) — physical identity ONLY.
  Renders live in extraction artifacts (§3); sheet_number/title are
  machine_observations resolved by human_decision (cached resolved values
  are views/materializations, never competing truth).
- **region**(id, page_id, kind: plan_viewport|schedule_table|legend|
  detail|other, created_at) — STABLE IDENTITY ONLY (amended). Geometry of
  the region is versioned: proposals are machine_observations
  (claim=region_geometry), accepted boxes are human_decisions; current box
  = resolved claim. Extractions and runs record the exact region-geometry
  decision id they used. UI: Approve / Redraw / Use-full-page (redraw
  beats handle-dragging). Rectangles only in pilot.
- **space**(id, building_id, level_id, code, name, kind: room|open_zone|
  corridor|material_zone, notes) — THE CANONICAL LOGICAL ROOM. Identity
  across plan-set revisions is asserted by an explicit identity_link
  human_decision (v1.2) — never auto-assumed from code/name matching.
- **space_source_link**(space_id, source_type: schedule_row|label_anchor|
  polygon_prediction|region|takeoff_item, source_id, link_decision_id) —
  THE authoritative connection of schedule truth, plan labels, geometry,
  and customer quantities. polygon_prediction.space_id is a derived cache
  of this table only, never independently authoritative (v1.2).

## 2. Leakage & provenance groups (amended)
- **design_family**(id, name) + **design_family_member**(family_id,
  member_type: document|page|region, member_id) — duplication tracked at
  the level it occurs, not per building.
- **leakage_group**(id, clustering_run_id) + members — the CONSERVATIVE
  union of: exact doc hashes, perceptual page matches, region-similarity,
  refiles, known standard designs, manual links. RULE: all members of a
  leakage_group share one dataset split. **clustering_run**(id, method,
  version, code_commit, config_hash, input_snapshot_hash,
  assignment_artifact_id, created_at) — similarity logic evolves AND the
  same version regroups when inputs change (v1.3), so runs pin
  code+config+input hashes and their output assignment artifact; dataset
  snapshots pin clustering_run_id + assignment artifact hash.
  Architecture FIRM tracked separately (building.firm_id via title-block
  evidence) — firm holdouts measure cross-firm generalization; family and
  firm are different dimensions.

## 3. Extraction (two tiers, versioned; amended cheap/heavy split)
- **extraction**(id, page_id, tier: cheap|heavy|semantic, extractor_name,
  extractor_version, config_hash, created_at, status: active|superseded|
  defective, manifest_json, artifacts[]) — never overwritten; datasets pin
  exact ids; superseded/defective flags but no deletion while referenced.
  - CHEAP (every page at ingestion): render artifact(s), page dims +
    transform, words+bboxes, vector/image presence summary, layer-name
    inventory, source hash.
  - HEAVY (geometry-candidate pages only — machine-suggested relevant,
    human-confirmed plan, or audit-selected): full normalized segment
    parquet, layer properties, connectivity, derived line features.
  - SEMANTIC (post confirmation, queued): confirmed page type + sheet
    no/title, accepted region geometries + transforms, schedule cell grid
    (text+bbox+row/col) per schedule region, room-label anchors per plan
    region; pins the base extraction ids used.
- Renders: multiple allowed (DPI/engine versions) as extraction artifacts;
  page table never holds "the" render. Crops regenerated from coords, not
  stored (hot cache only).

## 4. Claims & decisions (amended: supersession + registry)
- **claim_definition**(name, allowed_target_types, value_schema,
  taxonomy_version nullable, resolution: single|multi, notes) — the
  registry; no unregistered claim_types (junk-drawer guard). Includes
  purpose-specific eligibility claims: dataset_eligibility_boundary,
  dataset_eligibility_table_parser, dataset_eligibility_sf_eval,
  dataset_eligibility_demo.
- **machine_observation**(id, target_type, target_id, claim, value_json,
  source, source_version, score_raw, score_type, calibration_version,
  created_at) — confidences typed per source, never cross-compared raw.
- **human_decision**(id, target_type, target_id, claim, value_json,
  actor_type (human|importer|system), actor_id, original_source nullable
  (v1.2: imports preserve who originally asserted it), binding bool
  (v1.3: imported/legacy rows are binding=false — visible as reference,
  NEVER resolve as current truth; only fresh binding decisions do),
  decided_at, taxonomy_version, blind bool, note) — rows NEVER updated.
- **decision_relation**(id, from_decision_id, to_decision_id, relation:
  supersedes|disputes|adjudicates, actor_type, actor_id, note,
  created_at) — APPEND-ONLY graph; status (active/superseded/disputed)
  DERIVED by walking relations; adjudications reference any number of
  conflicting decisions. INVARIANTS (v1.3): no self-links (CHECK
  from<>to); one relation kind per ordered pair (unique constraint);
  supersession graph must stay acyclic — enforced at write time by the
  application (walk-before-insert), violations rejected.
- AI-agent labels are machine_observations, never human_decisions — even
  when imported from legacy files (v1.2).
- Geometry corrections: **geometry_annotation** holds the rich payload
  (original+corrected geometry, action, failure_type, affected segments,
  label/material before+after, split/merge polygon links) and ALWAYS links
  to its human_decision (the accepted claim). One truth system; geometry
  table carries specialty payload only (amended).
- Page labeling: ONE primary category + independent flags; keep/drop
  derived, read-only with reason. **taxonomy_version** + **taxonomy_map**
  (rename/merge auto-map; splits go to a review queue).
- Claude's review role (amended): NOT a mandatory co-signer. Triggered
  review on: uncertain corrections, split/merge cases, random QA sample,
  large quantity deltas, schedule-contradicting geometry. Founder is final
  authority.

## 5. Rooms & Finishes
- **schedule_row**(id, region_id, extraction_id, row_index, raw values
  incl. source_cells_json) — IMMUTABLE machine extraction. Confirmed
  values live in human_decisions per field; the resolved view shows
  raw + accepted + provenance side by side (amended). Confirmed rows link
  to canonical **space** — where schedule truth meets geometry truth.

## 6. Geometry
- **geometry_run**(id, region_id, plan_set_id, run_no, manifest_json,
  status) — manifest freezes: source hashes, extraction ids + artifact
  hashes, boundary engine/model + model-file hash, feature version, code
  commit, full config, layer-norm map version, scale value/units/evidence,
  transform, gap rules, filters, seed, container versions, output hashes.
- **polygon_prediction**(id, run_id, geom_json, space_id nullable,
  label_match, area_sf, product_action, flags).
- Verdicts are REGION-scoped (amended): region {usable|partial|unusable|
  wrong_viewport|wrong_scale}; space/polygon {correct|missed|merged|split|
  fake|wrong_label|open_zone|boundary_fix}; run {approved_training|
  approved_eval|diagnostic|rejected}. Page summaries are UI conveniences.

## 7. Datasets & models (amended roles)
- **artifact**(id, r2_key, sha256, bytes, kind).
- **dataset_snapshot**(id, name, purpose, created_at, code_commit,
  clustering_run_id, clustering_assignment_artifact_id (v1.3: pins the
  exact grouping OUTPUT hash, not just the method version),
  manifest_artifact_id).
- **dataset_item**(id, snapshot_id, split_role {train|val|frozen_test|
  calibration|canary}, plan_set_id, region_id) with normalized child
  link tables (v1.3, real FK integrity — no arrays):
  **dataset_item_extraction**(item_id, extraction_id),
  **dataset_item_decision**(item_id, decision_id),
  **dataset_item_artifact**(item_id, artifact_id). The manifest artifact
  additionally carries the hashed flat listing for external
  reproducibility.
- **model_version**(id, name, training_dataset_snapshot_id, config,
  model_artifact_id) + **evaluation_run**(id, model_version_id,
  eval_dataset_snapshot_id, eval_config, metrics_json, report_artifact).

## 8. Jobs (amended: explicit queue)
- **job**(id, type, target_type, target_id, requested_version,
  idempotency_key unique, status, attempts, queued_at, started_at,
  finished_at, result_ref, error_summary) — answers "why isn't this
  processed yet"; idempotency prevents duplicate work from repeat clicks.

## 9. Computed, never stored
Stage per building/track; Work Queue lanes; resolved labels/regions/
values; tier badges; keep/drop; eligibility statuses. All views over the
supersession-resolved decision graph. Evidence tracks (labels, schedule,
geometry) are parallel, not one ladder.

## 10. Workbench IA
Global: Work Queue · Buildings · Datasets · Models · Pipeline (health
only). Building: Summary · Source Files · Page Review · Rooms & Finishes ·
Geometry Review · Activity (meaning-changing events; grouped machine
events; override reasons). Product preview separate.

## 11. Pilot protocol (10 diverse buildings — list as v1.0)
Success = the PROCESS works: identity unambiguous, pages/regions
confirmable, schedule truth traceable, failures understandable,
corrections captured structurally, datasets reproducible — NOT every
polygon corrected in every building (deep-correct selected rooms only,
e.g. not all 68 townhouse rooms). Blind-label a SUSTAINABLE sample,
STRATIFIED (v1.2) across predicted keep/drop, hybrid sheets, firms,
low-confidence results, and rare labels — never plain-random, or junk
pages dominate the audit. Log founder confusion as process defects;
schema may evolve through building 10. Legacy backfill: Nick's own UI
verdicts import as human_decisions (original actor preserved, no active
adjudication — pilot buildings re-confirmed fresh); agent labels import
as machine_observations.

## 12. Founder decisions (Nick to answer before lock)
1. Top-level operational object in the Buildings UI (recommend: building,
   with permit/plan-set visible inside).
2. Space identity across revisions (recommend: same space, new geometry).
3. Actor model: who makes binding decisions (today: Nick; record actor
   types now).
4. Blind-audit rate he can sustain (recommend: 5% consistently over 10%
   aspirationally).
5. Which stages require HIS review vs delegable (labels/regions/schedule/
   geometry/eligibility).
6. Eligibility policies per purpose (boundary-training vs SF-eval vs demo
   vs bid-truth) — named rules, drafted by Claude, approved by Nick.

## 13. Build slices (unchanged, emphasis per GPT)
S1: identity spine (permit/building/plan_set/document/page/region/space)
+ backfill + THIN page review & region confirm. S2: Rooms & Finishes +
semantic extraction queue. S3: Geometry Review + correction capture.
S4: datasets/models views. Legacy stays read-only; nothing deleted.
