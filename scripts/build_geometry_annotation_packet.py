#!/usr/bin/env python3
"""Create the complete-project human geometry task packet for one pilot.

Schedule areas are reference evidence, never polygon labels. Every scheduled
space gets an explicit task, including missing/unresolved rooms, so annotation
cannot silently collapse back to the polygons an engine happened to find.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_one(pattern: str) -> tuple[Path, dict]:
    paths = sorted(ROOT.glob(pattern))
    if len(paths) != 1:
        raise RuntimeError(f"expected one match for {pattern}, found {paths}")
    return paths[0], json.loads(paths[0].read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permit", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    packet_path, project = load_one(f"data/pilot_projects/{args.permit}.project_packet_*.json")
    truth_path, schedule = load_one(f"data/triage/truth_area/{args.permit}.json")
    views = {view["level"]: view for view in project["primary_plan_views"]}

    tasks = []
    for row in schedule["rooms"]:
        view = views[row["level"]]
        tasks.append({
            "task_id": f"{args.permit}:{row['level']}:{row['room']}",
            "level": row["level"],
            "page_index": view["page_index"],
            "sheet_number": view["sheet_number"],
            "viewport_bbox_pdf": view["viewport_bbox"],
            "space": {
                "code": str(row["room"]),
                "name": row.get("name"),
                "schedule_area_sf_reference": row.get("area_sf"),
                "floor_material_reference": row.get("floor_material_bucket"),
            },
            "reference_qualification": "legacy_unverified_diagnostic_only",
            "required_human_outcome": {
                "status": "pending",
                "outcome": None,
                "boundary_types": [],
                "polygon_pdf": None,
                "open_zone_members": [],
                "notes": None,
                "reviewer": None,
                "reviewed_at": None,
            },
            "allowed_outcomes": [
                "enclosed_polygon", "open_zone", "finish_zone",
                "not_in_scope", "unresolved",
            ],
            "allowed_boundary_types": [
                "wall", "finish", "exterior", "open_split", "mixed", "unresolved",
            ],
        })

    output = {
        "schema_version": "geometry_annotation_packet_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "permit": args.permit,
        "status": "awaiting_human_geometry",
        "source_project_packet": str(packet_path.relative_to(ROOT)),
        "source_schedule_reference": str(truth_path.relative_to(ROOT)),
        "source_schedule_qualification": "legacy_unverified_diagnostic_only",
        "annotation_contract": {
            "unit": "complete_project",
            "required_task_count": len(tasks),
            "all_tasks_require_explicit_outcome": True,
            "schedule_area_is_not_polygon_truth": True,
            "model_proposals_must_remain_separate_from_human_outcomes": True,
            "coordinate_system": "source_pdf_points",
        },
        "tasks": tasks,
    }
    out_path = Path(args.output) if args.output else (
        ROOT / "data" / "geometry_annotations" / f"{args.permit}.geometry_annotation_packet_v1.json"
    )
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"created {out_path.relative_to(ROOT)}")
    print(f"tasks: {len(tasks)}; completed: 0; status: awaiting_human_geometry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
