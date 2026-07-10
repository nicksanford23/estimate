#!/usr/bin/env python3
"""Probe 30 Phase 3 -- MODEL-AS-ENGINE geometry: same v2 gap-closer / cavity
filter + v4 anchor-cluster proximity-reconnection shape as
geometry_v2.run_geometry_engine_v2 / geometry_v4.run_geometry_engine_v4, but
wall CANDIDATES come from the trained segment classifier (wall_model_v2)
instead of the rules-path two_tier_wall_candidates() selection. This is the
"layerless path" the promotion gate (improvement-loop skill) is judging.

Everything downstream of wall-candidate selection (gap closing, cavity/hatch
filter, anchor-cluster proximity reconnection) is REUSED UNCHANGED from
geometry_v2/geometry_v4 -- only the wall-selection step is swapped for a
model prediction. This isolates the comparison to exactly the thing being
tested (rules wall-picking vs learned wall-picking), not a different
downstream pipeline.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import seg_len, polygonize_rooms  # noqa: E402
from geometry_v2 import snap_and_close_v2, filter_cavity_hatch  # noqa: E402
from geometry_v4 import filter_anchor_clusters_v4, PROXIMITY_GAP_FT  # noqa: E402
from probe30_extract_worker import extract_all_segments, compute_features  # noqa: E402

MIN_SEG_FRAC = 0.006  # same minimum-length-to-count-as-a-wall-candidate probe25 used


def predict_wall_mask(pdf_path, page_index, clf, feet_per_pt, threshold=0.5):
    """Runs the SAME feature pipeline used at training time (probe30's
    'fixed' 10-feature set) and returns (segs, arcs, pw, ph, mask, proba)."""
    segs, arcs, pw, ph = extract_all_segments(pdf_path, page_index)
    if not segs:
        return segs, arcs, pw, ph, None, None
    _, X_fixed, _ = compute_features(segs, pw, ph, feet_per_pt)
    proba = clf.predict_proba(X_fixed)[:, 1]
    mask = proba >= threshold
    return segs, arcs, pw, ph, mask, proba


def run_geometry_from_mask(p0_arr, p1_arr, widths_arr, arcs, pw, ph, feet_per_pt,
                            mask, anchor_points, min_sqft=15, max_sqft=5000,
                            enable_anchor_filter=True, gap_ft=PROXIMITY_GAP_FT,
                            extra_diag=None):
    """Geometry engine from ALREADY-COMPUTED per-segment arrays + a boolean
    wall mask -- no PDF / feature re-extraction. Used both by
    run_geometry_engine_model (fresh PDF) and by the learning-curve loop
    (cached probe30 features, only the model/threshold varies per point)."""
    diag = dict(engine_version="model")
    if extra_diag:
        diag.update(extra_diag)
    diag["n_pred_wall"] = int(mask.sum())
    diag["pred_wall_frac"] = round(float(mask.mean()), 4) if len(mask) else 0.0

    walls_final = []
    for i in range(len(p0_arr)):
        if not mask[i]:
            continue
        p0, p1 = tuple(p0_arr[i]), tuple(p1_arr[i])
        L = seg_len(p0, p1)
        if L > MIN_SEG_FRAC * pw:
            walls_final.append((p0, p1, L, float(widths_arr[i])))
    diag["n_wall_candidates_after_len_filter"] = len(walls_final)
    if not walls_final:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = "model predicted zero wall-length-qualifying segments"
        return None, diag

    lines_ls, gap_info = snap_and_close_v2(walls_final, arcs, pw, feet_per_pt=feet_per_pt)
    diag["gap_closing_v2"] = gap_info

    rooms_pre_filter, n_faces = polygonize_rooms(lines_ls, pw, ph, min_sqft, max_sqft, feet_per_pt)
    diag["n_polygon_faces_total"] = n_faces
    diag["n_rooms_pre_cavity_filter"] = len(rooms_pre_filter)

    rooms_all, killed, kept_idx = filter_cavity_hatch(rooms_pre_filter, feet_per_pt)
    diag["n_cavity_hatch_killed"] = len(killed)
    diag["cavity_hatch_killed_sf"] = round(sum(k["sqft"] for k in killed), 1)
    diag["n_rooms_all"] = len(rooms_all)

    if not rooms_all:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = "no room-sized polygons closed at all (model engine)"
        return None, diag

    largest_sqft = max(p.area * feet_per_pt ** 2 for p in rooms_all)
    total_sqft = sum(p.area * feet_per_pt ** 2 for p in rooms_all)
    audit_ok = 30 <= largest_sqft <= 10000 and 30 <= total_sqft <= 200000
    diag.update(largest_room_sqft=round(largest_sqft, 1),
                total_sqft_all_polys=round(total_sqft, 1), audit_ok=audit_ok)
    if not audit_ok:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = f"self-audit failed: largest={largest_sqft:.0f} total={total_sqft:.0f}"
        return None, diag

    diag["verdict"] = "engine_ok"
    out2 = dict(rooms_all=rooms_all, extracted=dict(pw=pw, ph=ph, arcs=arcs),
                feet_per_pt=feet_per_pt, lines_ls=lines_ls, walls_final=walls_final,
                rooms_pre_filter=rooms_pre_filter)

    if not enable_anchor_filter:
        diag["anchor_cluster_filter_applied"] = False
        return out2, diag

    ac = filter_anchor_clusters_v4(rooms_all, anchor_points, feet_per_pt, gap_ft)
    review_polys = [rooms_all[i] for i in ac["review_killed_idx"]]
    artifact_polys = [rooms_all[i] for i in ac["artifact_idx"]]
    review_sf = sum(p.area * feet_per_pt ** 2 for p in review_polys)
    artifact_sf = sum(p.area * feet_per_pt ** 2 for p in artifact_polys)

    diag["anchor_cluster_filter_applied"] = True
    diag["anchor_cluster_gap_ft"] = gap_ft
    diag["anchor_cluster_n_islands_total"] = ac["n_islands_total"]
    diag["anchor_cluster_n_anchored_islands"] = ac["n_anchored_islands"]
    diag["anchor_cluster_n_reconnected_islands"] = ac["n_reconnected_islands"]
    diag["anchor_cluster_n_still_unanchored_islands"] = ac["n_still_unanchored_islands"]
    diag["anchor_cluster_n_polys_killed"] = len(ac["killed_idx"])
    diag["anchor_cluster_sf_killed"] = round(review_sf + artifact_sf, 1)
    diag["anchor_cluster_n_polys_review_killed"] = len(ac["review_killed_idx"])
    diag["anchor_cluster_sf_review_killed"] = round(review_sf, 1)
    diag["anchor_cluster_n_polys_artifact"] = len(ac["artifact_idx"])
    diag["anchor_cluster_sf_artifact"] = round(artifact_sf, 1)
    diag["anchor_cluster_false_positive_suspects"] = ac["false_positive_suspects"]

    rooms_all_new = [rooms_all[i] for i in ac["kept_idx"]]
    out2["rooms_all_pre_anchor_filter"] = rooms_all
    out2["rooms_all"] = rooms_all_new
    out2["rooms_review_killed"] = review_polys
    out2["rooms_artifact_killed"] = artifact_polys
    out2["anchor_cluster_diag"] = ac
    return out2, diag


def run_geometry_engine_model(pdf_path, page_index, clf, feet_per_pt, anchor_points,
                               min_sqft=15, max_sqft=5000, threshold=0.5,
                               enable_anchor_filter=True, gap_ft=PROXIMITY_GAP_FT):
    """Fresh-PDF entry point: extracts segments, computes the probe30
    'fixed' feature set, predicts the wall mask, then delegates to
    run_geometry_from_mask for everything downstream."""
    segs, arcs, pw, ph = extract_all_segments(pdf_path, page_index)
    if not segs:
        return None, dict(engine_version="model", n_segs_total=0,
                           verdict="scale_unverified",
                           reason="no vector segments on page (raster/flattened, out of Route A scope)")
    _, X_fixed, _ = compute_features(segs, pw, ph, feet_per_pt)
    proba = clf.predict_proba(X_fixed)[:, 1]
    mask = proba >= threshold
    p0_arr = np.array([s[0] for s in segs])
    p1_arr = np.array([s[1] for s in segs])
    widths_arr = np.array([s[3] for s in segs])
    return run_geometry_from_mask(
        p0_arr, p1_arr, widths_arr, arcs, pw, ph, feet_per_pt, mask, anchor_points,
        min_sqft=min_sqft, max_sqft=max_sqft, enable_anchor_filter=enable_anchor_filter,
        gap_ft=gap_ft, extra_diag=dict(n_segs_total=len(segs), threshold=threshold))
