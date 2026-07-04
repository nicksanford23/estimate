#!/usr/bin/env python3
"""One-shot cutover: copy estimate.db (SQLite) -> Neon schema `estimate`.

Run ONLY when nothing is writing to SQLite (wave boundary). Idempotent-ish:
drops and recreates the estimate schema, so re-running replaces the copy.
"""
import os
import sqlite3

import psycopg2
from psycopg2.extras import execute_values

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {}
with open(os.path.join(ROOT, ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            ENV[k] = v

DDL = """
DROP SCHEMA IF EXISTS estimate CASCADE;
CREATE SCHEMA estimate;
CREATE TABLE estimate.document (
    id              bigint PRIMARY KEY,
    permit_num      text NOT NULL,
    onestop_doc_id  bigint NOT NULL UNIQUE,
    filename        text NOT NULL,
    sha256          text,
    bytes           bigint,
    page_count      int,
    storage_path    text,
    status          text NOT NULL DEFAULT 'pending',
    error           text,
    downloaded_at   text
);
CREATE INDEX ON estimate.document(status);
CREATE INDEX ON estimate.document(permit_num);
CREATE TABLE estimate.page (
    id              bigint PRIMARY KEY,
    document_id     bigint NOT NULL REFERENCES estimate.document(id),
    page_index      int NOT NULL,
    image_path      text NOT NULL,
    width_px        int,
    height_px       int,
    has_vector_text int,
    status          text NOT NULL DEFAULT 'rendered',
    UNIQUE (document_id, page_index)
);
CREATE INDEX ON estimate.page(status);
CREATE TABLE estimate.page_label (
    id          bigint PRIMARY KEY,
    page_id     bigint NOT NULL REFERENCES estimate.page(id),
    source      text NOT NULL,
    category    text NOT NULL,
    keep        int NOT NULL,
    confidence  real NOT NULL,
    created_at  text NOT NULL DEFAULT now()::text,
    sheet_title text,
    scale_visible int,
    finish_codes_visible int,
    table_present int,
    room_labels_visible int,
    dimensions_visible int,
    flag_reason text,
    evidence    text
);
CREATE INDEX ON estimate.page_label(page_id);
CREATE SEQUENCE estimate.document_id_seq OWNED BY estimate.document.id;
CREATE SEQUENCE estimate.page_id_seq OWNED BY estimate.page.id;
CREATE SEQUENCE estimate.page_label_id_seq OWNED BY estimate.page_label.id;
ALTER TABLE estimate.document ALTER id SET DEFAULT nextval('estimate.document_id_seq');
ALTER TABLE estimate.page ALTER id SET DEFAULT nextval('estimate.page_id_seq');
ALTER TABLE estimate.page_label ALTER id SET DEFAULT nextval('estimate.page_label_id_seq');
"""

COPIES = [
    ("document", "id, permit_num, onestop_doc_id, filename, sha256, bytes, "
                 "page_count, storage_path, status, error, downloaded_at"),
    ("page", "id, document_id, page_index, image_path, width_px, height_px, "
             "has_vector_text, status"),
    ("page_label", "id, page_id, source, category, keep, confidence, created_at, "
                   "sheet_title, scale_visible, finish_codes_visible, table_present, "
                   "room_labels_visible, dimensions_visible, flag_reason, evidence"),
]


def main():
    lite = sqlite3.connect(os.path.join(ROOT, "data", "estimate.db"))
    pg = psycopg2.connect(ENV["NEON_DATABASE_URL"])
    pg.autocommit = False
    cur = pg.cursor()
    cur.execute(DDL)
    for table, cols in COPIES:
        rows = lite.execute(f"SELECT {cols} FROM {table}").fetchall()
        execute_values(cur, f"INSERT INTO estimate.{table} ({cols}) VALUES %s", rows,
                       page_size=1000)
        cur.execute(f"SELECT setval('estimate.{table}_id_seq', "
                    f"(SELECT COALESCE(MAX(id),0)+1 FROM estimate.{table}), false)")
        print(f"{table}: {len(rows)} rows", flush=True)
    pg.commit()
    for table, _ in COPIES:
        cur.execute(f"SELECT COUNT(*) FROM estimate.{table}")
        print(f"verify {table}: {cur.fetchone()[0]}", flush=True)
    pg.close()
    print("CUTOVER COMPLETE — SQLite is now read-only legacy; "
          "rename data/estimate.db to data/estimate.db.pre-neon after verifying.")


if __name__ == "__main__":
    main()
