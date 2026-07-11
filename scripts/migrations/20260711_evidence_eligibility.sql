BEGIN;

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

COMMIT;
