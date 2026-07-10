#!/usr/bin/env python3
"""Probe 30 Phase 1 -- feature extraction worker (runs LOCAL or on a RunPod
CPU pod; self-contained, no .env / ROOT import chain so it survives being
shipped alone). R2 creds come from os.environ (matches deploy_pod.py's
container env pattern) with a .env fallback for local runs.

For each (doc_id, page_index) row in the input roster CSV:
  1. download docs/<doc_id>.pdf from R2 (skip if a feature npz already
     exists in R2 at OUT_PREFIX/<tag>.npz -- resumable)
  2. extract ALL vector line-ish segments (fitz get_drawings()) + arcs
  3. label = 1 iff classify_layer(layer) == "wall" (probe8 ontology;
     layer info used ONLY for the label, never as a model feature)
  4. compute features -- TWO variants cached together:
       X_raw  : probe25's original 9 features, UNCHANGED (raw stroke_width,
                page-width-normalized distances always) -- the ablation
                baseline reproduction.
       X_fixed: probe25's two known fixes applied
                (a) stroke_width -> per-page PERCENTILE RANK (bucketed),
                    not a raw point value
                (b) length/nearest-parallel-dist/local-density-radius/
                    margin-dist/collinear-chain-len -> REAL FEET via the
                    page's own fpp (pagetext-regex-free: parsed straight off
                    the downloaded PDF's own text) where derivable; else the
                    same page-width-relative fallback probe25 always used.
                PLUS one new diagnostic feature `has_scale` (1 if fpp came
                from a real regex match, 0 if page-width fallback) appended.
  5. BUDGET GUARD: if a page has >150k total segments, sample NON-wall
     segments down to 150k (keep ALL wall segments), note it in meta.
  6. cache one npz per page: X_raw, X_fixed, y, p0, p1, pw, ph, fpp,
     scale_text, has_scale, sampled(bool), n_segs_total, tag
  7. upload npz to R2 claude-repo/probe30_features/<tag>.npz; delete local
     pdf + npz immediately (disk is tight / shared box).

Usage:
  python3 scripts/probe30_extract_worker.py --roster data/probe30/roster.csv \
      --workers 14 --out-prefix claude-repo/probe30_features
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import time
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import boto3
import fitz
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    env = dict(os.environ)
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env.setdefault(k, v)
    return env


ENV = load_env()
LOCAL_TMP = os.path.join("/tmp", "probe30_worker")
os.makedirs(LOCAL_TMP, exist_ok=True)

WALL_RE = re.compile(r"wall|cmu|stud|gyp|stucco|partition|mason", re.I)
ANNOT_RE = re.compile(r"tag|label|note|\bdim|text|title|bord|ref\b|leader|anno|symbol|keynote|\bkey\b|schedule|legend", re.I)
SCALE_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*\"?\s*=\s*1\s*'\s*-?\s*0?\"?", re.IGNORECASE)

SCALE_OVERRIDE = {9058456: (0.11111, "1/8\" = 1'-0\" (vision-verified, probe24/25)")}

MAX_SEGS = 150_000

FEATURE_NAMES_RAW = [
    "norm_length", "angle_rel_dom_deg", "stroke_width", "fill_flag", "dash_flag",
    "nearest_parallel_dist_norm", "local_density", "dist_from_margin_norm",
    "collinear_chain_len_norm",
]
FEATURE_NAMES_FIXED = [
    "length_ft_or_norm", "angle_rel_dom_deg", "stroke_width_pctile", "fill_flag", "dash_flag",
    "nearest_parallel_dist_ft_or_norm", "local_density", "dist_from_margin_ft_or_norm",
    "collinear_chain_len_ft_or_norm", "has_scale",
]


def classify_layer(name):
    if name is None:
        return "other"
    if ANNOT_RE.search(name):
        return "annotation"
    if WALL_RE.search(name):
        return "wall"
    return "other"


def r2_client():
    return boto3.client(
        "s3", endpoint_url=ENV["R2_ENDPOINT"],
        aws_access_key_id=ENV["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=ENV["R2_SECRET_ACCESS_KEY"],
        region_name="auto")


def download_pdf(s3, doc_id):
    # KNOWN RACE (hit once in the first full run: doc 7372349/24-06748-RNVS
    # has 4 roster rows on ONE doc_id, processed by different worker
    # PROCESSES concurrently): a shared path keyed only by doc_id let one
    # process delete the PDF (see cleanup in process_one) while a sibling
    # process for a different PAGE of the same doc was still using it. Fix:
    # key the local path by PID too, so concurrent processes never share a
    # file handle.
    dest = os.path.join(LOCAL_TMP, f"{doc_id}_{os.getpid()}.pdf")
    if os.path.exists(dest):
        return dest
    s3.download_file(ENV["R2_BUCKET"], f"docs/{doc_id}.pdf", dest)
    with open(dest, "rb") as f:
        head = f.read(5)
    assert head[:4] == b"%PDF", f"not a PDF: doc {doc_id}"
    return dest


def seg_len(p0, p1):
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def dominant_angle(line_segments, pw):
    """Length-weighted histogram of segment angles mod 90, min-length
    filtered -- same approach as probe2_sf.dominant_angle / probe25."""
    hist = defaultdict(float)
    for p0, p1, w in line_segments:
        L = seg_len(p0, p1)
        if L < 0.02 * pw:
            continue
        ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0])) % 90.0
        bucket = round(ang)
        hist[bucket] += L
    if not hist:
        return 0.0
    return max(hist.items(), key=lambda kv: kv[1])[0]


def extract_all_segments(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    segs = []
    arcs = []
    for d in page.get_drawings():
        layer = d.get("layer")
        width = d.get("width") or 0.0
        is_fill = d.get("fill") is not None and d.get("type") in ("f", "fs")
        dashes = d.get("dashes")
        dash_flag = 1 if dashes and dashes not in ("[] 0", "") else 0
        curve_pts = []
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
            elif item[0] == "c":
                p0 = (item[1].x, item[1].y)
                p3 = (item[4].x, item[4].y)
                curve_pts.append((p0, p3))
        for p0, p3 in curve_pts:
            L = seg_len(p0, p3)
            if 0.01 * pw < L < 0.06 * pw:
                arcs.append((p0, p3))
    doc.close()
    return segs, arcs, pw, ph


def page_scale(pdf_path, page_index, doc_id):
    if doc_id in SCALE_OVERRIDE:
        return SCALE_OVERRIDE[doc_id]
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


def circ_dist(a, b, mod):
    d = np.abs(a - b) % mod
    return np.minimum(d, mod - d)


def _rotcoord(angle_deg, pts):
    th = math.radians(angle_deg)
    tx, ty = math.cos(th), math.sin(th)
    nx, ny = -ty, tx
    n = pts[:, 0] * nx + pts[:, 1] * ny
    t = pts[:, 0] * tx + pts[:, 1] * ty
    return n, t


def compute_geometry(segs, pw, ph):
    """Shared geometry (dominant axis, per-segment length/angle/parallel-
    dist/density/margin/chain) computed ONCE; raw units are page-relative
    (pt / page-width fraction). Callers convert to feet or keep as fallback
    per the fix-toggle. Returns a dict of raw-unit arrays."""
    N = len(segs)
    P0 = np.array([s[0] for s in segs], dtype=float)
    P1 = np.array([s[1] for s in segs], dtype=float)
    widths = np.array([s[3] for s in segs], dtype=float)
    fill = np.array([s[4] for s in segs], dtype=float)
    dash = np.array([s[5] for s in segs], dtype=float)

    dx = P1[:, 0] - P0[:, 0]
    dy = P1[:, 1] - P0[:, 1]
    L = np.hypot(dx, dy)
    mid = (P0 + P1) / 2.0
    ang90 = np.degrees(np.arctan2(dy, dx)) % 90.0
    ang180 = np.degrees(np.arctan2(dy, dx)) % 180.0

    dom = dominant_angle([(tuple(p0), tuple(p1), w) for p0, p1, w in
                           zip(P0.tolist(), P1.tolist(), widths.tolist())], pw)
    domA = dom % 90.0
    d1 = np.abs(ang90 - domA)
    d2 = np.abs(ang90 - domA - 90)
    d3 = np.abs(ang90 - domA + 90)
    angle_rel_dom = np.minimum(np.minimum(d1, d2), d3)

    dist_margin_pt = np.minimum.reduce(
        [mid[:, 0], pw - mid[:, 0], mid[:, 1], ph - mid[:, 1]])

    tree = cKDTree(mid)
    r = 0.02 * pw
    density = tree.query_ball_point(mid, r, return_length=True).astype(float) - 1.0
    density = np.clip(density, 0, None)

    frameA_deg = domA
    frameB_deg = (domA + 90) % 180
    dA = circ_dist(ang180, frameA_deg % 180, 180.0)
    dB = circ_dist(ang180, frameB_deg, 180.0)
    frame = (dB < dA).astype(int)

    dist_parallel_pt = np.full(N, pw, dtype=float)
    chain_len_pt = L.copy()

    for f, fdeg in ((0, frameA_deg), (1, frameB_deg)):
        idx = np.where(frame == f)[0]
        if len(idx) < 2:
            continue
        n_f, t_f = _rotcoord(fdeg, mid[idx])
        pts = np.column_stack([n_f, t_f])
        tf_tree = cKDTree(pts)
        dists, _ = tf_tree.query(pts, k=min(2, len(idx)))
        if dists.ndim == 1:
            dists = dists[:, None]
        nn = dists[:, 1] if dists.shape[1] > 1 else np.full(len(idx), pw)
        dist_parallel_pt[idx] = nn

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
                chain_len_pt[members] = total

    return dict(L=L, angle_rel_dom=angle_rel_dom, widths=widths, fill=fill, dash=dash,
                dist_margin_pt=dist_margin_pt, density=density,
                dist_parallel_pt=dist_parallel_pt, chain_len_pt=chain_len_pt)


def pctile_rank(x):
    order = np.argsort(x)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(len(x))
    return ranks / max(1, len(x) - 1)


def compute_features(segs, pw, ph, fpp):
    """Returns (X_raw[N,9], X_fixed[N,10], y[N])."""
    g = compute_geometry(segs, pw, ph)
    layers = [s[2] for s in segs]
    y = np.array([1 if classify_layer(l) == "wall" else 0 for l in layers], dtype=int)

    # ---- RAW (probe25 exact reproduction, ablation baseline) ----
    norm_length = g["L"] / pw
    dist_parallel_norm = g["dist_parallel_pt"] / pw
    dist_margin_norm = g["dist_margin_pt"] / pw
    chain_len_norm = g["chain_len_pt"] / pw
    X_raw = np.column_stack([
        norm_length, g["angle_rel_dom"], g["widths"], g["fill"], g["dash"],
        dist_parallel_norm, g["density"], dist_margin_norm, chain_len_norm,
    ])

    # ---- FIXED (probe30: bucketed stroke width + feet-based distances) ----
    has_scale = 1.0 if fpp else 0.0
    if fpp:
        length_u = g["L"] * fpp
        dist_parallel_u = g["dist_parallel_pt"] * fpp
        dist_margin_u = g["dist_margin_pt"] * fpp
        chain_len_u = g["chain_len_pt"] * fpp
    else:
        length_u = norm_length
        dist_parallel_u = dist_parallel_norm
        dist_margin_u = dist_margin_norm
        chain_len_u = chain_len_norm
    stroke_pctile = pctile_rank(g["widths"])
    has_scale_col = np.full(len(y), has_scale)
    X_fixed = np.column_stack([
        length_u, g["angle_rel_dom"], stroke_pctile, g["fill"], g["dash"],
        dist_parallel_u, g["density"], dist_margin_u, chain_len_u, has_scale_col,
    ])
    return X_raw, X_fixed, y


def process_one(row, s3, out_prefix):
    permit, doc_id, page = row["permit"], int(row["doc_id"]), int(row["page"])
    tag = f"{permit}_{doc_id}_p{page}"
    key = f"{out_prefix}/{tag}.npz"
    try:
        s3.head_object(Bucket=ENV["R2_BUCKET"], Key=key)
        return dict(tag=tag, status="skip_exists")
    except Exception:
        pass

    t0 = time.time()
    pdf = download_pdf(s3, doc_id)
    segs, arcs, pw, ph = extract_all_segments(pdf, page)
    n_total = len(segs)
    sampled = False
    if n_total > MAX_SEGS:
        wall_idx = [i for i, s in enumerate(segs) if classify_layer(s[2]) == "wall"]
        nonwall_idx = [i for i, s in enumerate(segs) if classify_layer(s[2]) != "wall"]
        n_keep_nonwall = max(0, MAX_SEGS - len(wall_idx))
        rng = np.random.RandomState(0)
        if len(nonwall_idx) > n_keep_nonwall:
            keep_nonwall = set(rng.choice(nonwall_idx, size=n_keep_nonwall, replace=False).tolist())
        else:
            keep_nonwall = set(nonwall_idx)
        keep_idx = sorted(set(wall_idx) | keep_nonwall)
        segs = [segs[i] for i in keep_idx]
        sampled = True

    fpp, scale_text = page_scale(pdf, page, doc_id)
    p0 = np.array([s[0] for s in segs])
    p1 = np.array([s[1] for s in segs])
    X_raw, X_fixed, y = compute_features(segs, pw, ph, fpp)

    local_npz = os.path.join(LOCAL_TMP, f"{tag}.npz")
    np.savez_compressed(local_npz, X_raw=X_raw, X_fixed=X_fixed, y=y, p0=p0, p1=p1,
                         pw=pw, ph=ph, fpp=(fpp if fpp else 0.0),
                         scale_text=(scale_text or ""), has_scale=(1 if fpp else 0),
                         sampled=int(sampled), n_segs_total=n_total,
                         arcs=np.array(arcs) if arcs else np.zeros((0, 2, 2)),
                         permit=permit, doc_id=doc_id, page=page)
    s3.upload_file(local_npz, ENV["R2_BUCKET"], key)
    os.remove(local_npz)
    if os.path.exists(pdf):
        os.remove(pdf)
    dt = time.time() - t0
    return dict(tag=tag, status="ok", n_segs=n_total, n_wall=int(y.sum()),
                sampled=sampled, scale_text=scale_text, dt=round(dt, 1))


def _worker_entry(row, out_prefix):
    s3 = r2_client()
    try:
        return process_one(row, s3, out_prefix)
    except Exception as e:
        return dict(tag=f"{row['permit']}_{row['doc_id']}_p{row['page']}", status="error",
                    error=str(e), tb=traceback.format_exc())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out-prefix", default="claude-repo/probe30_features")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.roster)))
    print(f"{len(rows)} rows to process, {a.workers} workers, out={a.out_prefix}")

    results = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(_worker_entry, row, a.out_prefix): row for row in rows}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            print(json.dumps(r, default=str), flush=True)

    n_ok = sum(1 for r in results if r["status"] == "ok")
    n_skip = sum(1 for r in results if r["status"] == "skip_exists")
    n_err = sum(1 for r in results if r["status"] == "error")
    print(f"\nDONE: ok={n_ok} skip_exists={n_skip} error={n_err} / {len(results)}")
    if n_err:
        for r in results:
            if r["status"] == "error":
                print("ERROR", r["tag"], r.get("error"))


if __name__ == "__main__":
    main()
