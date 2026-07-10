#!/usr/bin/env python3
"""Probe 30 Phase 3.1/3.2 -- DOWNSTREAM grading on the 10 held-out permits:
predicted walls (train-chosen threshold) -> geometry_v4-style snap/close/
polygonize (geometry_model.run_geometry_from_mask) -> compare rooms vs the
permit's OWN layer-truth rooms (matched/missed/merged, total-SF delta).

TRUE rooms: polygonize the CAD wall-LAYER-labeled segments directly (probe25
style: length filter + plain snap_and_close, MIN_SQFT=15/MAX_SQFT=8000) --
this is the page's own ground truth, independent of the model.
PRED rooms: geometry_model.run_geometry_from_mask on the model's predicted
wall mask (train-chosen canonical threshold from segment_results.json),
using the SAME anchor-cluster proximity filter (v4) rules-path production
uses, with anchors found generically via takeoff.py's real_text_anchors
(no truth whitelist -- these permits have no TRUTH_AREA answer key, only
their own wall-layer truth).

Downloads each holdout permit's PDF ONCE (kept locally for the whole
learning-curve sweep -- reused across all N points to avoid 5x redownload),
deletes at the end.

Writes data/probe30/downstream/holdout_results.json (final-model results)
and data/probe30/downstream/learning_curve_downstream.json (matched-rooms
vs N).
"""
import csv
import json
import os
import sys
from collections import defaultdict

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from probe2_sf import r2_client, download_pdf, seg_len, snap_and_close, polygonize_rooms  # noqa: E402
import probe2_sf  # noqa: E402
from geometry_model import run_geometry_from_mask  # noqa: E402
from geometry_v4 import PROXIMITY_GAP_FT  # noqa: E402
import takeoff  # noqa: E402 -- reuse real_text_anchors (ROOM_NUM regex) verbatim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROSTER = os.path.join(ROOT, "data", "probe30", "roster.csv")
FEAT_DIR = os.path.join(ROOT, "data", "probe30", "features")
SEG_RESULTS = os.path.join(ROOT, "data", "probe30", "segment_results.json")
OUT_DIR = os.path.join(ROOT, "data", "probe30", "downstream")
OVERLAY_DIR = os.path.join(ROOT, "data", "probe30", "overlays")
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
for d in (OUT_DIR, OVERLAY_DIR, PDF_TMP_DIR):
    os.makedirs(d, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR

MIN_SQFT, MAX_SQFT = 15, 8000
MERGE_TOL = 0.15
MATCH_MIN_OVERLAP = 0.5


def load_roster_holdout():
    rows = list(csv.DictReader(open(ROSTER)))
    return [r for r in rows if r["split"] == "holdout"]


def true_rooms_from_labels(z, min_seg_frac=0.006):
    p0, p1, y = z["p0"], z["p1"], z["y"]
    pw, ph = float(z["pw"]), float(z["ph"])
    fpp = float(z["fpp"]) or None
    arcs_arr = z["arcs"]
    arcs = [(tuple(a[0]), tuple(a[1])) for a in arcs_arr] if len(arcs_arr) else []
    X_raw = z["X_raw"]
    widths = X_raw[:, 2]
    walls = []
    for i in range(len(p0)):
        if not y[i]:
            continue
        p0i, p1i = tuple(p0[i]), tuple(p1[i])
        L = seg_len(p0i, p1i)
        if L > min_seg_frac * pw:
            walls.append((p0i, p1i, L, float(widths[i])))
    if not walls or fpp is None:
        return [], fpp
    lines, _ = snap_and_close(walls, arcs, pw, feet_per_pt=fpp)
    polys, _ = polygonize_rooms(lines, pw, ph, MIN_SQFT, MAX_SQFT, fpp)
    return polys, fpp


def get_anchor_points(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    anchors = takeoff.real_text_anchors(page)
    doc.close()
    return list(anchors.values())


def match_rooms(true_polys, pred_polys, feet_per_pt):
    """Overlap-based matching: MATCHED (1 true <-> 1 pred, >=50% of true
    area covered by that pred, mutually best), MERGED (>=2 true polys'
    area predominantly -- >=50% each -- covered by the SAME one pred poly,
    combined SF within MERGE_TOL of that pred's SF), else MISSED. Pred
    polys never claimed by any true poly are EXTRA (fabricated/unlabeled)."""
    n_true, n_pred = len(true_polys), len(pred_polys)
    best_pred_for_true = [None] * n_true
    best_frac_for_true = [0.0] * n_true
    for ti, tp in enumerate(true_polys):
        if tp.area == 0:
            continue
        for pi, pp in enumerate(pred_polys):
            if not tp.intersects(pp):
                continue
            inter = tp.intersection(pp).area
            frac = inter / tp.area
            if frac > best_frac_for_true[ti]:
                best_frac_for_true[ti] = frac
                best_pred_for_true[ti] = pi

    claimants = defaultdict(list)
    for ti in range(n_true):
        pi = best_pred_for_true[ti]
        if pi is not None and best_frac_for_true[ti] >= MATCH_MIN_OVERLAP:
            claimants[pi].append(ti)

    rows = []
    claimed_pred = set()
    for pi, tis in claimants.items():
        claimed_pred.add(pi)
        pred_sqft = pred_polys[pi].area * feet_per_pt ** 2
        if len(tis) == 1:
            ti = tis[0]
            true_sqft = true_polys[ti].area * feet_per_pt ** 2
            pct_err = 100 * (pred_sqft - true_sqft) / true_sqft if true_sqft else None
            rows.append(dict(kind="MATCHED", true_idx=[ti], pred_idx=pi,
                              true_sqft=round(true_sqft, 1), pred_sqft=round(pred_sqft, 1),
                              pct_error=round(pct_err, 1) if pct_err is not None else None))
        else:
            true_sqft_sum = sum(true_polys[ti].area * feet_per_pt ** 2 for ti in tis)
            ok = true_sqft_sum > 0 and abs(pred_sqft - true_sqft_sum) / true_sqft_sum <= MERGE_TOL
            rows.append(dict(kind="MERGED_OK" if ok else "MERGED_ERROR", true_idx=tis, pred_idx=pi,
                              true_sqft_sum=round(true_sqft_sum, 1), pred_sqft=round(pred_sqft, 1),
                              pct_error=round(100 * (pred_sqft - true_sqft_sum) / true_sqft_sum, 1)
                              if true_sqft_sum else None))

    matched_true_idx = {ti for r in rows for ti in r["true_idx"]}
    for ti in range(n_true):
        if ti not in matched_true_idx:
            rows.append(dict(kind="MISSED", true_idx=[ti], pred_idx=None,
                              true_sqft=round(true_polys[ti].area * feet_per_pt ** 2, 1)))

    extra_sf = sum(pred_polys[pi].area * feet_per_pt ** 2 for pi in range(n_pred) if pi not in claimed_pred)
    return rows, round(extra_sf, 1), sum(1 for pi in range(n_pred) if pi not in claimed_pred)


def render_downstream_overlay(pdf_path, page_index, true_polys, pred_polys, out_path, target_w=1600):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    zoom = target_w / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(ov)
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        fnt = ImageFont.load_default()
    for pp in pred_polys:
        pts = [(x * zoom, y * zoom) for x, y in pp.exterior.coords]
        dd.polygon(pts, fill=(220, 30, 30, 70), outline=(180, 0, 0, 255))
    for tp in true_polys:
        pts = [(x * zoom, y * zoom) for x, y in tp.exterior.coords]
        dd.polygon(pts, outline=(0, 140, 0, 255))
        c = tp.centroid
        dd.text((c.x * zoom, c.y * zoom), f"{tp.area:.0f}pt2", fill=(0, 90, 0, 255), font=fnt)
    out = Image.alpha_composite(im, ov).convert("RGB")
    out.save(out_path, quality=88)
    doc.close()


def grade_one_permit(row, clf, threshold, s3, pdf_cache, render=False):
    permit, doc_id, page = row["permit"], int(row["doc_id"]), int(row["page"])
    tag = f"{permit}_{doc_id}_p{page}"
    z = np.load(os.path.join(FEAT_DIR, f"{tag}.npz"), allow_pickle=True)
    pw, ph = float(z["pw"]), float(z["ph"])
    fpp = float(z["fpp"]) or None
    arcs_arr = z["arcs"]
    arcs = [(tuple(a[0]), tuple(a[1])) for a in arcs_arr] if len(arcs_arr) else []
    p0, p1 = z["p0"], z["p1"]
    widths = z["X_raw"][:, 2]

    true_polys, fpp_true = true_rooms_from_labels(z)
    if fpp is None:
        return dict(tag=tag, verdict="scale_unverified", reason="no scale note on page")

    if doc_id not in pdf_cache:
        pdf_cache[doc_id] = download_pdf(s3, doc_id)
    pdf_path = pdf_cache[doc_id]
    anchor_points = get_anchor_points(pdf_path, page)

    X_fixed = z["X_fixed"]
    proba = clf.predict_proba(X_fixed)[:, 1]
    mask = proba >= threshold

    out, diag = run_geometry_from_mask(p0, p1, widths, arcs, pw, ph, fpp, mask, anchor_points,
                                        min_sqft=MIN_SQFT, max_sqft=MAX_SQFT,
                                        gap_ft=PROXIMITY_GAP_FT)
    result = dict(tag=tag, permit=permit, doc_id=doc_id, page=page,
                  fpp=fpp, n_true_rooms=len(true_polys),
                  true_total_sqft=round(sum(p.area * fpp ** 2 for p in true_polys), 1),
                  engine_diag={k: v for k, v in diag.items()
                               if k not in ("anchor_cluster_false_positive_suspects",)})
    if out is None:
        result["verdict"] = diag.get("verdict", "no_rooms")
        result["n_pred_rooms"] = 0
        result["match_rows"] = []
        result["n_matched"] = 0
        result["n_missed"] = len(true_polys)
        result["n_merged_ok"] = 0
        result["n_merged_error"] = 0
        result["extra_sf"] = 0.0
        return result

    pred_polys = out["rooms_all"]
    rows, extra_sf, n_extra_polys = match_rooms(true_polys, pred_polys, fpp)
    result["verdict"] = "graded"
    result["n_pred_rooms"] = len(pred_polys)
    result["pred_total_sqft"] = round(sum(p.area * fpp ** 2 for p in pred_polys), 1)
    result["match_rows"] = rows
    result["n_matched"] = sum(1 for r in rows if r["kind"] == "MATCHED")
    result["n_missed"] = sum(1 for r in rows if r["kind"] == "MISSED")
    result["n_merged_ok"] = sum(1 for r in rows if r["kind"] == "MERGED_OK")
    result["n_merged_error"] = sum(1 for r in rows if r["kind"] == "MERGED_ERROR")
    result["n_extra_pred_polys"] = n_extra_polys
    result["extra_sf"] = extra_sf
    errs = [abs(r["pct_error"]) for r in rows if r["kind"] == "MATCHED" and r.get("pct_error") is not None]
    result["median_abs_pct_error_matched"] = round(float(np.median(errs)), 1) if errs else None

    if render:
        overlay_path = os.path.join(OVERLAY_DIR, f"downstream_{tag}.jpg")
        render_downstream_overlay(pdf_path, page, true_polys, pred_polys, overlay_path)
        result["overlay_path"] = os.path.relpath(overlay_path, ROOT)
    return result


def main():
    holdout_rows = load_roster_holdout()
    seg_results = json.load(open(SEG_RESULTS))
    clf = joblib.load(os.path.join(ROOT, "models", "wall_model_v2.joblib"))
    threshold = seg_results["fixed_model"]["canonical_threshold"]
    print(f"final model canonical threshold = {threshold}")

    s3 = r2_client()
    pdf_cache = {}
    final_results = []
    for row in holdout_rows:
        r = grade_one_permit(row, clf, threshold, s3, pdf_cache, render=True)
        print(json.dumps({k: v for k, v in r.items() if k != "match_rows" and k != "engine_diag"}, default=str))
        final_results.append(r)

    with open(os.path.join(OUT_DIR, "holdout_results.json"), "w") as f:
        json.dump(final_results, f, indent=2, default=str)

    # ---------------- learning curve downstream (matched rooms vs N) ----------------
    lc_out = []
    for entry in seg_results["learning_curve"]:
        n = entry["n_train_permits"]
        model_path = os.path.join(ROOT, entry["model_path"])
        clf_n = joblib.load(model_path)
        t_n = entry["canonical_threshold"]
        n_matched_total, n_missed_total, n_true_total = 0, 0, 0
        for row in holdout_rows:
            r = grade_one_permit(row, clf_n, t_n, s3, pdf_cache, render=False)
            n_matched_total += r.get("n_matched", 0)
            n_missed_total += r.get("n_missed", 0)
            n_true_total += r.get("n_true_rooms", 0)
        lc_out.append(dict(n_train_permits=n, pooled_holdout_pr_auc=entry["pooled_holdout_pr_auc"],
                            n_matched_total=n_matched_total, n_missed_total=n_missed_total,
                            n_true_total=n_true_total,
                            matched_frac=round(n_matched_total / n_true_total, 3) if n_true_total else None))
        print("learning curve downstream:", lc_out[-1])

    with open(os.path.join(OUT_DIR, "learning_curve_downstream.json"), "w") as f:
        json.dump(lc_out, f, indent=2, default=str)

    for doc_id, path in pdf_cache.items():
        if os.path.exists(path):
            os.remove(path)
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
