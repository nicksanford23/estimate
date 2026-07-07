#!/usr/bin/env python3
"""Part 1(c): rerun the 18 probe-3 pages' saved candidate room polygons
through sf_guard.run_guard(), report before/after accept/reject/merged
counts per page. Re-downloads each doc's PDF from R2 (deleted after probe
3), deletes it again immediately after use -- disk is tight.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import ROOT, r2_client, download_pdf  # noqa: E402
from sf_guard import run_guard, guard_summary  # noqa: E402

RAW_PATH = os.path.join(ROOT, "data", "probe3", "results_raw.json")
OUT_PATH = os.path.join(ROOT, "data", "probe3", "guard_validation.json")


def main():
    with open(RAW_PATH) as f:
        pages = json.load(f)

    s3 = r2_client()
    out_rows = []
    for p in pages:
        permit = p["permit"]
        rooms = p.get("rooms", [])
        row = dict(permit=permit, verdict_before=p.get("verdict") or p.get("mechanical_verdict"),
                   n_candidate_rooms=len(rooms))
        if not rooms:
            row["guard_summary"] = {}
            row["note"] = "no candidate rooms in probe-3 output (RASTER/SCALE_FAIL/no closure)"
            out_rows.append(row)
            print(permit, "-- no candidates, skipped")
            continue

        doc_id, page_index = p["doc_id"], p["page_index"]
        pdf_path = download_pdf(s3, doc_id)
        try:
            guard_rows = run_guard(rooms, pdf_path, page_index)
            row["guard_summary"] = guard_summary(guard_rows)
            row["guard_rows"] = guard_rows
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        out_rows.append(row)
        print(permit, row["guard_summary"])

    with open(OUT_PATH, "w") as f:
        json.dump(out_rows, f, indent=2, default=str)
    print("\nwrote", OUT_PATH)


if __name__ == "__main__":
    main()
