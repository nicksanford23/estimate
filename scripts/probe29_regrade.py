#!/usr/bin/env python3
"""Probe 29 (Task A) -- re-grade the RULES geometry path with the PROXIMITY
continuity fix (geometry_v4.py) on the EXACT same 4 truth_area permits /
pages / anchoring / grader fixes 3-4 as probe28_regrade.py (imported
verbatim; only the geometry engine changes, plus one NEW grading-time step
this file adds: routing killed-but-suspect clusters to a REVIEW_KILLED
bucket instead of leaving them silently folded into MISSED_NO_POLYGON).

New vs probe28_regrade.py (v3):
  FIX (geometry, geometry_v4.py): PROXIMITY-BASED CLUSTER GROUPING replaces
    v3's strict wall-graph-touching grouping, reusing the density-gated
    closer's own GAP_FT=3.25ft scale, run BEFORE judging "zero anchors =
    off-scope". This directly targets probe28's confirmed false-positive:
    the target building's OWN wall graph fragmenting into disconnected
    islands (24-06233 p10 Building B upper rooms).
  FIX (grader, this file, NEW step "fix 6"): any cluster that is STILL
    anchor-less even after proximity grouping is no longer silently
    discarded -- geometry_v4 already splits it into REVIEW_KILLED (flagged
    false_positive_suspect) vs ARTIFACT (not suspect, discarded exactly as
    v3). Here: any MISSED_NO_POLYGON truth row whose anchor point lands
    inside a REVIEW_KILLED polygon is reclassified `REVIEW_KILLED` (a new
    grading kind) instead of remaining a bare "missed" -- the row carries
    the polygon's computed SF and the suspect metadata so a human reviewer
    can see exactly what to check. Rows with no such geometric candidate
    stay `MISSED_NO_POLYGON`, unchanged.

  Fix 3 (confident-wrong guard), fix 4 (merge-scoring fix), and fix 5
  (unit/corridor merge guard, resplit + cross-unit) are REUSED UNCHANGED
  from probe28_regrade.py (imported, not copied).

Deletes fetched PDFs after use.
"""
import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import Point  # noqa: E402

import fitz  # noqa: E402

import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, extract_drawings, find_scale,
    extract_dim_words,
)
from probe2b_sf import build_grading_table  # noqa: E402
from geometry_v3 import build_arcs_only_rooms  # noqa: E402
from geometry_v4 import run_geometry_engine_v4  # noqa: E402
import probe26_truth_grading as v1  # noqa: E402 -- reuse config/anchoring/overlay verbatim
import probe27_regrade as v2g  # noqa: E402 -- reuse fix3/fix4 verbatim
import probe28_regrade as v3g  # noqa: E402 -- reuse fix5 (merge guard) + overlay addons verbatim

OUT_DIR = os.path.join(ROOT, "data", "probe29")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR

MERGE_OK_TOL = v1.MERGE_OK_TOL
apply_confident_wrong_guard = v2g.apply_confident_wrong_guard   # fix 3, unchanged
apply_merge_scoring_fix = v2g.apply_merge_scoring_fix           # fix 4, unchanged
apply_unit_merge_guard = v3g.apply_unit_merge_guard             # fix 5, unchanged
render_artifact_addon = v3g.render_artifact_addon               # overlay addon, unchanged shape
render_resplit_addon = v3g.render_resplit_addon                 # overlay addon, unchanged


# ------------------------------------------------------------- fix 6: REVIEW_KILLED routing --

def apply_review_killed_routing(rows, review_killed_polys, feet_per_pt, anchors):
    """Any MISSED_NO_POLYGON row whose token's anchor point lands inside a
    REVIEW_KILLED polygon (geometry_v4's false-positive-suspect kill
    bucket) is reclassified REVIEW_KILLED instead of staying a bare
    'missed' -- the SF is real (a polygon exists, computed), just excluded
    from auto totals pending human review. Rows with no candidate polygon
    at all (no printed anchor point ever found in a review_killed poly)
    remain MISSED_NO_POLYGON, unchanged."""
    out_rows = []
    n_routed = 0
    routed_truth_sf = 0.0
    routed_computed_sf = 0.0
    for row in rows:
        if row["kind"] != "MISSED_NO_POLYGON":
            out_rows.append(row)
            continue
        token = row["tokens"][0]
        pts = anchors.get(token, [])
        found_poly = None
        for (x, y) in pts:
            pt = Point(x, y)
            for poly in review_killed_polys:
                if poly.contains(pt):
                    found_poly = poly
                    break
            if found_poly is not None:
                break
        if found_poly is None:
            out_rows.append(row)
            continue
        sqft = found_poly.area * feet_per_pt ** 2
        new_row = dict(row)
        new_row["kind"] = "REVIEW_KILLED"
        new_row["orig_kind"] = "MISSED_NO_POLYGON"
        new_row["computed_sqft"] = round(sqft, 1)
        new_row["excluded_from_auto_totals"] = True
        new_row["reason"] = ("anchor found inside a geometry_v4 REVIEW_KILLED polygon "
                              "(proximity-clustered, still anchor-less, flagged false_positive_suspect) "
                              "-- excluded from auto totals, needs human review, not silently discarded")
        out_rows.append(new_row)
        n_routed += 1
        routed_truth_sf += row.get("truth_sqft") or 0
        routed_computed_sf += sqft
    return out_rows, dict(n_routed=n_routed, routed_truth_sf=round(routed_truth_sf, 1),
                           routed_computed_sf=round(routed_computed_sf, 1))


# ---------------------------------------------------------------- pipeline --

def run_engine_wrapper(pdf_path, page_index, anchor_points):
    extracted = extract_drawings(pdf_path, page_index)
    doc_id_for_scale = int(os.path.splitext(os.path.basename(pdf_path))[0])
    feet_per_pt, scale_text = find_scale(doc_id_for_scale, page_index)
    diag = dict(scale_text=scale_text, feet_per_pt=feet_per_pt)
    if feet_per_pt is None:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = "no scale note found in page text"
        return None, diag
    out, engine_diag = run_geometry_engine_v4(extracted, feet_per_pt, anchor_points)
    diag.update(engine_diag)
    if out is None:
        return None, diag
    return out, diag


def process_permit(s3, cfg):
    permit = cfg["permit"]
    truth = v1.load_truth(cfg["truth"])
    print(f"\n{'=' * 70}\n{permit} (v4 engine)\n{'=' * 70}")

    for r in truth["rooms"]:
        r["_addressable"] = cfg["addressable"](r)
        r["_token"] = cfg["room_token"](r)
        r["_page_key"] = None
        if r["_addressable"]:
            r["_page_key"] = cfg["page_for_room"](r)

    not_addr = [r for r in truth["rooms"] if not r["_addressable"]]
    addr = [r for r in truth["rooms"] if r["_addressable"]]
    not_addr_by_key = defaultdict(list)
    for r in not_addr:
        not_addr_by_key[cfg["not_addressable_key"](r)].append(r)

    permit_result = dict(permit=permit, truth_total_sf=truth["total_sf"],
                          truth_n_rooms=len(truth["rooms"]),
                          n_not_addressable=len(not_addr),
                          not_addressable_by_key={
                              k: dict(n=len(v), sf=sum((x["area_sf"] or 0) for x in v))
                              for k, v in not_addr_by_key.items()},
                          pages=[])

    all_rows = []
    for page_cfg in cfg["pages"]:
        pi = page_cfg["page_index"]
        doc_id = page_cfg.get("doc_id", cfg["doc_id"])
        tag = f"{permit}_{doc_id}_p{pi}"
        print(f"\n--- page {tag} ({page_cfg['sheet']}) [v4] ---")
        pdf_path = download_pdf(s3, doc_id)

        page_truth_rooms = [r for r in addr if r["_page_key"] == (doc_id, pi)]
        truth_by_token = {r["_token"]: r for r in page_truth_rooms}
        target_tokens = [r["_token"] for r in page_truth_rooms]

        anchors = v1.find_room_anchors(pdf_path, pi, target_tokens)
        anchor_points = [pt for pts in anchors.values() for pt in pts]

        engine_out, diag = run_engine_wrapper(pdf_path, pi, anchor_points)
        print("  engine diag (v4):", json.dumps(
            {k: v for k, v in diag.items()
             if k not in ("cavity_hatch_killed_detail", "anchor_cluster_false_positive_suspects")},
            default=str))
        page_result = dict(doc_id=doc_id, page_index=pi, sheet=page_cfg["sheet"], diag=diag)

        if engine_out is None:
            page_result["verdict"] = diag["verdict"]
            page_result["rows"] = []
            permit_result["pages"].append(page_result)
            continue

        rooms_all = engine_out["rooms_all"]
        feet_per_pt = engine_out["feet_per_pt"]
        walls_final = engine_out["walls_final"]
        rows, unlabeled_polys, ambiguous = v1.grade_page(rooms_all, feet_per_pt, anchors, page_truth_rooms)

        # FIX 3: confident-wrong guard (unchanged, probe27)
        rows, n_demoted = apply_confident_wrong_guard(rows, truth_by_token)
        # FIX 4: merge scoring fix (unchanged, probe27)
        rows, n_downgraded = apply_merge_scoring_fix(rows, rooms_all, walls_final)
        # FIX 5: unit/corridor merge guard (unchanged, probe28)
        extracted = engine_out["extracted"]
        arcs_only_rooms = build_arcs_only_rooms(
            walls_final, extracted["arcs"], extracted["pw"], extracted["ph"], feet_per_pt)
        rows, merge_guard_stats = apply_unit_merge_guard(
            rows, rooms_all, truth_by_token, anchors, arcs_only_rooms, feet_per_pt)
        # FIX 6 (new, probe29): route MISSED rows whose anchor lands inside
        # a REVIEW_KILLED polygon (geometry_v4's flagged-suspect kill
        # bucket) to their own bucket instead of leaving them as bare misses
        review_killed_polys = engine_out.get("rooms_review_killed", [])
        rows, review_routing_stats = apply_review_killed_routing(
            rows, review_killed_polys, feet_per_pt, anchors)

        page_result["n_anchors_found_on_page"] = len(anchors)
        page_result["n_target_tokens"] = len(target_tokens)
        page_result["ambiguous_tokens"] = ambiguous
        page_result["n_unlabeled_polys"] = len(unlabeled_polys)
        page_result["unlabeled_polys_sqft"] = sorted(
            [round(rooms_all[i].area * feet_per_pt ** 2, 1) for i in unlabeled_polys], reverse=True)
        page_result["n_confident_wrong_demoted"] = n_demoted
        page_result["n_merge_suspect_downgraded"] = n_downgraded
        page_result["merge_guard_stats"] = merge_guard_stats
        page_result["review_killed_routing_stats"] = review_routing_stats
        page_result["n_review_killed_polys_on_page"] = len(review_killed_polys)
        page_result["review_killed_polys_sqft_on_page"] = sorted(
            [round(p.area * feet_per_pt ** 2, 1) for p in review_killed_polys], reverse=True)
        page_result["n_artifact_polys_on_page"] = len(engine_out.get("rooms_artifact_killed", []))
        page_result["artifact_polys_sqft_on_page"] = sorted(
            [round(p.area * feet_per_pt ** 2, 1) for p in engine_out.get("rooms_artifact_killed", [])],
            reverse=True)
        page_result["rows"] = rows
        page_result["verdict"] = "GRADED"

        dims = extract_dim_words(pdf_path, pi)
        dim_texts = sorted({d["text"] for d in dims})
        all_rooms_sorted = sorted(rooms_all, key=lambda p: -p.area)
        dim_grading = build_grading_table(all_rooms_sorted, feet_per_pt, dim_texts)
        page_result["dimension_grading_table"] = dim_grading

        overlay_path = os.path.join(OUT_DIR, f"overlay_{tag}_v4.png")
        v1.render_overlay(pdf_path, pi, rooms_all, feet_per_pt, rows, overlay_path, unlabeled_polys)
        rooms_all_pre_filter = engine_out.get("rooms_all_pre_anchor_filter")
        ac_diag = engine_out.get("anchor_cluster_diag")
        if rooms_all_pre_filter is not None:
            render_artifact_addon(pdf_path, pi, rooms_all_pre_filter, ac_diag, feet_per_pt, overlay_path)
        render_resplit_addon(pdf_path, pi, [r for r in rows if r.get("resolved_via") == "resplit"],
                              overlay_path)
        page_result["overlay_path"] = os.path.relpath(overlay_path, ROOT)

        all_rows.extend(rows)
        permit_result["pages"].append(page_result)

        pdf_full = os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf")
        if os.path.exists(pdf_full):
            os.remove(pdf_full)

    matched = [r for r in all_rows if r["kind"] in ("MATCHED", "MATCHED_NO_AREA")]
    conf_wrong = [r for r in all_rows if r["kind"] == "CONFIDENT_WRONG"]
    merged_ok = [r for r in all_rows if r["kind"] == "MERGED_OK"]
    merge_suspect = [r for r in all_rows if r["kind"] == "MERGE_SUSPECT"]
    merged_err = [r for r in all_rows if r["kind"] == "MERGED_ERROR"]
    merge_cross_unit = [r for r in all_rows if r["kind"] == "MERGE_CROSS_UNIT"]
    review_killed = [r for r in all_rows if r["kind"] == "REVIEW_KILLED"]
    missed = [r for r in all_rows if r["kind"] == "MISSED_NO_POLYGON"]
    not_on_page = [r for r in all_rows if r["kind"] == "NOT_ON_PAGE"]

    errs = [abs(r["pct_error"]) for r in matched if r.get("pct_error") is not None]
    merge_errs = [abs(r["pct_error"]) for r in merged_err if r.get("pct_error") is not None]

    matched_computed = sum(r["computed_sqft"] for r in matched)
    matched_truth = sum(r.get("truth_sqft") or 0 for r in matched)
    merged_ok_computed = sum(r["computed_sqft"] for r in merged_ok)
    merged_ok_truth = sum(r["truth_sqft_sum"] for r in merged_ok)
    review_killed_truth_sf = sum(r.get("truth_sqft") or 0 for r in review_killed)
    review_killed_computed_sf = sum(r.get("computed_sqft") or 0 for r in review_killed)

    addressable_truth_sf = sum((r["area_sf"] or 0) for r in addr)

    permit_result["summary"] = dict(
        n_addressable=len(addr),
        addressable_truth_sf=addressable_truth_sf,
        n_matched=len(matched),
        n_confident_wrong=len(conf_wrong),
        n_merged_ok_groups=len(merged_ok), n_merged_ok_rooms=sum(len(r["tokens"]) for r in merged_ok),
        n_merge_suspect_groups=len(merge_suspect), n_merge_suspect_rooms=sum(len(r["tokens"]) for r in merge_suspect),
        n_merged_err_groups=len(merged_err), n_merged_err_rooms=sum(len(r["tokens"]) for r in merged_err),
        n_merge_cross_unit_groups=len(merge_cross_unit),
        n_merge_cross_unit_rooms=sum(len(r["tokens"]) for r in merge_cross_unit),
        n_review_killed=len(review_killed),
        review_killed_truth_sf=round(review_killed_truth_sf, 1),
        review_killed_computed_sf=round(review_killed_computed_sf, 1),
        n_missed_no_polygon=len(missed),
        n_not_on_page=len(not_on_page),
        median_abs_pct_error_matched=round(statistics.median(errs), 1) if errs else None,
        median_abs_pct_error_merged_err=round(statistics.median(merge_errs), 1) if merge_errs else None,
        matched_computed_sf=round(matched_computed, 1), matched_truth_sf=round(matched_truth, 1),
        merged_ok_computed_sf=round(merged_ok_computed, 1), merged_ok_truth_sf=round(merged_ok_truth, 1),
    )
    print("\nSUMMARY (v4):", json.dumps(permit_result["summary"], indent=2))
    return permit_result


def main():
    s3 = r2_client()
    results = []
    for cfg in v1.PERMITS:
        r = process_permit(s3, cfg)
        results.append(r)

    with open(os.path.join(OUT_DIR, "results_v4.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    for f in os.listdir(PDF_TMP_DIR):
        os.remove(os.path.join(PDF_TMP_DIR, f))
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass

    print("\n\n=== ALL DONE (v4) ===")
    for r in results:
        print(r["permit"], r["summary"])


if __name__ == "__main__":
    main()
