#!/usr/bin/env python3
"""Deterministic closure diagnostic (the instrument Probe 5 said we needed). Build
an endpoint graph from the STRUCTURAL wall segments, find DANGLING endpoints (a
wall end that meets no other wall), and measure the GAP to the nearest endpoint.
Per room: closure status + the specific gaps around it + likely cause. Renders the
gaps on the plan. This tells us what to FIX (and whether it needs per-room care)."""
import os, sys, math
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point
from probe2_sf import ROOT, r2_client, download_pdf, snap_and_close, polygonize_rooms, find_scale, SCALE_RE, seg_len
from probe7_layer_walls import extract_wall_layer_segments
from probe8_layer_classes import classify_layer
from probe4_room_sf import ROOMS

DOC, PAGE, Z = 1494156, 3, 3.2
OUT = os.path.join(ROOT, "data", "probe17"); os.makedirs(OUT, exist_ok=True)


def font(sz):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def cause(gap_ft):
    if gap_ft < 0.4:  return "hairline (snap)"
    if gap_ft <= 4.0: return "door/opening"
    return "missing wall"


def main():
    s3 = r2_client(); pdf = download_pdf(s3, DOC)
    fpp, _ = find_scale(DOC, PAGE)
    doc = fitz.open(pdf); page = doc[PAGE]; pw, ph = page.rect.width, page.rect.height
    if fpp is None:
        m = SCALE_RE.findall(page.get_text())
        if m: fpp = (int(m[0][1]) / int(m[0][0])) / 72.0

    # structural wall segments only (so door openings appear as GAPS)
    wsegs = []
    for d in page.get_drawings():
        if classify_layer(d.get("layer")) != "wall":
            continue
        for it in d.get("items", []):
            if it[0] == "l":
                p0, p1 = (it[1].x, it[1].y), (it[2].x, it[2].y)
                if seg_len(p0, p1) > 0.008 * pw:
                    wsegs.append((p0, p1))

    # endpoint graph: snap endpoints into clusters
    tol = 0.4 / fpp                      # 0.4 ft cluster tolerance
    def key(p): return (round(p[0] / tol), round(p[1] / tol))
    node_pts = {}; deg = defaultdict(int); adj = defaultdict(set)
    for p0, p1 in wsegs:
        k0, k1 = key(p0), key(p1)
        node_pts.setdefault(k0, p0); node_pts.setdefault(k1, p1)
        deg[k0] += 1; deg[k1] += 1; adj[k0].add(k1); adj[k1].add(k0)
    dangling = [k for k in node_pts if deg[k] == 1]

    # for each dangling node, nearest OTHER node (not already adjacent) within 8 ft = the gap
    gaps = []   # (mid_pt, gap_ft, a, b)
    maxg = 8.0 / fpp
    nodes = list(node_pts.items())
    for k in dangling:
        px, py = node_pts[k]; best = None
        for k2, p2 in nodes:
            if k2 == k or k2 in adj[k]: continue
            dd = math.hypot(px - p2[0], py - p2[1])
            if dd <= maxg and (best is None or dd < best[0]):
                best = (dd, p2, k2)
        if best:
            mid = ((px + best[1][0]) / 2, (py + best[1][1]) / 2)
            gaps.append((mid, best[0] * fpp, (px, py), best[1]))

    # polygonize (Probe 7 walls) + room status
    segsB, _pw, _ph, _u = extract_wall_layer_segments(pdf, PAGE)
    walls = [(p0, p1, w) for p0, p1, w in segsB if seg_len(p0, p1) > 0.008 * pw]
    lines, _ = snap_and_close([(p0, p1, seg_len(p0, p1), w) for p0, p1, w in walls], [], pw, feet_per_pt=fpp)
    polys, _ = polygonize_rooms(lines, pw, ph, 15, 8000, fpp)
    anchors = {}
    for w in page.get_text("words"):
        t = w[4].strip()
        if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
            anchors[int(t)] = ((w[0]+w[2])/2, (w[1]+w[3])/2)
    room_poly, poly_rooms = {}, defaultdict(list)
    for rn, (x, y) in anchors.items():
        for i, pg in enumerate(polys):
            if pg.contains(Point(x, y)):
                room_poly[rn] = i; poly_rooms[i].append(rn); break

    def status(rn):
        i = room_poly.get(rn)
        if i is None: return "no-polygon"
        if len(poly_rooms[i]) > 1: return "merged"
        a = polys[i].area * fpp**2
        return "fragment" if a < 45 else "closed"

    # gaps near each room (within ~10 ft of anchor)
    rad = 10.0 / fpp
    print(f"fpp={fpp:.4f}  wall-segs={len(wsegs)}  dangling endpoints={len(dangling)}  gaps<8ft={len(gaps)}\n")
    print(f"{'rm':>4} {'name':<13}{'status':<11} gaps nearby (ft: cause)")
    tally = defaultdict(int)
    for rn in sorted(ROOMS):
        if rn not in anchors: continue
        ax, ay = anchors[rn]
        near = sorted([(g[1], cause(g[1])) for g in gaps
                       if math.hypot(g[0][0]-ax, g[0][1]-ay) <= rad])
        st = status(rn); tally[st] += 1
        gtxt = ", ".join(f"{d:.1f}:{c}" for d, c in near[:6]) if near else "(none within 10ft)"
        print(f"{rn:>4} {ROOMS[rn]:<13}{st:<11} {gtxt}")

    print(f"\nstatus tally: {dict(tally)}")
    gc = defaultdict(int)
    for _, gft, _, _ in gaps: gc[cause(gft)] += 1
    print(f"gap causes (all {len(gaps)}): {dict(gc)}")

    # overlay
    pm = page.get_pixmap(matrix=fitz.Matrix(Z, Z), alpha=False)
    im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
    dd = ImageDraw.Draw(im, "RGBA"); fnt = font(int(6*Z))
    for p0, p1 in wsegs:
        dd.line([p0[0]*Z, p0[1]*Z, p1[0]*Z, p1[1]*Z], fill=(120,120,120,120), width=1)
    for mid, gft, a, b in gaps:
        col = (200,180,0,255) if gft < 0.4 else ((220,40,40,255) if gft <= 4 else (150,0,160,255))
        dd.line([a[0]*Z, a[1]*Z, b[0]*Z, b[1]*Z], fill=col, width=3)
        dd.ellipse([a[0]*Z-4, a[1]*Z-4, a[0]*Z+4, a[1]*Z+4], fill=col)
    for rn,(x,y) in anchors.items():
        dd.text((x*Z, y*Z), f"{rn} {status(rn)[:4]}", fill=(10,20,120,255), font=fnt)
    im.convert("RGB").save(os.path.join(OUT, "gaps.jpg"), "JPEG", quality=86)
    doc.close(); os.remove(pdf)
    print(f"\noverlay -> data/probe17/gaps.jpg  (yellow=hairline, red=door/opening, purple=missing wall)")


if __name__ == "__main__":
    main()
