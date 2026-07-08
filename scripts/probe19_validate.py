#!/usr/bin/env python3
"""First REAL accuracy measurement: geometry vs a per-room finish-schedule answer
key. 26-05332 (Curran Rd Townhouses). Parse the schedule (p19) for per-room area,
run rules geometry on the floor plans (p8/p9 — flattened PDF, no wall layers), and
compare. Honest: this is the hard case (flattened + repeated units)."""
import os, sys, re
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from probe2_sf import (ROOT, r2_client, download_pdf, extract_drawings, wall_candidates,
    suppress_hatches, snap_and_close, polygonize_rooms, find_scale, SCALE_RE)

DOC = 8929774
SCHED_PAGE = 19
FLOOR_PAGES = [8, 9]
ROOM_RE = re.compile(r'^[A-D]-\d{3}$')


def parse_gt(page):
    words = page.get_text("words")
    rooms = [(( w[1]+w[3])/2, w[0], w[4]) for w in words if ROOM_RE.match(w[4])]
    # every 'SF' token with the number immediately to its left
    sf = []
    for w in words:
        if w[4] == "SF":
            yc, x = (w[1]+w[3])/2, w[0]
            cand = [(x-vw[2], int(vw[4])) for vw in words
                    if vw[4].isdigit() and abs((vw[1]+vw[3])/2 - yc) < 3 and vw[2] <= x and x-vw[2] < 60]
            if cand:
                sf.append((yc, min(cand)[1]))
    gt = {}
    for yc, x, code in rooms:
        best = [(abs(yc-sy), a) for sy, a in sf if abs(yc-sy) < 4]
        if best and code not in gt:
            gt[code] = min(best)[1]
    return gt


def geom_areas(pdf, pi):
    fpp, _ = find_scale(DOC, pi)
    doc = fitz.open(pdf); page = doc[pi]; pw, ph = page.rect.width, page.rect.height
    if fpp is None:
        m = SCALE_RE.findall(page.get_text())
        fpp = (int(m[0][1])/int(m[0][0]))/72.0 if m else None
    doc.close()
    if not fpp: return None, []
    ex = extract_drawings(pdf, pi)
    walls, dom, thick = wall_candidates(ex)
    walls_clean, _ = suppress_hatches(walls, ex["pw"])
    lines, _ = snap_and_close(walls_clean, ex["arcs"], ex["pw"], feet_per_pt=fpp)
    polys, _ = polygonize_rooms(lines, ex["pw"], ex["ph"], 15, 8000, fpp)
    return fpp, [p.area*fpp**2 for p in polys]


def main():
    s3 = r2_client(); pdf = download_pdf(s3, DOC)
    doc = fitz.open(pdf)
    gt = parse_gt(doc[SCHED_PAGE]); doc.close()
    gt_total = sum(gt.values())
    print(f"GROUND TRUTH (finish schedule): {len(gt)} rooms, total {gt_total} SF (sheet says 5278)")
    print(f"  sample: {dict(list(gt.items())[:8])}\n")

    all_polys = []
    for pi in FLOOR_PAGES:
        fpp, areas = geom_areas(pdf, pi)
        realistic = [a for a in areas if 8 <= a <= 1500]
        print(f"floor page p{pi}: fpp={fpp}  polygons={len(areas)}  "
              f"realistic-room-size(8-1500sf)={len(realistic)}  sum={sum(realistic):.0f} SF")
        all_polys += realistic
    os.remove(pdf)

    geo_total = sum(all_polys)
    print(f"\n=== TOTALS ===")
    print(f"  ground truth:   {gt_total} SF  ({len(gt)} rooms)")
    print(f"  geometry:       {geo_total:.0f} SF  ({len(all_polys)} room-size polygons)")
    if gt_total:
        print(f"  delta: {geo_total-gt_total:+.0f} SF ({100*(geo_total-gt_total)/gt_total:+.0f}%)")
    print(f"\n(honest read: flattened PDF + repeated-unit townhouse = the hard case.)")


if __name__ == "__main__":
    main()
