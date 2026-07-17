#!/usr/bin/env python3
"""Snap vision-proposed room polygons to actual PDF vector wall lines.

The hybrid step: Claude vision understands WHICH room and roughly where its
boundary is; the PDF's vector drawing knows EXACTLY where the lines are.
For each polygon edge, find nearby parallel vector segments and move the
edge onto the best one; rebuild vertices by intersecting consecutive edges.

Outputs per room: snapped polygon (px + pdf), before/after overlay PNG
(magenta = vision original, green = snapped), area before/after. Snapped
polygons are still machine proposals — human lock required as always.

Usage: snap_polygon_walls.py --permit 24-06748-RNVS --codes 100,101,...
"""
import argparse
import glob
import json
import math
import os

import fitz
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = {"24-06748-RNVS": os.path.join(ROOT, "data", "render_cache", "pdf", "7372349.pdf")}

MAX_PERP_FT = 1.0        # how far an edge may move to reach a wall line
MIN_SEG_FT = 1.2         # ignore vector segments shorter than this (hatch/fixtures)
MIN_OVERLAP = 0.25       # candidate must overlap >=25% of the edge span
ANGLE_TOL_DEG = 6.0
PT_PER_FT = 18.0         # 1/4" = 1'-0"


def load_tasks(permit):
    p = json.load(open(os.path.join(ROOT, "data", "sam_smoke", permit, "bundle_g1b", "tasks.json")))
    tl = p["tasks"] if isinstance(p, dict) else p
    return {t["code"]: t for t in tl}


def load_vision(permit):
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "sam_smoke", permit, "claude_vision", "level_0*.json"))):
        for e in json.load(open(f)):
            out[e["code"]] = e
    return out


def page_segments(doc, page_index):
    """All straight vector segments on the page (PDF pts), incl. rect edges."""
    segs = []
    for path in doc[page_index].get_drawings():
        for item in path["items"]:
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                segs.append(((p1.x, p1.y), (p2.x, p2.y)))
            elif item[0] == "re":
                r = item[1]
                cs = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                for i in range(4):
                    segs.append((cs[i], cs[(i + 1) % 4]))
    min_len = MIN_SEG_FT * PT_PER_FT
    return [s for s in segs
            if math.dist(s[0], s[1]) >= min_len]


def edge_line(p1, p2):
    """Return (unit direction, unit normal, offset c) with line: n.x = c."""
    d = np.array(p2) - np.array(p1)
    L = np.linalg.norm(d)
    u = d / L
    n = np.array([-u[1], u[0]])
    return u, n, float(n @ p1), L


def snap_polygon(poly_pdf, segs):
    """poly_pdf: list of [x,y]. Returns (snapped list, per-edge report)."""
    n_pts = len(poly_pdf)
    lines = []   # per edge: (u, n, c) possibly snapped
    report = []
    max_perp = MAX_PERP_FT * PT_PER_FT
    for i in range(n_pts):
        p1, p2 = poly_pdf[i], poly_pdf[(i + 1) % n_pts]
        u, nvec, c, L = edge_line(p1, p2)
        lo = min(np.array(p1) @ u, np.array(p2) @ u)
        hi = max(np.array(p1) @ u, np.array(p2) @ u)
        best = None
        for s1, s2 in segs:
            su, snv, sc, sL = edge_line(s1, s2)
            cosang = abs(float(u @ su))
            if cosang < math.cos(math.radians(ANGLE_TOL_DEG)):
                continue
            # perpendicular distance from edge line to segment (use midpoint)
            mid = (np.array(s1) + np.array(s2)) / 2
            dist = abs(float(nvec @ mid) - c)
            if dist > max_perp:
                continue
            # overlap along edge direction
            a, b = sorted((float(np.array(s1) @ u), float(np.array(s2) @ u)))
            ov = min(hi, b) - max(lo, a)
            if ov < MIN_OVERLAP * (hi - lo):
                continue
            score = dist - 0.02 * min(sL, 3 * PT_PER_FT)  # prefer close, then long
            if best is None or score < best[0]:
                best = (score, dist, float(nvec @ mid))
        if best is None:
            lines.append((u, nvec, c))
            report.append({"edge": i, "snapped": False, "moved_in": 0.0})
        else:
            lines.append((u, nvec, best[2]))
            report.append({"edge": i, "snapped": True,
                           "moved_in": round(abs(best[2] - c) / PT_PER_FT * 12, 1)})
    # rebuild vertices: intersection of consecutive edge lines
    snapped = []
    for i in range(n_pts):
        (u1, n1, c1) = lines[(i - 1) % n_pts]
        (u2, n2, c2) = lines[i]
        A = np.array([n1, n2])
        if abs(np.linalg.det(A)) < 1e-6:
            snapped.append(list(poly_pdf[i]))       # near-parallel: keep original
            continue
        v = np.linalg.solve(A, np.array([c1, c2]))
        # guard against wild intersections (>4ft from original vertex)
        if math.dist(v, poly_pdf[i]) > 4 * PT_PER_FT:
            snapped.append(list(poly_pdf[i]))
        else:
            snapped.append([float(v[0]), float(v[1])])
    return snapped, report


def shoelace(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--permit", default="24-06748-RNVS")
    ap.add_argument("--codes", required=True)
    a = ap.parse_args()
    tasks = load_tasks(a.permit)
    vision = load_vision(a.permit)
    doc = fitz.open(PDF[a.permit])
    seg_cache = {}
    outdir = os.path.join(ROOT, "data", "sam_smoke", a.permit, "snapped")
    os.makedirs(outdir, exist_ok=True)
    results = {}
    for code in a.codes.split(","):
        t, v = tasks[code], vision[code]
        tr = t["transform"]
        zoom, (ox, oy) = tr["zoom"], tr["crop_origin_pdf"]
        pidx = t["page_index"]
        if pidx not in seg_cache:
            seg_cache[pidx] = page_segments(doc, pidx)
        poly_pdf = [[p[0] / zoom + ox, p[1] / zoom + oy] for p in v["polygon_px"]]
        snapped_pdf, rep = snap_polygon(poly_pdf, seg_cache[pidx])
        ppf = tr["px_per_foot"]
        area_before = shoelace(v["polygon_px"]) / ppf ** 2
        snapped_px = [[(p[0] - ox) * zoom, (p[1] - oy) * zoom] for p in snapped_pdf]
        area_after = shoelace(snapped_px) / ppf ** 2
        n_snapped = sum(1 for r in rep if r["snapped"])
        results[code] = dict(task_id=t["task_id"], polygon_pdf_snapped=[[round(x, 3) for x in p] for p in snapped_pdf],
                             polygon_px_snapped=[[round(x, 2) for x in p] for p in snapped_px],
                             area_sf_before=round(area_before, 1), area_sf_after=round(area_after, 1),
                             edges_snapped=f"{n_snapped}/{len(rep)}", edge_report=rep,
                             proposal_source="claude_vision_v1+wall_snap_v1", machine_proposal=True)
        # before/after overlay
        img = Image.open(os.path.join(ROOT, "data", "sam_smoke", a.permit, "bundle_g1b", t["image"])).convert("RGB")
        d = ImageDraw.Draw(img)
        d.polygon([tuple(p) for p in v["polygon_px"]], outline=(255, 0, 180), width=3)
        d.polygon([tuple(p) for p in snapped_px], outline=(0, 170, 0), width=4)
        img.save(os.path.join(outdir, f"snap_{code}.png"))
        print(f"{code}: edges snapped {n_snapped}/{len(rep)}, "
              f"SF {area_before:.1f} -> {area_after:.1f}")
    json.dump(results, open(os.path.join(outdir, "snapped_proposals.json"), "w"), indent=1)
    print("wrote", outdir)


if __name__ == "__main__":
    main()
