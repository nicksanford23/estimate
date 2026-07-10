#!/usr/bin/env python3
"""Probe 30 follow-up -- DUAL-engine product test on the 4 TRUTH_AREA
answer-key permits, for the CONDITIONAL PROMOTE acceptance battery.

Runs BOTH engines per page -- rules-v4 (probe29's exact pipeline) and
model-as-engine (probe30's exact pipeline) -- then reconciles them with
takeoff.reconcile_dual_engines (the SAME function `takeoff.py run --engine
dual` uses, quality gates and all), and grades the reconciled polygon set
through the identical probe26-29 grader stack (grade_page + fixes 3-6,
imported verbatim). One extra grading-time step, mirroring what takeoff.py's
build_rooms does with poly_notes: any graded row whose polygon carries a
non-empty reconcile note (winner quality-gate demotion, loser-only rescue,
engines-disagree, or a whole-page demote) is reclassified DUAL_REVIEW --
excluded from matched AND from confident-wrong (it ships as geometry_review,
never as an auto number).

Approximation, documented: fixes 4/5 (merge-scoring, unit-merge guard)
consult the WINNER engine's walls_final/extracted/arcs; rescued loser-only
polygons are not part of that wall graph, but every rescued polygon is
force-routed to DUAL_REVIEW anyway, so no auto/matched number ever depends
on the approximation.

Deletes fetched PDFs after use.
"""
import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joblib  # noqa: E402

import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, find_scale, extract_drawings,
    extract_dim_words,
)
from geometry_v3 import build_arcs_only_rooms  # noqa: E402
from geometry_v4 import run_geometry_engine_v4  # noqa: E402
from geometry_model import run_geometry_engine_model  # noqa: E402
import probe26_truth_grading as v1  # noqa: E402 -- config/anchoring/grader verbatim
import probe27_regrade as v2g  # noqa: E402 -- fixes 3/4 verbatim
import probe28_regrade as v3g  # noqa: E402 -- fix 5 verbatim
import probe29_regrade as v4g  # noqa: E402 -- fix 6 verbatim
import takeoff  # noqa: E402 -- reconcile_dual_engines, the same one `run --engine dual` uses

OUT_DIR = os.path.join(ROOT, "data", "probe30", "product_test")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp_dual")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR

apply_confident_wrong_guard = v2g.apply_confident_wrong_guard
apply_merge_scoring_fix = v2g.apply_merge_scoring_fix
apply_unit_merge_guard = v3g.apply_unit_merge_guard
apply_review_killed_routing = v4g.apply_review_killed_routing

MODEL_PATH = os.path.join(ROOT, "models", "wall_model_v2.joblib")
SEG_RESULTS = os.path.join(ROOT, "data", "probe30", "segment_results.json")

DEMOTABLE_KINDS = ("MATCHED", "MATCHED_NO_AREA", "CONFIDENT_WRONG", "MERGED_OK",
                    "MERGED_ERROR", "MERGE_SUSPECT", "MERGE_CROSS_UNIT")


def apply_dual_review_routing(rows, poly_notes):
    """Grading-time mirror of takeoff.build_rooms' forced_review: a row whose
    polygon carries any reconcile note never ships as an auto/matched/
    confident number -- it becomes DUAL_REVIEW (its own bucket, like fix 6's
    REVIEW_KILLED). Rows without a poly_idx (MISSED_NO_POLYGON etc.) pass
    through untouched."""
    out, n_routed = [], 0
    for row in rows:
        idx = row.get("poly_idx")
        if (idx is not None and idx < len(poly_notes) and poly_notes[idx]
                and row["kind"] in DEMOTABLE_KINDS):
            new_row = dict(row)
            new_row["orig_kind"] = row["kind"]
            new_row["kind"] = "DUAL_REVIEW"
            new_row["dual_notes"] = list(poly_notes[idx])
            new_row["excluded_from_auto_totals"] = True
            out.append(new_row)
            n_routed += 1
        else:
            out.append(row)
    return out, n_routed


def process_permit(s3, cfg, clf, threshold):
    permit = cfg["permit"]
    truth = v1.load_truth(cfg["truth"])
    print(f"\n{'=' * 70}\n{permit} (DUAL engine: v4 + wall_model_v2 t={threshold})\n{'=' * 70}")

    for r in truth["rooms"]:
        r["_addressable"] = cfg["addressable"](r)
        r["_token"] = cfg["room_token"](r)
        r["_page_key"] = cfg["page_for_room"](r) if r["_addressable"] else None

    addr = [r for r in truth["rooms"] if r["_addressable"]]
    permit_result = dict(permit=permit, n_addressable=len(addr), pages=[])

    all_rows = []
    for page_cfg in cfg["pages"]:
        pi = page_cfg["page_index"]
        doc_id = page_cfg.get("doc_id", cfg["doc_id"])
        tag = f"{permit}_{doc_id}_p{pi}"
        print(f"\n--- page {tag} ({page_cfg['sheet']}) [DUAL] ---")
        pdf_path = download_pdf(s3, doc_id)
        try:
            page_truth_rooms = [r for r in addr if r["_page_key"] == (doc_id, pi)]
            truth_by_token = {r["_token"]: r for r in page_truth_rooms}
            target_tokens = [r["_token"] for r in page_truth_rooms]

            anchors = v1.find_room_anchors(pdf_path, pi, target_tokens)
            anchor_points = [pt for pts in anchors.values() for pt in pts]

            feet_per_pt, scale_text = find_scale(doc_id, pi)
            page_result = dict(doc_id=doc_id, page_index=pi, sheet=page_cfg["sheet"],
                                scale_text=scale_text)
            if feet_per_pt is None:
                page_result["verdict"] = "scale_unverified"
                page_result["rows"] = []
                permit_result["pages"].append(page_result)
                continue

            # engine A: rules-v4 (probe29's exact pipeline)
            extracted = extract_drawings(pdf_path, pi)
            out4, diag4 = run_geometry_engine_v4(extracted, feet_per_pt, anchor_points)
            # engine B: model (probe30's exact pipeline)
            outm, diagm = run_geometry_engine_model(pdf_path, pi, clf, feet_per_pt,
                                                     anchor_points, threshold=threshold)
            rooms4 = out4["rooms_all"] if out4 else []
            roomsm = outm["rooms_all"] if outm else []
            dim_words = extract_dim_words(pdf_path, pi)
            final_polys, poly_engine, poly_notes, recon = takeoff.reconcile_dual_engines(
                "v4", rooms4, "model", roomsm, anchors, feet_per_pt, dim_words=dim_words)
            page_result["reconcile"] = {k: v for k, v in recon.items()
                                         if k != "principal_region"}
            print("  reconcile:", json.dumps(page_result["reconcile"], default=str))

            winner_out = out4 if recon["winner"] == "v4" else outm
            if winner_out is None or not final_polys:
                page_result["verdict"] = "no_rooms_either_engine"
                page_result["rows"] = [dict(kind="MISSED_NO_POLYGON", tokens=[t], poly_idx=None,
                                             truth_sqft=truth_by_token[t]["area_sf"])
                                        for t in truth_by_token]
                all_rows.extend(page_result["rows"])
                permit_result["pages"].append(page_result)
                continue

            rows, unlabeled_polys, ambiguous = v1.grade_page(
                final_polys, feet_per_pt, anchors, page_truth_rooms)
            rows, n_demoted = apply_confident_wrong_guard(rows, truth_by_token)
            walls_final = winner_out["walls_final"]
            rows, n_downgraded = apply_merge_scoring_fix(rows, final_polys, walls_final)
            wex = winner_out["extracted"]
            arcs_only_rooms = build_arcs_only_rooms(
                walls_final, wex["arcs"], wex["pw"], wex["ph"], feet_per_pt)
            rows, merge_guard_stats = apply_unit_merge_guard(
                rows, final_polys, truth_by_token, anchors, arcs_only_rooms, feet_per_pt)
            review_killed_polys = winner_out.get("rooms_review_killed", [])
            rows, review_routing_stats = apply_review_killed_routing(
                rows, review_killed_polys, feet_per_pt, anchors)
            # the dual step itself (mirrors takeoff.build_rooms poly_notes)
            rows, n_dual_routed = apply_dual_review_routing(rows, poly_notes)

            page_result.update(verdict="GRADED", n_dual_review_routed=n_dual_routed,
                                n_confident_wrong_demoted=n_demoted, rows=rows)
            all_rows.extend(rows)
            permit_result["pages"].append(page_result)
        finally:
            p = os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf")
            if os.path.exists(p):
                os.remove(p)

    matched = [r for r in all_rows if r["kind"] in ("MATCHED", "MATCHED_NO_AREA")]
    conf_wrong = [r for r in all_rows if r["kind"] == "CONFIDENT_WRONG"]
    dual_review = [r for r in all_rows if r["kind"] == "DUAL_REVIEW"]
    review_killed = [r for r in all_rows if r["kind"] == "REVIEW_KILLED"]
    missed = [r for r in all_rows if r["kind"] == "MISSED_NO_POLYGON"]
    errs = [abs(r["pct_error"]) for r in matched if r.get("pct_error") is not None]
    n_addr = len(addr)
    matched_le_30 = sum(1 for r in matched
                         if r.get("pct_error") is not None and abs(r["pct_error"]) <= 30)
    permit_result["summary"] = dict(
        n_addressable=n_addr,
        n_matched=len(matched),
        n_matched_le_30pct_err=matched_le_30,
        n_confident_wrong=len(conf_wrong),
        n_dual_review=len(dual_review),
        n_review_killed=len(review_killed),
        n_missed_no_polygon=len(missed),
        pct_missed=round(100 * len(missed) / n_addr, 1) if n_addr else None,
        median_abs_pct_error_matched=round(statistics.median(errs), 1) if errs else None,
    )
    print("\nSUMMARY (DUAL):", json.dumps(permit_result["summary"], default=str))
    return permit_result


def main():
    clf = joblib.load(MODEL_PATH)
    threshold = json.load(open(SEG_RESULTS))["fixed_model"]["canonical_threshold"]
    s3 = r2_client()
    results = [process_permit(s3, cfg, clf, threshold) for cfg in v1.PERMITS]

    with open(os.path.join(OUT_DIR, "results_dual.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    n_addr = sum(r["summary"]["n_addressable"] for r in results)
    n_missed = sum(r["summary"]["n_missed_no_polygon"] for r in results)
    n_matched = sum(r["summary"]["n_matched"] for r in results)
    n_le30 = sum(r["summary"]["n_matched_le_30pct_err"] for r in results)
    n_cw = sum(r["summary"]["n_confident_wrong"] for r in results)
    n_dr = sum(r["summary"]["n_dual_review"] for r in results)
    all_errs = [abs(row["pct_error"]) for r in results for pg in r["pages"]
                for row in pg.get("rows", [])
                if row["kind"] == "MATCHED" and row.get("pct_error") is not None]
    scorecard = dict(
        n_addressable_total=n_addr, n_missed_total=n_missed,
        pct_missed=round(100 * n_missed / n_addr, 1) if n_addr else None,
        n_matched_total=n_matched, n_matched_le_30pct_err=n_le30,
        n_confident_wrong_total=n_cw, n_dual_review_total=n_dr,
        median_abs_pct_error_matched=round(statistics.median(all_errs), 1) if all_errs else None,
        rules_v4_reference=dict(missed_pct=33.5, matched_le_30pct=7, median_err_pct=30.6),
        model_reference=dict(missed_pct=26.4, matched_le_30pct=29, median_err_pct=24.6),
    )
    with open(os.path.join(OUT_DIR, "scorecard_dual.json"), "w") as f:
        json.dump(scorecard, f, indent=2, default=str)
    print("\n=== DUAL SCORECARD ===")
    print(json.dumps(scorecard, indent=2, default=str))

    for fn in os.listdir(PDF_TMP_DIR):
        os.remove(os.path.join(PDF_TMP_DIR, fn))
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass


if __name__ == "__main__":
    main()
