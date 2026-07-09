#!/usr/bin/env python3
"""Probe 27 -- re-grade the RULES geometry path with the two probe-26 fixes
applied, on the EXACT same 4 truth_area permits / pages / anchoring as
probe26_truth_grading.py (imported, its PERMITS config/anchoring/grading
helpers reused verbatim -- only the geometry engine and two scoring rules
change, per the task spec: "keep the original numbers intact for
comparison").

New vs probe26_truth_grading.py:
  FIX 1+2 (geometry): run_geometry_engine_v2() from geometry_v2.py --
    density-gated 3.25ft generic gap closer + cavity/hatch polygon filter --
    in place of probe26's arc-chords-only engine.
  FIX 3 (grader): CONFIDENT-WRONG GUARD. A MATCHED row (single room-code
    token, single polygon) whose computed_sqft is < 40% of the truth area,
    OR < 60 SF for a non-utility room name, is demoted from MATCHED to
    CONFIDENT_WRONG -- reported separately, never counted as an auto-quantity
    success. (Every one of probe26's 14 MATCHED rows was actually this exact
    failure -- a small sliver polygon sitting under the room-number text,
    not the room -- so this fix's job is to stop calling that a match.)
  FIX 4 (grader): MERGE SCORING FIX. A MERGED_OK blob (passes the +/-15% sum
    tolerance) is downgraded to MERGE_SUSPECT if its interior still contains
    a non-trivial amount of unresolved wall-candidate linework (the v2
    engine's `walls_final` graph) -- i.e. real partitions exist inside the
    blob that never closed into their own rooms; summing-out within
    tolerance is not the same as correctly resolving the sub-rooms.

Deletes fetched PDFs after use.
"""
import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import Point  # noqa: E402

import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, extract_drawings, find_scale,
    extract_dim_words,
)
from probe2b_sf import build_grading_table  # noqa: E402
from geometry_v2 import run_geometry_engine_v2  # noqa: E402
import probe26_truth_grading as v1  # noqa: E402 -- reuse config/anchoring/overlay verbatim

OUT_DIR = os.path.join(ROOT, "data", "probe27")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR  # override v1's own tmp dir override

MERGE_OK_TOL = v1.MERGE_OK_TOL
CONFWRONG_FRAC = 0.40      # < 40% of truth area -> confident-wrong
CONFWRONG_ABS_SF = 60      # absolute floor for non-utility room names
UTILITY_NAME_KEYWORDS = (
    "CLOSET", "JAN", "ELEC", "DATA", "MECH", "STOR", "IDF", "ENTRY",
    "FOYER", "W.I.C", "WIC", "PANTRY", "UTIL", "HALL", "VEST", "ALCOVE",
)
MERGE_INTERIOR_WALL_GATE = 6  # >= this many unresolved wall-candidate
                              # midpoints strictly inside a blob -> SUSPECT


def run_engine_wrapper(pdf_path, page_index):
    """Mirrors probe26_truth_grading.run_geometry_engine's call shape/scale
    handling, but delegates the actual geometry to geometry_v2's v2 engine."""
    extracted = extract_drawings(pdf_path, page_index)
    doc_id_for_scale = int(os.path.splitext(os.path.basename(pdf_path))[0])
    feet_per_pt, scale_text = find_scale(doc_id_for_scale, page_index)
    diag = dict(scale_text=scale_text, feet_per_pt=feet_per_pt)
    if feet_per_pt is None:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = "no scale note found in page text"
        return None, diag
    out, engine_diag = run_geometry_engine_v2(extracted, feet_per_pt)
    diag.update(engine_diag)
    if out is None:
        return None, diag
    return out, diag


def is_utility_name(name):
    n = (name or "").upper()
    return any(k in n for k in UTILITY_NAME_KEYWORDS)


def apply_confident_wrong_guard(rows, truth_by_token):
    """MATCHED rows -> CONFIDENT_WRONG if implausibly small vs truth."""
    out_rows = []
    n_demoted = 0
    for row in rows:
        if row["kind"] != "MATCHED":
            out_rows.append(row)
            continue
        tok = row["tokens"][0]
        tr = truth_by_token.get(tok, {})
        truth_sf = row.get("truth_sqft")
        computed = row["computed_sqft"]
        name = tr.get("name", "")
        reasons = []
        if truth_sf:
            if computed < CONFWRONG_FRAC * truth_sf:
                reasons.append(f"computed {computed:.1f}sf < {CONFWRONG_FRAC:.0%} of truth {truth_sf:.0f}sf")
        if computed < CONFWRONG_ABS_SF and not is_utility_name(name):
            reasons.append(f"computed {computed:.1f}sf < {CONFWRONG_ABS_SF}sf floor for non-utility room '{name}'")
        if reasons:
            new_row = dict(row)
            new_row["kind"] = "CONFIDENT_WRONG"
            new_row["orig_kind"] = "MATCHED"
            new_row["guard_reasons"] = reasons
            out_rows.append(new_row)
            n_demoted += 1
        else:
            out_rows.append(row)
    return out_rows, n_demoted


def count_interior_wall_mass(poly, walls_final):
    """Count wall-candidate segment MIDPOINTS strictly inside poly's
    interior (buffered inward slightly so boundary-hugging segments that
    define the blob's own perimeter don't count as "unresolved interior
    clutter")."""
    if not walls_final:
        return 0
    shrunk = poly.buffer(-max(1e-6, poly.length * 0.0005))
    if shrunk.is_empty:
        shrunk = poly
    c = 0
    for p0, p1, L, w in walls_final:
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        if shrunk.contains(Point(mx, my)):
            c += 1
    return c


def apply_merge_scoring_fix(rows, rooms_all, walls_final):
    n_downgraded = 0
    out_rows = []
    for row in rows:
        if row["kind"] != "MERGED_OK":
            out_rows.append(row)
            continue
        poly = rooms_all[row["poly_idx"]]
        n_interior = count_interior_wall_mass(poly, walls_final)
        if n_interior >= MERGE_INTERIOR_WALL_GATE:
            new_row = dict(row)
            new_row["kind"] = "MERGE_SUSPECT"
            new_row["orig_kind"] = "MERGED_OK"
            new_row["n_interior_wall_candidates"] = n_interior
            out_rows.append(new_row)
            n_downgraded += 1
        else:
            row = dict(row)
            row["n_interior_wall_candidates"] = n_interior
            out_rows.append(row)
    return out_rows, n_downgraded


def process_permit(s3, cfg):
    permit = cfg["permit"]
    truth = v1.load_truth(cfg["truth"])
    print(f"\n{'=' * 70}\n{permit} (v2 engine)\n{'=' * 70}")

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
        print(f"\n--- page {tag} ({page_cfg['sheet']}) [v2] ---")
        pdf_path = download_pdf(s3, doc_id)

        page_truth_rooms = [r for r in addr if r["_page_key"] == (doc_id, pi)]
        truth_by_token = {r["_token"]: r for r in page_truth_rooms}

        engine_out, diag = run_engine_wrapper(pdf_path, pi)
        print("  engine diag (v2):", json.dumps(
            {k: v for k, v in diag.items() if k != "cavity_hatch_killed_detail"},
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
        target_tokens = [r["_token"] for r in page_truth_rooms]
        anchors = v1.find_room_anchors(pdf_path, pi, target_tokens)
        rows, unlabeled_polys, ambiguous = v1.grade_page(rooms_all, feet_per_pt, anchors, page_truth_rooms)

        # FIX 3: confident-wrong guard
        rows, n_demoted = apply_confident_wrong_guard(rows, truth_by_token)
        # FIX 4: merge scoring fix
        rows, n_downgraded = apply_merge_scoring_fix(rows, rooms_all, walls_final)

        page_result["n_anchors_found_on_page"] = len(anchors)
        page_result["n_target_tokens"] = len(target_tokens)
        page_result["ambiguous_tokens"] = ambiguous
        page_result["n_unlabeled_polys"] = len(unlabeled_polys)
        page_result["unlabeled_polys_sqft"] = sorted(
            [round(rooms_all[i].area * feet_per_pt ** 2, 1) for i in unlabeled_polys], reverse=True)
        page_result["n_confident_wrong_demoted"] = n_demoted
        page_result["n_merge_suspect_downgraded"] = n_downgraded
        page_result["rows"] = rows
        page_result["verdict"] = "GRADED"

        dims = extract_dim_words(pdf_path, pi)
        dim_texts = sorted({d["text"] for d in dims})
        all_rooms_sorted = sorted(rooms_all, key=lambda p: -p.area)
        dim_grading = build_grading_table(all_rooms_sorted, feet_per_pt, dim_texts)
        page_result["dimension_grading_table"] = dim_grading

        overlay_path = os.path.join(OUT_DIR, f"overlay_{tag}_v2.png")
        v1.render_overlay(pdf_path, pi, rooms_all, feet_per_pt, rows, overlay_path, unlabeled_polys)
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
    missed = [r for r in all_rows if r["kind"] == "MISSED_NO_POLYGON"]
    not_on_page = [r for r in all_rows if r["kind"] == "NOT_ON_PAGE"]

    errs = [abs(r["pct_error"]) for r in matched if r.get("pct_error") is not None]
    merge_errs = [abs(r["pct_error"]) for r in merged_err if r.get("pct_error") is not None]

    matched_computed = sum(r["computed_sqft"] for r in matched)
    matched_truth = sum(r.get("truth_sqft") or 0 for r in matched)
    merged_ok_computed = sum(r["computed_sqft"] for r in merged_ok)
    merged_ok_truth = sum(r["truth_sqft_sum"] for r in merged_ok)

    addressable_truth_sf = sum((r["area_sf"] or 0) for r in addr)

    permit_result["summary"] = dict(
        n_addressable=len(addr),
        addressable_truth_sf=addressable_truth_sf,
        n_matched=len(matched),
        n_confident_wrong=len(conf_wrong),
        n_merged_ok_groups=len(merged_ok), n_merged_ok_rooms=sum(len(r["tokens"]) for r in merged_ok),
        n_merge_suspect_groups=len(merge_suspect), n_merge_suspect_rooms=sum(len(r["tokens"]) for r in merge_suspect),
        n_merged_err_groups=len(merged_err), n_merged_err_rooms=sum(len(r["tokens"]) for r in merged_err),
        n_missed_no_polygon=len(missed),
        n_not_on_page=len(not_on_page),
        median_abs_pct_error_matched=round(statistics.median(errs), 1) if errs else None,
        median_abs_pct_error_merged_err=round(statistics.median(merge_errs), 1) if merge_errs else None,
        matched_computed_sf=round(matched_computed, 1), matched_truth_sf=round(matched_truth, 1),
        merged_ok_computed_sf=round(merged_ok_computed, 1), merged_ok_truth_sf=round(merged_ok_truth, 1),
    )
    print("\nSUMMARY (v2):", json.dumps(permit_result["summary"], indent=2))
    return permit_result


def main():
    s3 = r2_client()
    results = []
    for cfg in v1.PERMITS:
        r = process_permit(s3, cfg)
        results.append(r)

    with open(os.path.join(OUT_DIR, "results_v2.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    for f in os.listdir(PDF_TMP_DIR):
        os.remove(os.path.join(PDF_TMP_DIR, f))
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass

    print("\n\n=== ALL DONE (v2) ===")
    for r in results:
        print(r["permit"], r["summary"])


if __name__ == "__main__":
    main()
