#!/usr/bin/env python3
"""Run the unchanged takeoff engine on every primary page in a project packet."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import takeoff


ROOT = Path(__file__).resolve().parent.parent


def load_packet(permit: str) -> dict:
    matches = sorted((ROOT / "data" / "pilot_projects").glob(f"{permit}.project_packet_*.json"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one project packet for {permit}, found {matches}")
    with matches[0].open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permit", required=True)
    parser.add_argument("--engine", default="v4", choices=takeoff.RULES_ENGINES)
    parser.add_argument("--run-name", default="full_sheet_v4")
    parser.add_argument(
        "--use-viewports", action="store_true",
        help="constrain output polygons to each project packet's proposed quantity viewport",
    )
    args = parser.parse_args()

    packet = load_packet(args.permit)
    doc_id = int(packet["plan_set"]["onestop_doc_id"])
    pages = [int(view["page_index"]) for view in packet["primary_plan_views"]]
    viewport_by_page = None
    if args.use_viewports:
        viewport_by_page = {
            int(view["page_index"]): view["viewport_bbox"]
            for view in packet["primary_plan_views"]
        }
    source_pdf = ROOT / "data" / "render_cache" / "pdf" / f"{doc_id}.pdf"
    if not source_pdf.exists():
        raise RuntimeError(f"local source PDF missing: {source_pdf}")

    temp_paths: list[Path] = []

    def local_pdf(_client, requested_doc_id):
        if int(requested_doc_id) != doc_id:
            raise RuntimeError(f"packet doc {doc_id}, runner requested {requested_doc_id}")
        handle = tempfile.NamedTemporaryFile(prefix=f"project-{doc_id}-", suffix=".pdf", delete=False)
        handle.close()
        dest = Path(handle.name)
        shutil.copy2(source_pdf, dest)
        temp_paths.append(dest)
        return str(dest)

    takeoff.OUT_ROOT = str(ROOT / "data" / "project_runs" / args.run_name)
    takeoff.download_pdf = local_pdf
    takeoff.r2_client = lambda: None
    takeoff.append_scoreboard = lambda _row: None

    try:
        result = takeoff.run_permit(
            args.permit, doc_id, pages, engine=args.engine,
            viewport_by_page=viewport_by_page,
        )
    finally:
        for path in temp_paths:
            path.unlink(missing_ok=True)

    result_path = Path(takeoff.OUT_ROOT) / args.permit / "run.json"
    print(f"project baseline: {result_path.relative_to(ROOT)}")
    print(f"primary pages requested: {pages}")
    print(f"viewport filter: {'project packet' if args.use_viewports else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
