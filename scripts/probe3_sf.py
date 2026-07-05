#!/usr/bin/env python3
"""Probe 3 -- coverage survey. Runs the probe-2b pipeline (imported as a
library, NO per-page tuning -- this measures how the CURRENT rules
generalize) across 18 floor_plan pages from 18 DIFFERENT permits.

Per .claude/skills/sf-extraction/SKILL.md probe ladder step 3. Verdicts are
assigned by a human-equivalent visual grading pass over the overlay PNGs
(the skill's verification standard: "Overlay PNGs accompany every result --
humans grade pictures, not stats") -- this script produces the mechanical
JSON/overlay artifacts; verdict labels are filled in by the orchestrating
agent after reviewing each overlay, then written into results.json.

Deletes fetched PDFs after use (disk is tight).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, extract_drawings, snap_and_close,
    polygonize_rooms, cluster_by_touching, find_scale, extract_dim_words,
    parse_ft_in, render_overlay,
)
from probe2b_sf import (  # noqa: E402
    two_tier_wall_candidates, find_parallel_pairs, admit_minor,
    build_grading_table,
)

OUT_DIR = os.path.join(ROOT, "data", "probe3")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
# download_pdf() (imported from probe2_sf) writes into probe2_sf's own
# module-level PDF_TMP_DIR global -- retarget it at OUR tmp dir so cleanup
# here actually finds the files (probe2/probe2b dirs are untouched).
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR

# 18 floor_plan pages, 18 DIFFERENT permits (excludes 17-35590-RNVS and
# 19-24353-RNVS, already probed in probe 1/2/2b), spanning 2013-2026 and a
# mix of new-construction (NEWC) / renovation (RNVS/RNVN) project types.
PAGES = [
    dict(permit="13-38849-NEWC", doc_id=1035289, page_index=6),
    dict(permit="13-44083-NEWC", doc_id=1074488, page_index=18),
    dict(permit="13-44124-NEWC", doc_id=1017503, page_index=9),
    dict(permit="13-44130-NEWC", doc_id=1074611, page_index=18),
    dict(permit="14-11290-NEWC", doc_id=1494156, page_index=3),
    dict(permit="15-08510-NEWC", doc_id=1774036, page_index=8),
    dict(permit="16-17098-NEWC", doc_id=2406075, page_index=16),
    dict(permit="17-10173-NEWC", doc_id=2794931, page_index=16),
    dict(permit="18-13316-RNVS", doc_id=3371384, page_index=9),
    dict(permit="18-29543-RNVS", doc_id=3619276, page_index=14),
    dict(permit="19-00670-RNVS", doc_id=5101148, page_index=5),
    dict(permit="19-27088-NEWC", doc_id=4418151, page_index=4),
    dict(permit="21-32352-NEWC", doc_id=5503323, page_index=2),
    dict(permit="22-37867-NEWC", doc_id=5953479, page_index=14),
    dict(permit="24-06748-RNVS", doc_id=7372349, page_index=6),
    dict(permit="24-17262-NEWC", doc_id=7308452, page_index=30),
    dict(permit="25-27326-RNVS", doc_id=8502229, page_index=15),
    dict(permit="26-05332-NEWC", doc_id=8929774, page_index=8),
]


def process_page(s3, page_def):
    permit, doc_id, page_index = page_def["permit"], page_def["doc_id"], page_def["page_index"]
    tag = f"{permit}_{doc_id}_p{page_index}"
    print(f"\n=== {tag} ===")
    result = dict(permit=permit, doc_id=doc_id, page_index=page_index, tag=tag)

    pdf_path = download_pdf(s3, doc_id)
    try:
        feet_per_pt, scale_text = find_scale(doc_id, page_index)
        result["scale_text"] = scale_text
        result["feet_per_pt"] = feet_per_pt

        extracted = extract_drawings(pdf_path, page_index)
        n_lines = len(extracted["line_segments"])
        result["n_line_segments_raw"] = n_lines
        pw, ph = extracted["pw"], extracted["ph"]

        # RASTER check: near-empty get_drawings() = scanned/flattened page,
        # out of Route A scope per skill known failure modes.
        if n_lines < 20:
            result["verdict"] = "RASTER"
            result["reason"] = f"get_drawings() returned only {n_lines} line segments -- scanned/flattened page"
            print(json.dumps(result, indent=2))
            return result

        if feet_per_pt is None:
            result["verdict"] = "SCALE_FAIL"
            result["reason"] = "no scale note found in page text"
            print(json.dumps(result, indent=2))
            return result

        tiers = two_tier_wall_candidates(extracted, feet_per_pt)
        major_clean, minor_clean = tiers["major"], tiers["minor"]
        result["n_major_clean"] = len(major_clean)
        result["n_minor_clean_candidates"] = len(minor_clean)
        result["dominant_angle_deg"] = round(tiers["dom"], 3)

        combined_clean = major_clean + minor_clean
        pairs = find_parallel_pairs(combined_clean, feet_per_pt)
        pair_member_segs = set()
        for a, b, *_ in pairs:
            pair_member_segs.add(a)
            pair_member_segs.add(b)
        result["n_parallel_pairs"] = len(pairs)

        centerlines, seen_keys = [], set()
        for a, b, horiz, lo, hi, c in pairs:
            p0, p1 = ((lo, c), (hi, c)) if horiz else ((c, lo), (c, hi))
            key = (horiz, round(c / 2.0), round(lo / 3.0), round(hi / 3.0))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            centerlines.append((p0, p1, hi - lo, 0.3))

        minor_unpaired = [s for s in minor_clean if s not in pair_member_segs]
        seed = major_clean + centerlines
        walls_final, n_added, n_left = admit_minor(seed, minor_unpaired, pw)
        result["n_walls_final"] = len(walls_final)

        lines_ls, gap_info = snap_and_close(walls_final, extracted["arcs"], pw, feet_per_pt=None)
        result["gap_closing"] = gap_info

        min_sqft, max_sqft = 15, 5000
        rooms_all, n_faces = polygonize_rooms(lines_ls, pw, ph, min_sqft, max_sqft, feet_per_pt)
        result["n_polygon_faces_total"] = n_faces
        result["n_rooms_before_clustering"] = len(rooms_all)

        if not rooms_all:
            result["verdict"] = "BLOB"
            result["reason"] = "no room-sized polygons closed at all (either total merge, or total fragmentation)"
            print(json.dumps(result, indent=2))
            return result

        clusters = cluster_by_touching(rooms_all)
        clusters.sort(key=lambda idxs: -sum(rooms_all[i].area for i in idxs))
        main_cluster = clusters[0]
        other_clusters = clusters[1:]
        main_rooms = [rooms_all[i] for i in main_cluster]
        main_total_sqft = sum(p.area * feet_per_pt ** 2 for p in main_rooms)
        result["n_rooms_main_cluster"] = len(main_rooms)
        result["n_other_clusters_excluded"] = len(other_clusters)

        largest_room_sqft = max(p.area * feet_per_pt ** 2 for p in main_rooms)
        audit_ok = 30 <= largest_room_sqft <= 10000 and 30 <= main_total_sqft <= 200000
        result["largest_room_sqft"] = round(largest_room_sqft, 1)
        result["total_sqft_main_cluster"] = round(main_total_sqft, 1)
        result["audit_ok"] = audit_ok

        if not audit_ok:
            result["verdict"] = "SCALE_FAIL"
            result["reason"] = f"self-audit failed: largest_room={largest_room_sqft:.0f}sqft total={main_total_sqft:.0f}sqft"
            print(json.dumps(result, indent=2))
            return result

        rooms_sorted = sorted(main_rooms, key=lambda p: -p.area)
        rooms_json = []
        for i, poly in enumerate(rooms_sorted):
            sqft = poly.area * feet_per_pt ** 2
            minx, miny, maxx, maxy = poly.bounds
            rooms_json.append(dict(
                room_idx=i,
                sqft=round(sqft, 1),
                bbox_w_ft=round((maxx - minx) * feet_per_pt, 2),
                bbox_h_ft=round((maxy - miny) * feet_per_pt, 2),
                polygon_pts=[[round(x, 1), round(y, 1)] for x, y in poly.exterior.coords],
                confidence="low" if sqft > 900 else "medium",
            ))
        result["rooms"] = rooms_json

        dims = extract_dim_words(pdf_path, page_index)
        dim_texts = sorted({d["text"] for d in dims})
        result["n_dim_strings_found"] = len(dim_texts)
        all_rooms_sorted = sorted(rooms_all, key=lambda p: -p.area)
        grading = build_grading_table(all_rooms_sorted, feet_per_pt, dim_texts)
        result["grading_table"] = grading

        overlay_path = os.path.join(OUT_DIR, f"_allpages_overlay_{tag}.png")
        render_overlay(pdf_path, page_index, main_rooms, other_clusters, rooms_all,
                        rooms_json, overlay_path)
        result["overlay_path"] = overlay_path

        # mechanical pre-verdict, to be confirmed/overridden by visual review
        # of the overlay (per skill: humans grade pictures, not stats)
        n_graded = len(grading)
        if len(main_rooms) >= 4 and n_graded >= 2:
            result["mechanical_verdict"] = "ROOMS_GOOD"
        elif len(main_rooms) >= 2:
            result["mechanical_verdict"] = "PARTIAL"
        else:
            result["mechanical_verdict"] = "BLOB"

        print(json.dumps({k: v for k, v in result.items() if k not in ("rooms",)}, indent=2, default=str))
        return result
    except Exception as e:
        result["verdict"] = "ERROR"
        result["reason"] = f"{type(e).__name__}: {e}"
        print(json.dumps(result, indent=2, default=str))
        return result
    finally:
        pass


def main():
    s3 = r2_client()
    results = []
    for page_def in PAGES:
        r = process_page(s3, page_def)
        results.append(r)
        # delete this page's PDF immediately -- disk is tight, don't
        # accumulate 18 fetched PDFs
        pdf_path = os.path.join(PDF_TMP_DIR, f"{page_def['doc_id']}.pdf")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    with open(os.path.join(OUT_DIR, "results_raw.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass

    print("\n=== SUMMARY ===")
    for r in results:
        print(r["permit"], r.get("verdict", r.get("mechanical_verdict")),
              r.get("total_sqft_main_cluster"), "n_rooms=", r.get("n_rooms_main_cluster"))


if __name__ == "__main__":
    main()
