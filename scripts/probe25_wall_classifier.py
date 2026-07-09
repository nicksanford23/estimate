#!/usr/bin/env python3
"""Probe 25 — first vector wall-segment classifier baseline.

HYPOTHESIS: a classifier using only layer-FREE geometric features can find
wall segments in vector floor plans well enough that the existing
snap_and_close -> polygonize pipeline still closes rooms on the PREDICTED
walls -- i.e. ML can stand in for named CAD layers on layerless PDFs.

Labels come free: page.get_drawings()["layer"] -> probe8's classify_layer()
-> 1 if "wall" else 0. NO layer info is used as a MODEL FEATURE (leak-free);
it is only used to build y and to build the "truth" polygons for the
downstream check.

Data (see experiments/probe25_wall_classifier.md for the eyeball/closure
audit that produced this list):
  - 14-11290-NEWC   doc 1494156  page 3          (bank, clean CMU/stud)
  - 26-10321-RNVN   doc 9058456  pages 14-18      (office reno, clean NEW/EXIST
    WALL 2D, 5 sibling floor-plan pages of ONE permit -- kept in one
    leave-one-PERMIT-out fold, never split across train/test)
  - 23-05848-RNVS   doc 7888241  page 0           (Spotted Cat, A-WALL/A-WALL-EXT)
  EXCLUDED after eyeball + closure test (see probe25 writeup):
  - 20-21673-RNVS (wall layers literally named *_HATCH*, closure largest_frac
    0.018 on 168 "long" segments -> ~466 fragments)
  - 19-00670-RNVS (looks like clean centerlines at a glance, but 15k raw
    segments on ONE wall layer polygonize into 7022 fragments, largest
    single room only 67 sqft on a building whose plan reads ~7100 sqft
    footprint -- same failure signature as the excluded 25-33341 .3D solid:
    bad wall REPRESENTATION, not bad tolerance)
  - 25-33341-NEWC, 24-22310-RNVN excluded per task spec (.3D solid / hatch)

Usage:
  python3 scripts/probe25_wall_classifier.py            # full run
  python3 scripts/probe25_wall_classifier.py --cache-only  # reuse cached features
"""
import json
import math
import os
import re
import sys
import time
from collections import defaultdict

import numpy as np
import fitz
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.ops import unary_union, polygonize
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, precision_recall_curve

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe8_layer_classes import classify_layer          # noqa: E402
from probe2_sf import (                                   # noqa: E402
    ROOT, r2_client, download_pdf, seg_len, dominant_angle,
    snap_and_close, polygonize_rooms,
)

OUT = os.path.join(ROOT, "data", "probe25")
PDF_TMP = os.path.join(OUT, "_pdf_tmp")
CACHE = os.path.join(OUT, "_features_cache")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PDF_TMP, exist_ok=True)
os.makedirs(CACHE, exist_ok=True)

SCALE_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*\"?\s*=\s*1\s*'\s*-?\s*0?\"?", re.IGNORECASE)

# 26-10321's scale note lives on a trimmed sheet the pagetext regex can't
# reach (probe24 finding: had to read it by vision -> 1/8" = 1'-0"). Rather
# than re-derive it here, reuse that vision-verified value so downstream SF
# numbers for this permit are not silently computed off a garbage fallback.
SCALE_OVERRIDE = {
    9058456: (0.11111, "1/8\" = 1'-0\" (vision-verified, probe24)"),
}

PAGES = [
    dict(permit="14-11290-NEWC", doc_id=1494156, page_index=3),
    dict(permit="23-05848-RNVS", doc_id=7888241, page_index=0),
    dict(permit="26-10321-RNVN", doc_id=9058456, page_index=14),
    dict(permit="26-10321-RNVN", doc_id=9058456, page_index=15),
    dict(permit="26-10321-RNVN", doc_id=9058456, page_index=16),
    dict(permit="26-10321-RNVN", doc_id=9058456, page_index=17),
    dict(permit="26-10321-RNVN", doc_id=9058456, page_index=18),
]

FEATURE_NAMES = [
    "norm_length", "angle_rel_dom_deg", "stroke_width", "fill_flag", "dash_flag",
    "nearest_parallel_dist_norm", "local_density", "dist_from_margin_norm",
    "collinear_chain_len_norm",
]


# ------------------------------------------------------------- extraction --

def extract_all_segments(pdf_path, page_index):
    """ALL vector line-ish primitives on the page: 'l' items, plus thin
    filled rects synthesized to a centerline (walls-as-fill representation,
    same convention as probe2/probe7). Curves ('c', mostly door-swing arcs)
    are NOT included -- they are not wall candidates."""
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    segs = []  # (p0, p1, layer, width, fill_flag, dash_flag)
    for d in page.get_drawings():
        layer = d.get("layer")
        width = d.get("width") or 0.0
        is_fill = d.get("fill") is not None and d.get("type") in ("f", "fs")
        dashes = d.get("dashes")
        dash_flag = 1 if dashes and dashes not in ("[] 0", "") else 0
        for item in d.get("items", []):
            if item[0] == "l":
                p0, p1 = (item[1].x, item[1].y), (item[2].x, item[2].y)
                if p0 == p1:
                    continue
                segs.append((p0, p1, layer, width, 1 if is_fill else 0, dash_flag))
            elif item[0] == "re":
                r = item[1]
                rw, rh = r.width, r.height
                short, long = min(rw, rh), max(rw, rh)
                if is_fill and long > 0 and short / pw < 0.02 and long / max(pw, ph) > 0.01:
                    cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
                    if rw >= rh:
                        p0, p1 = (r.x0, cy), (r.x1, cy)
                    else:
                        p0, p1 = (cx, r.y0), (cx, r.y1)
                    segs.append((p0, p1, layer, short, 1, dash_flag))
    doc.close()
    return segs, pw, ph


def page_scale(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    text = doc[page_index].get_text()
    doc.close()
    m = SCALE_RE.findall(text)
    if not m:
        return None, None
    counts = defaultdict(int)
    for num, den in m:
        counts[(int(num), int(den))] += 1
    (num, den), _ = max(counts.items(), key=lambda kv: kv[1])
    feet_per_pt = (den / num) / 72.0
    return feet_per_pt, f"{num}/{den}\" = 1'-0\""


# ------------------------------------------------------------- features --

def circ_dist(a, b, mod):
    d = np.abs(a - b) % mod
    return np.minimum(d, mod - d)


def compute_features(segs, pw, ph):
    N = len(segs)
    P0 = np.array([s[0] for s in segs], dtype=float)
    P1 = np.array([s[1] for s in segs], dtype=float)
    widths = np.array([s[3] for s in segs], dtype=float)
    fill = np.array([s[4] for s in segs], dtype=float)
    dash = np.array([s[5] for s in segs], dtype=float)
    layers = [s[2] for s in segs]
    labels = np.array([1 if classify_layer(l) == "wall" else 0 for l in layers], dtype=int)

    dx = P1[:, 0] - P0[:, 0]
    dy = P1[:, 1] - P0[:, 1]
    L = np.hypot(dx, dy)
    mid = (P0 + P1) / 2.0
    ang90 = np.degrees(np.arctan2(dy, dx)) % 90.0
    ang180 = np.degrees(np.arctan2(dy, dx)) % 180.0

    # dominant angle: reuse the skill's own histogram fn (min-length filtered)
    dom = dominant_angle([(tuple(p0), tuple(p1), w) for p0, p1, w in
                           zip(P0.tolist(), P1.tolist(), widths.tolist())], pw)
    domA = dom % 90.0
    d1 = np.abs(ang90 - domA)
    d2 = np.abs(ang90 - domA - 90)
    d3 = np.abs(ang90 - domA + 90)
    angle_rel_dom = np.minimum(np.minimum(d1, d2), d3)

    norm_length = L / pw
    dist_margin = np.minimum.reduce(
        [mid[:, 0], pw - mid[:, 0], mid[:, 1], ph - mid[:, 1]]) / pw

    # local density: # of OTHER segment midpoints within 2% of page width
    tree = cKDTree(mid)
    r = 0.02 * pw
    density = tree.query_ball_point(mid, r, return_length=True).astype(float) - 1.0
    density = np.clip(density, 0, None)

    # dist-to-nearest-parallel + collinear-chain-length: two reference frames
    # (dominant axis, its perpendicular), each segment assigned to whichever
    # its own direction is closer to; work in that frame's (normal, tangent)
    # rotated coords.
    frameA_deg = domA
    frameB_deg = (domA + 90) % 180
    dA = circ_dist(ang180, frameA_deg % 180, 180.0)
    dB = circ_dist(ang180, frameB_deg, 180.0)
    frame = (dB < dA).astype(int)  # 0 -> frame A, 1 -> frame B

    dist_parallel = np.full(N, pw, dtype=float)   # default: "far" (no mate)
    chain_len = L.copy()                           # default: chain of 1 (itself)

    def rotcoord(angle_deg, pts):
        th = math.radians(angle_deg)
        tx, ty = math.cos(th), math.sin(th)
        nx, ny = -ty, tx
        n = pts[:, 0] * nx + pts[:, 1] * ny
        t = pts[:, 0] * tx + pts[:, 1] * ty
        return n, t

    for f, fdeg in ((0, frameA_deg), (1, frameB_deg)):
        idx = np.where(frame == f)[0]
        if len(idx) < 2:
            continue
        n_f, t_f = rotcoord(fdeg, mid[idx])

        # nearest-parallel proxy: 2D KDTree in (n, t) space, k=2 (self + 1)
        pts = np.column_stack([n_f, t_f])
        tf_tree = cKDTree(pts)
        dists, _ = tf_tree.query(pts, k=min(2, len(idx)))
        if dists.ndim == 1:
            dists = dists[:, None]
        nn = dists[:, 1] if dists.shape[1] > 1 else np.full(len(idx), pw)
        dist_parallel[idx] = nn

        # collinear chain: bucket by n (tol), then merge along t (gap tol)
        tol_n = 0.003 * pw
        gap_tol = 0.01 * pw
        order_n = np.argsort(n_f)
        n_sorted = n_f[order_n]
        bounds = [0]
        for i in range(1, len(n_sorted)):
            if n_sorted[i] - n_sorted[i - 1] > tol_n:
                bounds.append(i)
        bounds.append(len(n_sorted))
        for bi in range(len(bounds) - 1):
            grp = order_n[bounds[bi]:bounds[bi + 1]]
            if len(grp) == 1:
                continue
            gt = t_f[grp]
            order_t = np.argsort(gt)
            gt_sorted = gt[order_t]
            cid = np.zeros(len(grp), dtype=int)
            c = 0
            for i in range(1, len(grp)):
                if gt_sorted[i] - gt_sorted[i - 1] > gap_tol:
                    c += 1
                cid[i] = c
            Lg = L[idx[grp]][order_t]
            for cc in range(c + 1):
                m = cid == cc
                total = Lg[m].sum()
                members = idx[grp[order_t[m]]]
                chain_len[members] = total

    dist_parallel_norm = dist_parallel / pw
    chain_len_norm = chain_len / pw

    X = np.column_stack([
        norm_length, angle_rel_dom, widths, fill, dash,
        dist_parallel_norm, density, dist_margin, chain_len_norm,
    ])
    return X, labels


# ------------------------------------------------------------- pipeline --

def load_page(page_def, s3):
    tag = f"{page_def['permit']}_{page_def['doc_id']}_p{page_def['page_index']}"
    cache_path = os.path.join(CACHE, f"{tag}.npz")
    if os.path.exists(cache_path):
        z = np.load(cache_path, allow_pickle=True)
        return z["X"], z["y"], z["p0"], z["p1"], float(z["pw"]), float(z["ph"]), tag

    pdf = download_pdf(s3, page_def["doc_id"])
    t0 = time.time()
    segs, pw, ph = extract_all_segments(pdf, page_def["page_index"])
    X, y = compute_features(segs, pw, ph)
    p0 = np.array([s[0] for s in segs])
    p1 = np.array([s[1] for s in segs])
    print(f"  {tag}: {len(segs)} segments, {y.sum()} wall-labeled "
          f"({100*y.mean():.1f}%)  [{time.time()-t0:.1f}s]")
    np.savez_compressed(cache_path, X=X, y=y, p0=p0, p1=p1, pw=pw, ph=ph)
    return X, y, p0, p1, pw, ph, tag


def cleanup_pdfs():
    for f in os.listdir(PDF_TMP):
        try:
            os.remove(os.path.join(PDF_TMP, f))
        except OSError:
            pass


# -------------------------------------------------------- downstream eval --

def polys_from_labels(p0, p1, mask, pw, ph, feet_per_pt):
    """mask -> wall tuples -> snap_and_close -> polygonize_rooms."""
    walls = [(tuple(p0[i]), tuple(p1[i]), seg_len(p0[i], p1[i]), 1.0)
             for i in np.where(mask)[0] if seg_len(p0[i], p1[i]) > 0.006 * pw]
    if not walls:
        return []
    lines, _ = snap_and_close(walls, [], pw, feet_per_pt=feet_per_pt)
    polys, _ = polygonize_rooms(lines, pw, ph, 15, 20000, feet_per_pt)
    return polys


def match_rooms(true_polys, pred_polys, area_tol=0.20):
    """Match by centroid containment + area within +/-20%. Returns list of
    (true_idx, pred_idx or None, true_sqft, pred_sqft or None, matched)."""
    rows = []
    used_pred = set()
    for ti, tp in enumerate(true_polys):
        c = tp.centroid
        best = None
        for pi, pp in enumerate(pred_polys):
            if pi in used_pred:
                continue
            if pp.contains(c) or c.distance(pp) < 1e-6:
                ratio = pp.area / tp.area if tp.area else 0
                if abs(ratio - 1) <= area_tol:
                    best = pi
                    break
        if best is not None:
            used_pred.add(best)
        rows.append(dict(true_idx=ti, pred_idx=best, matched=best is not None))
    return rows


def render_downstream_overlay(pdf_path, page_index, true_polys, pred_polys, out_path,
                               target_w=1600):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    zoom = target_w / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(ov)
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
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


# ------------------------------------------------------------------ main --

def main():
    s3 = r2_client()
    per_page = []
    print("=== loading / extracting features (per page) ===")
    for pd_ in PAGES:
        X, y, p0, p1, pw, ph, tag = load_page(pd_, s3)
        per_page.append(dict(permit=pd_["permit"], doc_id=pd_["doc_id"],
                              page_index=pd_["page_index"], X=X, y=y, p0=p0, p1=p1,
                              pw=pw, ph=ph, tag=tag))
    cleanup_pdfs()

    permits = sorted(set(p["permit"] for p in per_page))
    print(f"\npermits: {permits}")

    all_results = {"segment_level": {}, "downstream": {}, "threshold_sweeps": {}}

    for held_out in permits:
        train_pages = [p for p in per_page if p["permit"] != held_out]
        test_pages = [p for p in per_page if p["permit"] == held_out]

        X_train = np.concatenate([p["X"] for p in train_pages])
        y_train = np.concatenate([p["y"] for p in train_pages])
        X_test = np.concatenate([p["X"] for p in test_pages])
        y_test = np.concatenate([p["y"] for p in test_pages])

        clf = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.08, max_depth=6,
            class_weight="balanced", random_state=0)
        clf.fit(X_train, y_train)

        # threshold chosen on TRAINING data only (best F1 via 5-fold-free proxy:
        # score train set itself -- simple, defensible for a smoke test; we are
        # not claiming this generalizes, just recording the canonical choice)
        train_scores = clf.predict_proba(X_train)[:, 1]
        best_f1, best_t = -1, 0.5
        for t in np.linspace(0.05, 0.95, 19):
            pred = train_scores >= t
            tp = np.sum(pred & (y_train == 1))
            fp = np.sum(pred & (y_train == 0))
            fn = np.sum((~pred) & (y_train == 1))
            prec = tp / (tp + fp) if (tp + fp) else 0
            rec = tp / (tp + fn) if (tp + fn) else 0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
            if f1 > best_f1:
                best_f1, best_t = f1, t
        canonical_t = round(float(best_t), 2)

        test_scores = clf.predict_proba(X_test)[:, 1]
        ap = average_precision_score(y_test, test_scores) if y_test.sum() else float("nan")

        sweep = []
        for t in np.linspace(0.1, 0.9, 9):
            pred = test_scores >= t
            tp = np.sum(pred & (y_test == 1))
            fp = np.sum(pred & (y_test == 0))
            fn = np.sum((~pred) & (y_test == 1))
            prec = tp / (tp + fp) if (tp + fp) else 0
            rec = tp / (tp + fn) if (tp + fn) else 0
            sweep.append(dict(t=round(float(t), 2), precision=round(float(prec), 3),
                               recall=round(float(rec), 3), n_pred=int(pred.sum())))

        pred_canon = test_scores >= canonical_t
        tp = np.sum(pred_canon & (y_test == 1))
        fp = np.sum(pred_canon & (y_test == 0))
        fn = np.sum((~pred_canon) & (y_test == 1))
        prec_c = tp / (tp + fp) if (tp + fp) else 0
        rec_c = tp / (tp + fn) if (tp + fn) else 0

        print(f"\n=== held out permit: {held_out} ===")
        print(f"  train segs={len(y_train)} (wall={y_train.sum()})  "
              f"test segs={len(y_test)} (wall={y_test.sum()})")
        print(f"  canonical threshold (train-chosen): {canonical_t}")
        print(f"  held-out @ canonical: precision={prec_c:.3f} recall={rec_c:.3f} PR-AUC={ap:.3f}")
        print(f"  held-out sweep: {sweep}")

        all_results["segment_level"][held_out] = dict(
            canonical_threshold=canonical_t, pr_auc=round(float(ap), 3),
            precision_at_canonical=round(float(prec_c), 3),
            recall_at_canonical=round(float(rec_c), 3),
            n_train_segs=int(len(y_train)), n_train_wall=int(y_train.sum()),
            n_test_segs=int(len(y_test)), n_test_wall=int(y_test.sum()),
        )
        all_results["threshold_sweeps"][held_out] = sweep

        # ---- downstream, per test page ----
        offset = 0
        downstream_pages = []
        for tp_ in test_pages:
            n = len(tp_["y"])
            y_page = y_test[offset:offset + n]
            score_page = test_scores[offset:offset + n]
            offset += n
            pred_mask = score_page >= canonical_t

            pdf = download_pdf(s3, tp_["doc_id"])
            fpp, scale_text = page_scale(pdf, tp_["page_index"])
            if fpp is None and tp_["doc_id"] in SCALE_OVERRIDE:
                fpp, scale_text = SCALE_OVERRIDE[tp_["doc_id"]]
            scale_unverified = fpp is None
            if fpp is None:
                fpp = 0.1  # scale-free fallback; SF numbers flagged unscaled below

            true_polys = polys_from_labels(tp_["p0"], tp_["p1"], y_page.astype(bool),
                                            tp_["pw"], tp_["ph"], fpp)
            pred_polys = polys_from_labels(tp_["p0"], tp_["p1"], pred_mask,
                                            tp_["pw"], tp_["ph"], fpp)
            match = match_rooms(true_polys, pred_polys)
            n_recovered = sum(1 for r in match if r["matched"])
            true_sqft = sum(p.area for p in true_polys) * fpp ** 2
            pred_sqft = sum(p.area for p in pred_polys) * fpp ** 2
            sqft_delta_pct = (100 * (pred_sqft - true_sqft) / true_sqft
                               if true_sqft else float("nan"))

            overlay_path = os.path.join(OUT, f"overlay_{tp_['tag']}.jpg")
            render_downstream_overlay(pdf, tp_["page_index"], true_polys, pred_polys,
                                       overlay_path)

            print(f"    page {tp_['tag']}: scale={scale_text}  "
                  f"true_rooms={len(true_polys)} pred_rooms={len(pred_polys)} "
                  f"recovered={n_recovered}/{len(true_polys)}  "
                  f"true_sqft={true_sqft:.0f} pred_sqft={pred_sqft:.0f} "
                  f"delta={sqft_delta_pct:.1f}%")

            downstream_pages.append(dict(
                tag=tp_["tag"], doc_id=tp_["doc_id"], page_index=tp_["page_index"],
                scale_text=scale_text, fpp_used=fpp, scale_unverified=scale_unverified,
                n_true_rooms=len(true_polys), n_pred_rooms=len(pred_polys),
                n_recovered=n_recovered, true_sqft=round(true_sqft, 1),
                pred_sqft=round(pred_sqft, 1), sqft_delta_pct=round(sqft_delta_pct, 1)
                if true_sqft else None,
                overlay_path=os.path.relpath(overlay_path, ROOT),
            ))
            cleanup_pdfs()

        all_results["downstream"][held_out] = downstream_pages

    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print("\n=== DONE. results.json + overlays written to data/probe25/ ===")


if __name__ == "__main__":
    main()
