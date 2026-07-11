-- v2 schema — new Postgres schema on same Neon DB, per SCHEMA_V2.md v1.4.
-- Legacy `estimate.*` untouched/read-only. Idempotent: safe to re-run.

CREATE SCHEMA IF NOT EXISTS v2;
SET search_path TO v2;

-- ============================================================ §1 Identity

CREATE TABLE IF NOT EXISTS v2.permit (
  id BIGSERIAL PRIMARY KEY,
  permit_num TEXT NOT NULL UNIQUE,
  city_description TEXT,
  city_sqft NUMERIC,
  filed_date DATE,
  issued_date DATE,
  address_raw TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS v2.building (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  address TEXT,
  firm_id BIGINT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS v2.permit_building (
  permit_id BIGINT NOT NULL REFERENCES v2.permit(id),
  building_id BIGINT NOT NULL REFERENCES v2.building(id),
  role TEXT,
  PRIMARY KEY (permit_id, building_id)
);

CREATE TABLE IF NOT EXISTS v2.level (
  id BIGSERIAL PRIMARY KEY,
  building_id BIGINT NOT NULL REFERENCES v2.building(id),
  name TEXT NOT NULL,
  ordinal INT,
  UNIQUE (building_id, name)
);

CREATE TABLE IF NOT EXISTS v2.plan_set (
  id BIGSERIAL PRIMARY KEY,
  building_id BIGINT NOT NULL REFERENCES v2.building(id),
  revision_label TEXT,
  effective_date DATE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS v2.document (
  id BIGSERIAL PRIMARY KEY,
  onestop_doc_id BIGINT NOT NULL UNIQUE,
  permit_id BIGINT REFERENCES v2.permit(id),
  filename TEXT,
  filed_date DATE,
  sha256 TEXT,
  kind_hint TEXT,
  supersedes_document_id BIGINT REFERENCES v2.document(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS v2.plan_set_document (
  plan_set_id BIGINT NOT NULL REFERENCES v2.plan_set(id),
  document_id BIGINT NOT NULL REFERENCES v2.document(id),
  role TEXT,
  PRIMARY KEY (plan_set_id, document_id)
);

CREATE TABLE IF NOT EXISTS v2.page (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES v2.document(id),
  pdf_page_index INT NOT NULL,
  printed_page_no TEXT,
  width_pt NUMERIC,
  height_pt NUMERIC,
  sha256_source_page TEXT,
  UNIQUE (document_id, pdf_page_index)
);

CREATE TABLE IF NOT EXISTS v2.region (
  id BIGSERIAL PRIMARY KEY,
  page_id BIGINT NOT NULL REFERENCES v2.page(id),
  kind TEXT NOT NULL CHECK (kind IN ('plan_viewport','schedule_table','legend','detail','other')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS v2.space (
  id BIGSERIAL PRIMARY KEY,
  building_id BIGINT NOT NULL REFERENCES v2.building(id),
  level_id BIGINT REFERENCES v2.level(id),
  code TEXT,
  name TEXT,
  kind TEXT CHECK (kind IN ('room','open_zone','corridor','material_zone')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS v2.space_source_link (
  id BIGSERIAL PRIMARY KEY,
  space_id BIGINT NOT NULL REFERENCES v2.space(id),
  source_type TEXT NOT NULL CHECK (source_type IN ('schedule_row','label_anchor','polygon_prediction','region','takeoff_item')),
  source_id BIGINT NOT NULL,
  link_decision_id BIGINT -- FK added below after human_decision exists
);

-- ============================================================ §2 Leakage & provenance

CREATE TABLE IF NOT EXISTS v2.design_family (
  id BIGSERIAL PRIMARY KEY,
  name TEXT
);

CREATE TABLE IF NOT EXISTS v2.design_family_member (
  family_id BIGINT NOT NULL REFERENCES v2.design_family(id),
  member_type TEXT NOT NULL CHECK (member_type IN ('document','page','region')),
  member_id BIGINT NOT NULL,
  PRIMARY KEY (family_id, member_type, member_id)
);

CREATE TABLE IF NOT EXISTS v2.clustering_run (
  id BIGSERIAL PRIMARY KEY,
  method TEXT,
  version TEXT,
  code_commit TEXT,
  config_hash TEXT,
  input_snapshot_hash TEXT,
  assignment_artifact_id BIGINT, -- FK added below after artifact exists
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS v2.leakage_group (
  id BIGSERIAL PRIMARY KEY,
  clustering_run_id BIGINT REFERENCES v2.clustering_run(id)
);

CREATE TABLE IF NOT EXISTS v2.leakage_group_member (
  leakage_group_id BIGINT NOT NULL REFERENCES v2.leakage_group(id),
  member_type TEXT NOT NULL CHECK (member_type IN ('document','page','region')),
  member_id BIGINT NOT NULL,
  PRIMARY KEY (leakage_group_id, member_type, member_id)
);

-- ============================================================ §3 Extraction

CREATE TABLE IF NOT EXISTS v2.extraction (
  id BIGSERIAL PRIMARY KEY,
  page_id BIGINT NOT NULL REFERENCES v2.page(id),
  tier TEXT NOT NULL CHECK (tier IN ('cheap','heavy','semantic')),
  extractor_name TEXT,
  extractor_version TEXT,
  config_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','defective')),
  manifest_json JSONB
);

-- ============================================================ §4 Claims & decisions

CREATE TABLE IF NOT EXISTS v2.taxonomy_version (
  id BIGSERIAL PRIMARY KEY,
  version TEXT NOT NULL UNIQUE,
  categories JSONB NOT NULL,
  flags JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS v2.claim_definition (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  allowed_target_types TEXT[] NOT NULL,
  value_schema JSONB,
  taxonomy_version TEXT REFERENCES v2.taxonomy_version(version),
  resolution TEXT NOT NULL DEFAULT 'single' CHECK (resolution IN ('single','multi')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS v2.machine_observation (
  id BIGSERIAL PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id BIGINT NOT NULL,
  claim TEXT NOT NULL REFERENCES v2.claim_definition(name),
  value_json JSONB NOT NULL,
  source TEXT NOT NULL,
  source_version TEXT,
  score_raw NUMERIC,
  score_type TEXT,
  calibration_version TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mo_target ON v2.machine_observation(target_type, target_id, claim);

CREATE TABLE IF NOT EXISTS v2.human_decision (
  id BIGSERIAL PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id BIGINT NOT NULL,
  claim TEXT NOT NULL REFERENCES v2.claim_definition(name),
  value_json JSONB NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('human','importer','system')),
  actor_id TEXT,
  original_source TEXT,
  binding BOOLEAN NOT NULL DEFAULT TRUE,
  decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  taxonomy_version TEXT REFERENCES v2.taxonomy_version(version),
  blind BOOLEAN NOT NULL DEFAULT FALSE,
  note TEXT
);
CREATE INDEX IF NOT EXISTS idx_hd_target ON v2.human_decision(target_type, target_id, claim);

-- Append-only, purpose-specific qualification ledger. Missing row = denied.
CREATE TABLE IF NOT EXISTS v2.evidence_eligibility_event (
  id BIGSERIAL PRIMARY KEY,
  subject_type TEXT NOT NULL CHECK (subject_type IN
    ('machine_observation','human_decision','extraction','schedule_row','geometry_run','artifact')),
  subject_id BIGINT NOT NULL,
  purpose TEXT NOT NULL CHECK (purpose IN
    ('boundary_train','table_parser_train','sf_eval','demo','page_label_train','pilot_truth')),
  eligible BOOLEAN NOT NULL,
  reason_code TEXT NOT NULL,
  manifest_version TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('human','importer','system')),
  actor_id TEXT,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_eligibility_subject
  ON v2.evidence_eligibility_event(subject_type, subject_id, purpose, id DESC);

CREATE OR REPLACE VIEW v2.effective_evidence_eligibility AS
SELECT DISTINCT ON (subject_type, subject_id, purpose)
  id, subject_type, subject_id, purpose, eligible, reason_code,
  manifest_version, actor_type, actor_id, note, created_at
FROM v2.evidence_eligibility_event
ORDER BY subject_type, subject_id, purpose, id DESC;

CREATE OR REPLACE FUNCTION v2.reject_eligibility_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'v2.evidence_eligibility_event is append-only';
END $$;

DROP TRIGGER IF EXISTS evidence_eligibility_append_only ON v2.evidence_eligibility_event;
CREATE TRIGGER evidence_eligibility_append_only
BEFORE UPDATE OR DELETE ON v2.evidence_eligibility_event
FOR EACH ROW EXECUTE FUNCTION v2.reject_eligibility_mutation();

ALTER TABLE v2.space_source_link
  ADD CONSTRAINT fk_ssl_decision FOREIGN KEY (link_decision_id) REFERENCES v2.human_decision(id);

CREATE TABLE IF NOT EXISTS v2.decision_relation (
  id BIGSERIAL PRIMARY KEY,
  from_decision_id BIGINT NOT NULL REFERENCES v2.human_decision(id),
  to_decision_id BIGINT NOT NULL REFERENCES v2.human_decision(id),
  relation TEXT NOT NULL CHECK (relation IN ('supersedes','disputes','adjudicates')),
  actor_type TEXT,
  actor_id TEXT,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (from_decision_id <> to_decision_id),
  UNIQUE (from_decision_id, to_decision_id, relation)
);

CREATE TABLE IF NOT EXISTS v2.geometry_annotation (
  id BIGSERIAL PRIMARY KEY,
  human_decision_id BIGINT NOT NULL REFERENCES v2.human_decision(id),
  original_geom_json JSONB,
  corrected_geom_json JSONB,
  action TEXT,
  failure_type TEXT,
  affected_segments JSONB,
  material_before TEXT,
  material_after TEXT,
  split_merge_links JSONB
);

-- ============================================================ §5 Rooms & Finishes

CREATE TABLE IF NOT EXISTS v2.schedule_row (
  id BIGSERIAL PRIMARY KEY,
  region_id BIGINT NOT NULL REFERENCES v2.region(id),
  extraction_id BIGINT NOT NULL REFERENCES v2.extraction(id),
  row_index INT NOT NULL,
  raw_values_json JSONB,
  source_cells_json JSONB
);

-- ============================================================ §6 Geometry

CREATE TABLE IF NOT EXISTS v2.geometry_run (
  id BIGSERIAL PRIMARY KEY,
  region_id BIGINT REFERENCES v2.region(id),
  plan_set_id BIGINT REFERENCES v2.plan_set(id),
  run_no INT,
  manifest_json JSONB,
  status TEXT NOT NULL DEFAULT 'imported'
);

CREATE TABLE IF NOT EXISTS v2.polygon_prediction (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES v2.geometry_run(id),
  geom_json JSONB,
  space_id BIGINT REFERENCES v2.space(id),
  label_match TEXT,
  area_sf NUMERIC,
  product_action TEXT,
  flags JSONB
);

-- ============================================================ §7 Datasets & models

CREATE TABLE IF NOT EXISTS v2.artifact (
  id BIGSERIAL PRIMARY KEY,
  r2_key TEXT,
  sha256 TEXT,
  bytes BIGINT,
  kind TEXT
);

ALTER TABLE v2.clustering_run
  ADD CONSTRAINT fk_cr_artifact FOREIGN KEY (assignment_artifact_id) REFERENCES v2.artifact(id);

CREATE TABLE IF NOT EXISTS v2.dataset_snapshot (
  id BIGSERIAL PRIMARY KEY,
  name TEXT,
  purpose TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  code_commit TEXT,
  clustering_run_id BIGINT REFERENCES v2.clustering_run(id),
  clustering_assignment_artifact_id BIGINT REFERENCES v2.artifact(id),
  manifest_artifact_id BIGINT REFERENCES v2.artifact(id)
);

CREATE TABLE IF NOT EXISTS v2.dataset_item (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id BIGINT NOT NULL REFERENCES v2.dataset_snapshot(id),
  split_role TEXT NOT NULL CHECK (split_role IN ('train','val','frozen_test','calibration','canary')),
  plan_set_id BIGINT REFERENCES v2.plan_set(id),
  region_id BIGINT REFERENCES v2.region(id)
);

CREATE TABLE IF NOT EXISTS v2.dataset_item_extraction (
  item_id BIGINT NOT NULL REFERENCES v2.dataset_item(id),
  extraction_id BIGINT NOT NULL REFERENCES v2.extraction(id),
  PRIMARY KEY (item_id, extraction_id)
);

CREATE TABLE IF NOT EXISTS v2.dataset_item_decision (
  item_id BIGINT NOT NULL REFERENCES v2.dataset_item(id),
  decision_id BIGINT NOT NULL REFERENCES v2.human_decision(id),
  PRIMARY KEY (item_id, decision_id)
);

CREATE TABLE IF NOT EXISTS v2.dataset_item_artifact (
  item_id BIGINT NOT NULL REFERENCES v2.dataset_item(id),
  artifact_id BIGINT NOT NULL REFERENCES v2.artifact(id),
  PRIMARY KEY (item_id, artifact_id)
);

CREATE TABLE IF NOT EXISTS v2.model_version (
  id BIGSERIAL PRIMARY KEY,
  name TEXT,
  training_dataset_snapshot_id BIGINT REFERENCES v2.dataset_snapshot(id),
  config JSONB,
  model_artifact_id BIGINT REFERENCES v2.artifact(id)
);

CREATE TABLE IF NOT EXISTS v2.evaluation_run (
  id BIGSERIAL PRIMARY KEY,
  model_version_id BIGINT REFERENCES v2.model_version(id),
  eval_dataset_snapshot_id BIGINT REFERENCES v2.dataset_snapshot(id),
  eval_config JSONB,
  metrics_json JSONB,
  report_artifact BIGINT REFERENCES v2.artifact(id)
);

-- ============================================================ §8 Jobs

CREATE TABLE IF NOT EXISTS v2.job (
  id BIGSERIAL PRIMARY KEY,
  type TEXT NOT NULL,
  target_type TEXT,
  target_id BIGINT,
  requested_version TEXT,
  idempotency_key TEXT UNIQUE,
  status TEXT NOT NULL DEFAULT 'queued',
  attempts INT NOT NULL DEFAULT 0,
  queued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  result_ref TEXT,
  error_summary TEXT
);

-- ============================================================ Seed data

INSERT INTO v2.taxonomy_version (version, categories, flags)
VALUES (
  'v2.0',
  '["floor_plan","finish_plan","finish_schedule","demo_plan","reflected_ceiling","furniture_plan","site_plan","elevation_section","detail","schedule_other","structural","mep","life_safety","cover_index","specs_notes","other"]'::jsonb,
  '["multiple_viewports","contains_area_table","scale_visible","finish_codes_visible","table_present","room_labels_visible","dimensions_visible","possible_duplicate"]'::jsonb
)
ON CONFLICT (version) DO NOTHING;
-- NOTE: taxonomy has 16 entries (15 categories + "other" per label-pages skill,
-- which lists "other" as the 15th/catch-all category — 15 total incl. other).
-- Flags: 8 chosen per mission spec judgment call — see report.

INSERT INTO v2.claim_definition (name, allowed_target_types, value_schema, taxonomy_version, resolution, notes) VALUES
  ('page_category', ARRAY['page'], '{"type":"string","enum_ref":"taxonomy_version.categories"}'::jsonb, 'v2.0', 'single', 'Primary page category from the 15-category taxonomy'),
  ('page_flags', ARRAY['page'], '{"type":"array","items":"string","enum_ref":"taxonomy_version.flags"}'::jsonb, 'v2.0', 'multi', 'Independent boolean flags on a page'),
  ('sheet_number', ARRAY['page'], '{"type":"string"}'::jsonb, NULL, 'single', 'Title-block sheet number, e.g. A-101'),
  ('sheet_title', ARRAY['page'], '{"type":"string"}'::jsonb, NULL, 'single', 'Title-block sheet title verbatim'),
  ('region_geometry', ARRAY['region'], '{"type":"object","properties":{"x":"number","y":"number","w":"number","h":"number","units":"string"}}'::jsonb, NULL, 'single', 'Region bounding-box proposal/decision'),
  ('region_approval', ARRAY['region'], '{"type":"string","enum":["usable","partial","unusable","wrong_viewport","wrong_scale"]}'::jsonb, NULL, 'single', 'Region-scoped usability verdict'),
  ('level_assignment', ARRAY['page','region'], '{"type":"object","properties":{"level_id":"integer"}}'::jsonb, NULL, 'single', 'Assigns a page/region to a building level'),
  ('identity_link', ARRAY['space'], '{"type":"object","properties":{"linked_space_id":"integer","plan_set_id":"integer"}}'::jsonb, NULL, 'single', 'Asserts a space identity link across plan-set revisions'),
  ('schedule_row_field', ARRAY['schedule_row'], '{"type":"object","properties":{"field":"string","value":"string"}}'::jsonb, NULL, 'single', 'Confirmed value for one field of a schedule row'),
  ('room_verdict', ARRAY['polygon_prediction','space'], '{"type":"string","enum":["correct","missed","merged","split","fake","wrong_label","open_zone","boundary_fix"]}'::jsonb, NULL, 'single', 'Space/polygon-scoped geometry verdict'),
  ('region_geometry_verdict', ARRAY['region'], '{"type":"string","enum":["usable","partial","unusable","wrong_viewport","wrong_scale"]}'::jsonb, NULL, 'single', 'Alias/region verdict used by geometry review flow'),
  ('run_verdict', ARRAY['geometry_run'], '{"type":"string","enum":["approved_training","approved_eval","diagnostic","rejected"]}'::jsonb, NULL, 'single', 'Run-level verdict'),
  ('dataset_eligibility_boundary', ARRAY['region','plan_set'], '{"type":"boolean"}'::jsonb, NULL, 'single', 'Eligible for boundary/geometry training set'),
  ('dataset_eligibility_table_parser', ARRAY['region','page'], '{"type":"boolean"}'::jsonb, NULL, 'single', 'Eligible for table-parser training set'),
  ('dataset_eligibility_sf_eval', ARRAY['plan_set','region'], '{"type":"boolean"}'::jsonb, NULL, 'single', 'Eligible for square-footage eval set'),
  ('dataset_eligibility_demo', ARRAY['page','plan_set'], '{"type":"boolean"}'::jsonb, NULL, 'single', 'Eligible for demo/showcase dataset')
ON CONFLICT (name) DO NOTHING;
