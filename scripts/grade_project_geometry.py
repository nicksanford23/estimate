#!/usr/bin/env python3
"""Grade every primary level in a project packet against its schedule roster.

This is diagnostic grading, not ground-truth qualification. The current pilot
schedule was agent-transcribed and remains ineligible for training/evaluation
until a human confirms the source region and rows.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_one(pattern: str) -> tuple[Path, dict]:
    paths = sorted(ROOT.glob(pattern))
    if len(paths) != 1:
        raise RuntimeError(f"expected one match for {pattern}, found {paths}")
    with paths[0].open(encoding="utf-8") as handle:
        return paths[0], json.load(handle)


def pct_error(actual: float, expected: float) -> float:
    return round((actual - expected) / expected * 100, 1)


def classify_error(error_pct: float, grouped: bool = False) -> str:
    prefix = "group_" if grouped else "room_"
    if abs(error_pct) <= 10:
        return prefix + "within_10_percent"
    if error_pct > 20:
        return prefix + "oversized_likely_merged"
    if error_pct < -20:
        return prefix + "undersized_likely_partial"
    return prefix + "near_mismatch_10_to_20_percent"


def grade_level(view: dict, page: dict, truth_rows: list[dict]) -> dict:
    expected = {str(row["room"]).upper(): row for row in truth_rows}
    rooms = page.get("rooms", [])
    groups = page.get("open_groups", [])

    exact = {}
    identified = set()
    unidentified = []
    for room in rooms:
        number = str(room.get("room") or "").upper()
        if number:
            identified.add(number)
            exact[number] = room
        elif room.get("product_action") == "geometry_review":
            unidentified.append(room)

    group_results = []
    grouped_members = set()
    for group in groups:
        members = [str(member).upper() for member in group.get("members", [])]
        grouped_members.update(members)
        identified.update(members)
        expected_sf = sum(float(expected[m]["area_sf"]) for m in members if m in expected)
        actual_sf = float(group.get("area_sf") or 0)
        error = pct_error(actual_sf, expected_sf) if expected_sf else None
        group_results.append({
            "group_id": group.get("group_id"),
            "members": members,
            "actual_sf": actual_sf,
            "expected_member_sum_sf": expected_sf,
            "error_pct": error,
            "classification": classify_error(error, grouped=True) if error is not None else "group_not_in_schedule",
        })

    exact_results = []
    for number, result in sorted(exact.items()):
        if number not in expected or result.get("area_sf") is None:
            continue
        actual_sf = float(result["area_sf"])
        expected_sf = float(expected[number]["area_sf"])
        error = pct_error(actual_sf, expected_sf)
        exact_results.append({
            "room": number,
            "actual_sf": actual_sf,
            "expected_sf": expected_sf,
            "error_pct": error,
            "classification": classify_error(error),
            "product_action": result.get("product_action"),
        })

    missing = sorted(set(expected) - identified)
    failures = []
    for item in exact_results:
        if abs(item["error_pct"]) > 10:
            failures.append({"type": item["classification"], "room": item["room"], "error_pct": item["error_pct"]})
    for item in group_results:
        if item["error_pct"] is None or abs(item["error_pct"]) > 10:
            failures.append({
                "type": item["classification"], "members": item["members"],
                "error_pct": item["error_pct"],
            })
        else:
            failures.append({
                "type": "open_group_requires_room_split", "members": item["members"],
                "error_pct": item["error_pct"],
            })
    failures.extend({"type": "scheduled_room_missing", "room": room} for room in missing)
    failures.extend({
        "type": "unidentified_polygon", "area_sf": room.get("area_sf"),
        "bbox_pdf": room.get("bbox_pdf"),
    } for room in unidentified)

    viewport_meta = page.get("routing_meta", {}).get("viewport_filter")
    if viewport_meta and viewport_meta.get("n_polys_removed"):
        failures.append({
            "type": "polygons_outside_quantity_view_removed",
            "count": viewport_meta["n_polys_removed"],
        })

    expected_total = sum(float(row["area_sf"]) for row in truth_rows)
    candidate_total = sum(float(room.get("area_sf") or 0) for room in rooms)
    within_10 = sum(1 for item in exact_results if abs(item["error_pct"]) <= 10)
    return {
        "page_index": int(view["page_index"]),
        "sheet_number": view["sheet_number"],
        "level": view["level"],
        "expected_room_count": len(expected),
        "expected_area_sf": expected_total,
        "candidate_polygon_count": len(rooms),
        "candidate_area_sf": round(candidate_total, 1),
        "candidate_total_error_pct": pct_error(candidate_total, expected_total),
        "identified_schedule_room_count": len(set(expected) & identified),
        "identified_schedule_room_coverage_pct": round(len(set(expected) & identified) / len(expected) * 100, 1),
        "exact_numbered_polygon_count": len(exact_results),
        "exact_rooms_within_10_percent": within_10,
        "open_group_count": len(group_results),
        "unidentified_polygon_count": len(unidentified),
        "unidentified_area_sf": round(sum(float(room.get("area_sf") or 0) for room in unidentified), 1),
        "missing_schedule_rooms": missing,
        "exact_room_results": exact_results,
        "open_group_results": group_results,
        "viewport_filter": viewport_meta,
        "failures": failures,
    }


def markdown(report: dict) -> str:
    lines = [
        f"# Project geometry diagnostic — {report['permit']}", "",
        f"Run: `{report['run_path']}`  ",
        f"Engine: `{report['rules_engine']}`  ",
        "Truth status: **legacy agent-transcribed diagnostic reference; not training/evaluation eligible**", "",
        "| Level | Sheet | Expected rooms / SF | Identified | Exact ≤10% | Open groups | Unidentified | Candidate SF error |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for level in report["levels"]:
        lines.append(
            f"| {level['level']} | {level['sheet_number']} | "
            f"{level['expected_room_count']} / {level['expected_area_sf']:.0f} | "
            f"{level['identified_schedule_room_count']} | {level['exact_rooms_within_10_percent']} | "
            f"{level['open_group_count']} | {level['unidentified_polygon_count']} | "
            f"{level['candidate_total_error_pct']:+.1f}% |"
        )
    a = report["aggregate"]
    lines.extend([
        "", "## Aggregate", "",
        f"- Primary levels executed: {a['levels_executed']}/{a['levels_required']}",
        f"- Scheduled identities found in a polygon/group: {a['identified_schedule_rooms']}/{a['expected_rooms']}",
        f"- Exact numbered rooms within ±10%: {a['exact_rooms_within_10_percent']}/{a['expected_rooms']}",
        f"- Missing scheduled identities: {a['missing_schedule_rooms']}",
        f"- Unidentified polygons: {a['unidentified_polygons']}",
        "", "## Level failures", "",
    ])
    for level in report["levels"]:
        lines.extend([f"### {level['level']} — {level['sheet_number']}", ""])
        for failure in level["failures"]:
            detail = json.dumps(failure, sort_keys=True)
            lines.append(f"- `{failure['type']}` — `{detail}`")
        if not level["failures"]:
            lines.append("- No diagnosed failures.")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permit", required=True)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args()

    packet_path, packet = load_one(f"data/pilot_projects/{args.permit}.project_packet_*.json")
    truth_path, truth = load_one(f"data/triage/truth_area/{args.permit}.json")
    run_path = ROOT / "data" / "project_runs" / args.run_name / args.permit / "run.json"
    with run_path.open(encoding="utf-8") as handle:
        run = json.load(handle)

    pages = {int(page["page_index"]): page for page in run.get("pages", [])}
    truth_by_level = defaultdict(list)
    for row in truth["rooms"]:
        truth_by_level[row["level"]].append(row)

    levels = []
    for view in packet["primary_plan_views"]:
        page_index = int(view["page_index"])
        if page_index not in pages:
            raise RuntimeError(f"run missing required page {page_index}")
        levels.append(grade_level(view, pages[page_index], truth_by_level[view["level"]]))

    aggregate = {
        "levels_required": len(packet["primary_plan_views"]),
        "levels_executed": len(levels),
        "expected_rooms": sum(level["expected_room_count"] for level in levels),
        "identified_schedule_rooms": sum(level["identified_schedule_room_count"] for level in levels),
        "exact_rooms_within_10_percent": sum(level["exact_rooms_within_10_percent"] for level in levels),
        "missing_schedule_rooms": sum(len(level["missing_schedule_rooms"]) for level in levels),
        "unidentified_polygons": sum(level["unidentified_polygon_count"] for level in levels),
    }
    report = {
        "schema_version": "project_geometry_diagnostic_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "permit": args.permit,
        "packet_path": str(packet_path.relative_to(ROOT)),
        "truth_path": str(truth_path.relative_to(ROOT)),
        "truth_qualification": "legacy_unverified_diagnostic_only",
        "run_path": str(run_path.relative_to(ROOT)),
        "rules_engine": run.get("rules_engine"),
        "levels": levels,
        "aggregate": aggregate,
    }
    out_dir = run_path.parent
    json_path = out_dir / "project_geometry_diagnostic.json"
    md_path = out_dir / "project_geometry_diagnostic.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, indent=2))
    print(f"json: {json_path.relative_to(ROOT)}")
    print(f"markdown: {md_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
