#!/usr/bin/env python3
"""Apply identity and machine-proposal portions of a project packet to V2.

This script never creates human decisions, source links that require human
decisions, or evidence-eligibility approvals. Viewports and level assignments
are machine observations until reviewed in the UI.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parent.parent
PACKET_DIR = ROOT / "data" / "pilot_projects"


def env_value(key: str) -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{key} missing from .env")


def packet_path(permit: str) -> Path:
    matches = sorted(PACKET_DIR.glob(f"{permit}.project_packet_*.json"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one packet for {permit}, found {matches}")
    return matches[0]


def load_packet(permit: str) -> dict:
    with packet_path(permit).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_schedule_reference(permit: str) -> dict:
    path = ROOT / "data" / "triage" / "truth_area" / f"{permit}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def space_kind(name: str) -> str:
    upper = name.upper()
    if "CORRIDOR" in upper or upper == "HALL":
        return "corridor"
    return "room"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permit", required=True)
    parser.add_argument("--apply", action="store_true", help="commit changes; default is rollback preview")
    args = parser.parse_args()

    packet = load_packet(args.permit)
    schedule = load_schedule_reference(args.permit)
    conn = psycopg2.connect(os.environ.get("NEON_DATABASE_URL") or env_value("NEON_DATABASE_URL"))
    conn.autocommit = False
    counts = {"plan_sets": 0, "plan_set_documents": 0, "levels": 0, "spaces": 0,
              "regions": 0, "region_geometry_observations": 0, "level_observations": 0}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.id, b.id FROM v2.permit p
                   JOIN v2.permit_building pb ON pb.permit_id=p.id
                   JOIN v2.building b ON b.id=pb.building_id
                   WHERE p.permit_num=%s""",
                (args.permit,),
            )
            permit_id, building_id = cur.fetchone()

            revision = packet["plan_set"]["revision_label"]
            cur.execute(
                "SELECT id FROM v2.plan_set WHERE building_id=%s AND revision_label=%s",
                (building_id, revision),
            )
            row = cur.fetchone()
            if row:
                plan_set_id = row[0]
            else:
                cur.execute(
                    """INSERT INTO v2.plan_set (building_id, revision_label, notes)
                       VALUES (%s,%s,%s) RETURNING id""",
                    (building_id, revision, "project_packet_v1; assembly pending human confirmation"),
                )
                plan_set_id = cur.fetchone()[0]
                counts["plan_sets"] += 1

            onestop = packet["plan_set"]["onestop_doc_id"]
            cur.execute(
                "SELECT id FROM v2.document WHERE permit_id=%s AND onestop_doc_id=%s",
                (permit_id, onestop),
            )
            document_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO v2.plan_set_document (plan_set_id,document_id,role)
                   VALUES (%s,%s,'primary_architectural') ON CONFLICT DO NOTHING""",
                (plan_set_id, document_id),
            )
            counts["plan_set_documents"] += cur.rowcount

            level_ids: dict[str, int] = {}
            for ordinal, name in enumerate(("01 LEVEL", "02 LEVEL", "03 LEVEL", "04 LEVEL"), start=1):
                cur.execute(
                    """INSERT INTO v2.level (building_id,name,ordinal) VALUES (%s,%s,%s)
                       ON CONFLICT (building_id,name) DO UPDATE SET ordinal=EXCLUDED.ordinal
                       RETURNING id, (xmax = 0)""",
                    (building_id, name, ordinal),
                )
                level_id, inserted = cur.fetchone()
                level_ids[name] = level_id
                counts["levels"] += int(inserted)

            for room in schedule["rooms"]:
                level_id = level_ids[room["level"]]
                code = str(room["room"]).strip()
                cur.execute(
                    "SELECT id FROM v2.space WHERE building_id=%s AND level_id=%s AND code=%s",
                    (building_id, level_id, code),
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    """INSERT INTO v2.space (building_id,level_id,code,name,kind,notes)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (
                        building_id,
                        level_id,
                        code,
                        room.get("name"),
                        space_kind(room.get("name") or ""),
                        "candidate identity from legacy agent-transcribed schedule; source link pending human decision",
                    ),
                )
                counts["spaces"] += 1

            for view in packet["primary_plan_views"]:
                cur.execute(
                    "SELECT id FROM v2.page WHERE document_id=%s AND pdf_page_index=%s",
                    (document_id, view["page_index"]),
                )
                page_id = cur.fetchone()[0]
                cur.execute(
                    "SELECT id FROM v2.region WHERE page_id=%s AND kind='plan_viewport' ORDER BY id LIMIT 1",
                    (page_id,),
                )
                row = cur.fetchone()
                if row:
                    region_id = row[0]
                else:
                    cur.execute("INSERT INTO v2.region (page_id,kind) VALUES (%s,'plan_viewport') RETURNING id", (page_id,))
                    region_id = cur.fetchone()[0]
                    counts["regions"] += 1

                proposals = (
                    ("region_geometry", view["viewport_bbox"]),
                    ("level_assignment", {"level_id": level_ids[view["level"]], "level": view["level"]}),
                )
                for claim, value in proposals:
                    cur.execute(
                        """SELECT 1 FROM v2.machine_observation
                           WHERE target_type='region' AND target_id=%s AND claim=%s
                             AND source='project_packet' AND source_version=%s""",
                        (region_id, claim, packet["schema_version"]),
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        """INSERT INTO v2.machine_observation
                           (target_type,target_id,claim,value_json,source,source_version,score_type)
                           VALUES ('region',%s,%s,%s::jsonb,'project_packet',%s,'machine_verified_pending_human')""",
                        (region_id, claim, json.dumps(value), packet["schema_version"]),
                    )
                    counts["region_geometry_observations" if claim == "region_geometry" else "level_observations"] += 1

        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    mode = "APPLIED" if args.apply else "DRY RUN (rolled back)"
    print(f"{mode}: {args.permit}")
    print(json.dumps(counts, indent=2, sort_keys=True))
    print("human_decisions=0 space_source_links=0 eligibility_approvals=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
