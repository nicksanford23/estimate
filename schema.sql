-- estimate.db schema (SQLite). Initialize with:
--   sqlite3 data/estimate.db < schema.sql
-- Safe to re-run (IF NOT EXISTS everywhere).

PRAGMA journal_mode = WAL;

-- One row per downloaded file from One Stop.
CREATE TABLE IF NOT EXISTS document (
    id              INTEGER PRIMARY KEY,
    permit_num      TEXT NOT NULL,             -- joins to data/nola_permits_commercial.csv
    onestop_doc_id  INTEGER NOT NULL UNIQUE,   -- GetDocument.aspx?DocID=
    filename        TEXT NOT NULL,
    sha256          TEXT,
    bytes           INTEGER,
    page_count      INTEGER,
    storage_path    TEXT,                      -- local path to the PDF
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- pending -> downloaded -> rendered | error
    error           TEXT,
    downloaded_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_document_status ON document(status);
CREATE INDEX IF NOT EXISTS idx_document_permit ON document(permit_num);

-- One row per rendered page image.
CREATE TABLE IF NOT EXISTS page (
    id              INTEGER PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES document(id),
    page_index      INTEGER NOT NULL,          -- 0-based
    image_path      TEXT NOT NULL,
    width_px        INTEGER,
    height_px       INTEGER,
    has_vector_text INTEGER,                   -- 1 = CAD-export PDF, 0 = scan
    status          TEXT NOT NULL DEFAULT 'rendered',
                    -- rendered -> labeled
    UNIQUE (document_id, page_index)
);
CREATE INDEX IF NOT EXISTS idx_page_status ON page(status);

-- Append-only labels with provenance. Never UPDATE; corrections are new rows.
-- "Current truth" for a page = the human row if any, else the
-- highest-confidence model row (see v_page_truth below).
CREATE TABLE IF NOT EXISTS page_label (
    id          INTEGER PRIMARY KEY,
    page_id     INTEGER NOT NULL REFERENCES page(id),
    source      TEXT NOT NULL,     -- 'claude-code' | 'codex' | 'human' | 'probe-v1'
    category    TEXT NOT NULL,     -- taxonomy below
    keep        INTEGER NOT NULL,  -- 1 if category in the takeoff-relevant set
    confidence  REAL NOT NULL,     -- 0..1
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_label_page ON page_label(page_id);

-- CLIP (or other) embeddings, one per page per model.
CREATE TABLE IF NOT EXISTS embedding (
    page_id     INTEGER NOT NULL REFERENCES page(id),
    model_name  TEXT NOT NULL,     -- e.g. 'clip-vit-b-32'
    dim         INTEGER NOT NULL,
    vector      BLOB NOT NULL,     -- float32 array, little-endian
    PRIMARY KEY (page_id, model_name)
);

CREATE TABLE IF NOT EXISTS training_run (
    id           INTEGER PRIMARY KEY,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    description  TEXT,
    n_train      INTEGER,
    n_eval       INTEGER,
    metrics_json TEXT,
    artifact_path TEXT
);

-- Current-truth view: human label wins, else best model label.
CREATE VIEW IF NOT EXISTS v_page_truth AS
SELECT pl.*
FROM page_label pl
JOIN (
    SELECT page_id,
           MAX(CASE WHEN source = 'human' THEN 2 ELSE 1 END) AS rank
    FROM page_label GROUP BY page_id
) best ON best.page_id = pl.page_id
WHERE (CASE WHEN pl.source = 'human' THEN 2 ELSE 1 END) = best.rank
GROUP BY pl.page_id
HAVING pl.confidence = MAX(pl.confidence);

-- Taxonomy (category values):
--   floor_plan, finish_plan, finish_schedule, demo_plan,        <- keep = 1
--   reflected_ceiling, furniture_plan, site_plan,
--   elevation_section, detail, schedule_other, structural,
--   mep, cover_index, specs_notes, other                        <- keep = 0
