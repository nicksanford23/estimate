#!/usr/bin/env python3
"""FAIR validation: LAYER geometry vs a per-room SF answer key, on the one truly
page-aligned golden permit (24-22310-RNVN): wall layers ON floor plan p2 + room
numbers + schedule pages. Parse schedule areas, run layer geometry, match by room#,
compare per room."""
import os, sys, re
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.geometry import Point
from probe2_sf import (ROOT, r2_client, download_pdf, snap_and_close, polygonize_rooms,
    find_scale, SCALE_RE, seg_len)
from probe7_layer_walls import extract_wall_layer_segments

DOC = 7671011
FLOOR = 2
SCHED_PAGES = [5, 1]           # finish_schedule, life_safety
ROOMTOK = re.compile(r'^\d{2,4}$')


def parse_sched(page):
    words = page.get_text("words")
    rooms = [((w[1]+w[3])/2, w[0], w[4]) for w in words if ROOMTOK.match(w[4])]
    sf = []
    for w in words:
        if w[4].upper() in ("SF", "S.F."):
            yc, x = (w[1]+w[3])/2, w[0]
            cand = [(x-vw[2], int(vw[4])) for vw in words
                    if vw[4].isdigit() and abs((vw[1]+vw[3])/2 - yc) < 3 and vw[2] <= x and x-vw[2] < 70]
            if cand: sf.append((yc, min(cand)[1]))
    gt = {}
    for yc, x, code in rooms:
        best = [(abs(yc-sy), a) for sy, a in sf if abs(yc-sy) < 4]
        if best and 5 <= min(best)[1] <= 5000 and code not in gt:
            gt[code] = min(best)[1]
    return gt


def main():
    s3 = r2_client(); pdf = download_pdf(s3, DOC); doc = fitz.open(pdf)
    for sp in SCHED_PAGES:
        gt = parse_sched(doc[sp])
        print(f"schedule p{sp}: parsed {len(gt)} room->SF  {dict(list(gt.items())[:10])}")
    # use whichever schedule parsed the most rooms
    gts = {sp: parse_sched(doc[sp]) for sp in SCHED_PAGES}
    sp = max(gts, key=lambda k: len(gts[k])); gt = gts[sp]
    print(f"\nusing schedule p{sp} as ground truth ({len(gt)} rooms, total {sum(gt.values())} SF)\n")

    # layer geometry on floor plan
    fpp, _ = find_scale(DOC, FLOOR)
    page = doc[FLOOR]; pw, ph = page.rect.width, page.rect.height
    if fpp is None:
        m = SCALE_RE.findall(page.get_text()); fpp = (int(m[0][1])/int(m[0][0]))/72.0 if m else None
    segs, _, _, used = extract_wall_layer_segments(pdf, FLOOR)
    walls = [(p0,p1,w) for p0,p1,w in segs if seg_len(p0,p1) > 0.008*pw]
    lines, _ = snap_and_close([(p0,p1,seg_len(p0,p1),w) for p0,p1,w in walls], [], pw, feet_per_pt=fpp)
    polys, _ = polygonize_rooms(lines, pw, ph, 15, 8000, fpp)
    print(f"floor p{FLOOR}: fpp={fpp} wall-layers={used} wall-segs={len(walls)} polygons={len(polys)}")

    # anchors: room# tokens on the floor plan
    anchors = {}
    for w in page.get_text("words"):
        if ROOMTOK.match(w[4]) and w[4] in gt and w[4] not in anchors:
            anchors[w[4]] = ((w[0]+w[2])/2, (w[1]+w[3])/2)
    print(f"anchors matched to schedule rooms: {len(anchors)}/{len(gt)}\n")

    print(f"{'room':>6} {'geom SF':>9} {'truth SF':>9} {'err':>7}")
    rows = []
    for rn,(x,y) in sorted(anchors.items()):
        pi = next((i for i,pg in enumerate(polys) if pg.contains(Point(x,y))), None)
        g = polys[pi].area*fpp**2 if pi is not None else None
        t = gt[rn]
        err = f"{100*(g-t)/t:+.0f}%" if g else "no-poly"
        rows.append((rn,g,t))
        print(f"{rn:>6} {(f'{g:.0f}' if g else '-'):>9} {t:>9} {err:>7}")
    matched = [(g,t) for rn,g,t in rows if g]
    if matched:
        gs=sum(g for g,t in matched); ts=sum(t for g,t in matched)
        print(f"\nmatched-room total: geom {gs:.0f} vs truth {ts} SF ({100*(gs-ts)/ts:+.0f}%), n={len(matched)}")
    doc.close(); os.remove(pdf)


if __name__ == "__main__":
    main()
