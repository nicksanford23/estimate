#!/usr/bin/env python3
"""Validate Geometry Label Book V2 annotation records.

JSON Schema checks the record shape. These semantic checks enforce invariants
that draft-07 cannot express cleanly: closed rings, one edge per segment,
threshold metadata, resolution consistency, and the two-part precision gate.
This script does not grant evidence eligibility.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = ROOT / "docs/pilot/schema/geometry_annotation_v2.schema.json"
EPSILON = 1e-9


def load_records(path: Path) -> list[tuple[str, dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        records: list[tuple[str, dict[str, Any]]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number}: expected an object")
            records.append((f"line {line_number}", value))
        return records

    value = json.loads(text)
    if isinstance(value, dict):
        return [("record", value)]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return [(f"record {index}", item) for index, item in enumerate(value)]
    raise ValueError("expected one object, an array of objects, or JSONL")


def same_point(a: list[float], b: list[float]) -> bool:
    return math.isclose(a[0], b[0], abs_tol=EPSILON) and math.isclose(
        a[1], b[1], abs_tol=EPSILON
    )


def orientation(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a: list[float], b: list[float], p: list[float]) -> bool:
    return (
        min(a[0], b[0]) - EPSILON <= p[0] <= max(a[0], b[0]) + EPSILON
        and min(a[1], b[1]) - EPSILON <= p[1] <= max(a[1], b[1]) + EPSILON
        and abs(orientation(a, b, p)) <= EPSILON
    )


def segments_intersect(
    a: list[float], b: list[float], c: list[float], d: list[float]
) -> bool:
    o1, o2 = orientation(a, b, c), orientation(a, b, d)
    o3, o4 = orientation(c, d, a), orientation(c, d, b)
    if ((o1 > EPSILON and o2 < -EPSILON) or (o1 < -EPSILON and o2 > EPSILON)) and (
        (o3 > EPSILON and o4 < -EPSILON) or (o3 < -EPSILON and o4 > EPSILON)
    ):
        return True
    return (
        (abs(o1) <= EPSILON and on_segment(a, b, c))
        or (abs(o2) <= EPSILON and on_segment(a, b, d))
        or (abs(o3) <= EPSILON and on_segment(c, d, a))
        or (abs(o4) <= EPSILON and on_segment(c, d, b))
    )


def ring_errors(ring: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    points = ring["coordinates_pdf"]
    edges = ring["edges"]
    if not same_point(points[0], points[-1]):
        errors.append(f"{path}.coordinates_pdf: ring is not closed")
    segment_count = len(points) - 1
    if len(edges) != segment_count:
        errors.append(
            f"{path}.edges: expected {segment_count} edges for {segment_count} segments, "
            f"found {len(edges)}"
        )
    seg_ids = [edge["seg_id"] for edge in edges]
    if len(seg_ids) != len(set(seg_ids)):
        errors.append(f"{path}.edges: seg_id values must be unique within a ring")

    for index, edge in enumerate(edges):
        edge_path = f"{path}.edges[{index}]"
        boundary_type = edge["boundary_type"]
        if boundary_type == "threshold" and edge.get("alignment_reference") not in {
            "jamb_line",
            "wall_center",
            "finish_transition",
        }:
            errors.append(f"{edge_path}: threshold requires an alignment_reference")
        if boundary_type == "unresolved" and not edge.get("unresolved_reason"):
            errors.append(f"{edge_path}: unresolved edge requires unresolved_reason")

    # Adjacent segments share endpoints and are expected to intersect there.
    for i in range(segment_count):
        a, b = points[i], points[i + 1]
        if same_point(a, b):
            errors.append(f"{path}: zero-length segment at index {i}")
        for j in range(i + 1, segment_count):
            if j in {i - 1, i, i + 1} or (i == 0 and j == segment_count - 1):
                continue
            c, d = points[j], points[j + 1]
            if segments_intersect(a, b, c, d):
                errors.append(f"{path}: segments {i} and {j} self-intersect")
    return errors


def semantic_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    geometry_status = record["geometry_status"]
    geometry = record["surface_geometry"]
    if geometry:
        unresolved_edges = 0
        for part_index, part in enumerate(geometry["polygons"]):
            errors.extend(
                ring_errors(part["exterior"], f"surface_geometry.polygons[{part_index}].exterior")
            )
            unresolved_edges += sum(
                edge["boundary_type"] == "unresolved" for edge in part["exterior"]["edges"]
            )
            for hole_index, hole in enumerate(part["holes"]):
                errors.extend(
                    ring_errors(
                        hole,
                        f"surface_geometry.polygons[{part_index}].holes[{hole_index}]",
                    )
                )
                unresolved_edges += sum(
                    edge["boundary_type"] == "unresolved" for edge in hole["edges"]
                )
        if geometry_status == "resolved" and unresolved_edges:
            errors.append("geometry_status resolved cannot contain unresolved edges")

    memberships = [item["space_code"] for item in record["identity_memberships"]]
    if len(memberships) != len(set(memberships)):
        errors.append("identity_memberships contains duplicate space_code values")

    precision = record["precision"]
    if precision and precision["passes"] is True:
        edge_error = precision["max_edge_deviation_in"]
        area_error = precision["area_error_pct"]
        if precision["reference_geometry_ref"] is None:
            errors.append("precision.passes true requires reference_geometry_ref")
        if edge_error is None or area_error is None:
            errors.append("precision.passes true requires both measured errors")
        elif edge_error > 1.5 or area_error > 2.0:
            errors.append(
                "precision.passes true requires max_edge_deviation_in <= 1.5 "
                "AND area_error_pct <= 2.0"
            )
    if precision and precision["passes"] is False:
        edge_error = precision["max_edge_deviation_in"]
        area_error = precision["area_error_pct"]
        if edge_error is not None and area_error is not None and edge_error <= 1.5 and area_error <= 2.0:
            errors.append("precision.passes false contradicts two passing measured errors")

    if record["scope_status"] == "not_in_scope" and geometry_status == "unresolved":
        errors.append("not_in_scope cannot replace unresolved Layer-A geometry")
    return errors


def format_schema_error(error: Any) -> str:
    path = ".".join(str(piece) for piece in error.absolute_path) or "$"
    return f"{path}: {error.message}"


def validate_records(
    records: Iterable[tuple[str, dict[str, Any]]], validator: Draft7Validator
) -> tuple[int, int]:
    checked = 0
    failed = 0
    for label, record in records:
        checked += 1
        errors = [format_schema_error(error) for error in validator.iter_errors(record)]
        if not errors:
            errors.extend(semantic_errors(record))
        if errors:
            failed += 1
            print(f"FAIL {label}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {label}: {record['annotation_id']}")
    return checked, failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="V2 .json or .jsonl file")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    try:
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        records = load_records(args.input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    checked, failed = validate_records(records, Draft7Validator(schema))
    print(f"checked={checked} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
