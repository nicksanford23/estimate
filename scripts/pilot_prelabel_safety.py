#!/usr/bin/env python3
"""Build the two-building truth inventory and append quarantine denials.

This script never changes source evidence. With --apply-denials it appends one
default-deny eligibility event per inventoried subject/purpose and is idempotent
for this manifest version.
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "pilot_safety"
PERMITS = ("26-10321-RNVN", "24-06748-RNVS")
INVENTORY_VERSION = "truth_inventory_v1"
MANIFEST_VERSION = "pilot_quarantine_manifest_v1"
PURPOSES = (
    "boundary_train",
    "table_parser_train",
    "sf_eval",
    "demo",
    "page_label_train",
    "pilot_truth",
)


def load_env():
    for raw in (ROOT / ".env").read_text().splitlines():
        raw = raw.strip()
        if raw and not raw.startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def fetch(cur, sql, params=()):
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-denials", action="store_true")
    args = parser.parse_args()
    load_env()
    conn = psycopg2.connect(os.environ["NEON_DATABASE_URL"])
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            pages = fetch(cur, """
              SELECT p.permit_num, pg.id, pg.document_id, pg.pdf_page_index,
                     pg.sha256_source_page
              FROM v2.permit p JOIN v2.document d ON d.permit_id=p.id
              JOIN v2.page pg ON pg.document_id=d.id
              WHERE p.permit_num=ANY(%s) ORDER BY p.permit_num,pg.id
            """, (list(PERMITS),))
            observations = fetch(cur, """
              SELECT p.permit_num,mo.id,mo.target_type,mo.target_id,mo.claim,
                     mo.source,mo.source_version,mo.created_at
              FROM v2.permit p JOIN v2.document d ON d.permit_id=p.id
              JOIN v2.page pg ON pg.document_id=d.id
              JOIN v2.machine_observation mo
                ON mo.target_type='page' AND mo.target_id=pg.id
              WHERE p.permit_num=ANY(%s) ORDER BY mo.id
            """, (list(PERMITS),))
            decisions = fetch(cur, """
              SELECT p.permit_num,hd.id,hd.target_type,hd.target_id,hd.claim,
                     hd.actor_type,hd.actor_id,hd.original_source,hd.binding,
                     hd.blind,hd.taxonomy_version,hd.decided_at
              FROM v2.permit p JOIN v2.document d ON d.permit_id=p.id
              JOIN v2.page pg ON pg.document_id=d.id
              JOIN v2.human_decision hd
                ON hd.target_type='page' AND hd.target_id=pg.id
              WHERE p.permit_num=ANY(%s) ORDER BY hd.id
            """, (list(PERMITS),))
            extractions = fetch(cur, """
              SELECT p.permit_num,e.id,e.page_id,e.tier,e.extractor_name,
                     e.extractor_version,e.status,e.created_at
              FROM v2.permit p JOIN v2.document d ON d.permit_id=p.id
              JOIN v2.page pg ON pg.document_id=d.id
              JOIN v2.extraction e ON e.page_id=pg.id
              WHERE p.permit_num=ANY(%s) ORDER BY e.id
            """, (list(PERMITS),))
            schedule_rows = fetch(cur, """
              SELECT p.permit_num,sr.id,sr.region_id,sr.extraction_id,sr.row_index
              FROM v2.permit p JOIN v2.document d ON d.permit_id=p.id
              JOIN v2.page pg ON pg.document_id=d.id
              JOIN v2.region r ON r.page_id=pg.id
              JOIN v2.schedule_row sr ON sr.region_id=r.id
              WHERE p.permit_num=ANY(%s) ORDER BY sr.id
            """, (list(PERMITS),))
            geometry_runs = fetch(cur, """
              SELECT p.permit_num,gr.id,gr.region_id,gr.plan_set_id,gr.run_no,gr.status
              FROM v2.permit p JOIN v2.document d ON d.permit_id=p.id
              JOIN v2.page pg ON pg.document_id=d.id
              JOIN v2.region r ON r.page_id=pg.id
              JOIN v2.geometry_run gr ON gr.region_id=r.id
              WHERE p.permit_num=ANY(%s) ORDER BY gr.id
            """, (list(PERMITS),))

            generated_at = datetime.now(timezone.utc).isoformat()
            inventory = {
                "version": INVENTORY_VERSION,
                "generated_at": generated_at,
                "pilot_permits": list(PERMITS),
                "trusted_semantic_count": 0,
                "policy": "legacy_unverified; diagnostic_only; default deny",
                "pages": pages,
                "machine_observations": observations,
                "human_decisions": decisions,
                "extractions": extractions,
                "schedule_rows": schedule_rows,
                "geometry_runs": geometry_runs,
                "counts": {
                    "pages": len(pages),
                    "machine_observations": len(observations),
                    "human_decisions": len(decisions),
                    "extractions": len(extractions),
                    "schedule_rows": len(schedule_rows),
                    "geometry_runs": len(geometry_runs),
                },
            }
            subjects = (
                [("machine_observation", row["id"]) for row in observations]
                + [("human_decision", row["id"]) for row in decisions]
                + [("extraction", row["id"]) for row in extractions]
                + [("schedule_row", row["id"]) for row in schedule_rows]
                + [("geometry_run", row["id"]) for row in geometry_runs]
            )
            inventory_bytes = json.dumps(inventory, sort_keys=True, default=str).encode()
            manifest = {
                "version": MANIFEST_VERSION,
                "generated_at": generated_at,
                "inventory_version": INVENTORY_VERSION,
                "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
                "policy": "deny every inventoried legacy subject for every purpose until a later append-only human qualification event",
                "default_when_absent": "deny",
                "source_rows_mutated": False,
                "subjects": [
                    {"subject_type": subject_type, "subject_id": subject_id}
                    for subject_type, subject_id in subjects
                ],
                "purposes": list(PURPOSES),
            }
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"{INVENTORY_VERSION}.json").write_text(
                json.dumps(inventory, indent=2, default=str) + "\n"
            )
            (OUT / f"{MANIFEST_VERSION}.json").write_text(
                json.dumps(manifest, indent=2) + "\n"
            )

            inserted = 0
            if args.apply_denials:
                rows = [
                    (subject_type, subject_id, purpose, False,
                     "founder_semantic_reset_2026_07_11", MANIFEST_VERSION,
                     "system", "pilot_prelabel_safety", "Legacy/unreviewed evidence quarantined before labeling")
                    for subject_type, subject_id in subjects for purpose in PURPOSES
                ]
                if rows:
                    execute_values(cur, """
                      INSERT INTO v2.evidence_eligibility_event
                        (subject_type,subject_id,purpose,eligible,reason_code,
                         manifest_version,actor_type,actor_id,note)
                      SELECT * FROM (VALUES %s) AS incoming
                        (subject_type,subject_id,purpose,eligible,reason_code,
                         manifest_version,actor_type,actor_id,note)
                      WHERE NOT EXISTS (
                        SELECT 1 FROM v2.evidence_eligibility_event e
                        WHERE e.subject_type=incoming.subject_type
                          AND e.subject_id=incoming.subject_id
                          AND e.purpose=incoming.purpose
                          AND e.manifest_version=incoming.manifest_version)
                    """, rows)
                    inserted = cur.rowcount
                conn.commit()
            print(json.dumps({"counts": inventory["counts"], "subjects": len(subjects),
                              "denial_events_inserted": inserted,
                              "output_dir": str(OUT.relative_to(ROOT))}))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
