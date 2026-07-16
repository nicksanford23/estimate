#!/usr/bin/env python3
"""Fail closed when a partial geometry run is presented as a project run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PACKET_DIR = ROOT / "data" / "pilot_projects"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def packet_path(permit: str) -> Path:
    matches = sorted(PACKET_DIR.glob(f"{permit}.project_packet_*.json"))
    if not matches:
        raise SystemExit(f"no project packet found for {permit} in {PACKET_DIR}")
    if len(matches) > 1:
        raise SystemExit(f"multiple project packets found for {permit}: {matches}")
    return matches[0]


def validate_shape(packet: dict, path: Path) -> list[str]:
    errors: list[str] = []
    if packet.get("schema_version") != "project_packet_v1":
        errors.append("schema_version must be project_packet_v1")
    if not packet.get("permit"):
        errors.append("permit is required")
    if not packet.get("schedule_sources"):
        errors.append("at least one schedule source is required")
    primary = packet.get("primary_plan_views") or []
    if not primary:
        errors.append("at least one primary plan view is required")
    keys = [(v.get("page_index"), v.get("level")) for v in primary]
    if len(keys) != len(set(keys)):
        errors.append("primary plan page/level pairs must be unique")
    for idx, view in enumerate(primary):
        for field in ("page_index", "sheet_number", "level", "expected_room_count", "expected_area_sf"):
            if view.get(field) in (None, ""):
                errors.append(f"primary_plan_views[{idx}].{field} is required")
    if errors:
        errors.insert(0, f"invalid packet: {path}")
    return errors


def geometry_pages(packet: dict) -> set[int]:
    permit = packet["permit"]
    configured = packet.get("current_baseline", {}).get("run_path")
    run_path = ROOT / configured if configured else ROOT / "data" / "takeoff" / permit / "run.json"
    if not run_path.exists():
        return set()
    run = load_json(run_path)
    return {
        int(page["page_index"])
        for page in run.get("pages", [])
        if page.get("page_index") is not None
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permit", required=True)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit nonzero unless every required primary plan has a geometry outcome",
    )
    args = parser.parse_args()

    path = packet_path(args.permit)
    packet = load_json(path)
    errors = validate_shape(packet, path)
    if errors:
        print("\n".join(errors))
        return 2

    required = {int(view["page_index"]) for view in packet["primary_plan_views"]}
    completed = geometry_pages(packet)
    completed_required = required & completed
    missing = required - completed
    extra = completed - required

    print(f"project: {args.permit}")
    print(f"packet: {path.relative_to(ROOT)}")
    print(f"primary geometry coverage: {len(completed_required)}/{len(required)}")
    print(f"completed required pages: {sorted(completed_required)}")
    print(f"missing required pages: {sorted(missing)}")
    if extra:
        print(f"supporting/unrecognized geometry pages: {sorted(extra)}")

    if missing:
        print("status: INCOMPLETE_PROJECT_DIAGNOSTIC_ONLY")
        return 1 if args.strict else 0

    print("status: PRIMARY_VIEW_COVERAGE_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
