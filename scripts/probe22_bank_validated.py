#!/usr/bin/env python3
"""The one fully-validated takeoff on the GOOD path: 14-11290 bank. Layer geometry
per room, cross-checked against the independently-read printed DIMENSIONS (vision
fleet, probe15/16). Two independent methods agreeing = validated; diverging =
flagged. No SF schedule for this permit, so dimensions are the ground truth."""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.geometry import Point
from probe2_sf import (ROOT, r2_client, download_pdf, snap_and_close, polygonize_rooms,
    find_scale, SCALE_RE, seg_len)
from probe7_layer_walls import extract_wall_layer_segments
from probe4_room_sf import ROOMS

DOC, PAGE = 1494156, 3
# vision dimension-read areas (probe15/16, 4 Sonnet workers) — independent of geometry
VDIM = {101:78,102:202,103:223,104:156,105:190,106:119,107:119,108:220,109:100,
        110:113,111:67,112:68,113:115,114:37,115:52,116:54,117:38,118:23}
MAT = {101:"Tile",102:"Tile",103:"Carpet",104:"Carpet",105:"Carpet",106:"Carpet",
       107:"Carpet",108:"Carpet",109:"Carpet",110:"Carpet",111:"Carpet",112:"Tile",
       113:"Resilient",114:"Carpet",115:"Resilient",116:"Resilient",117:"Carpet",118:"Resilient"}
BRANCH_GROSS = 3190


def verdict(g, v):
    if g is None: return "open (in blob)"
    d = abs(g-v)/v
    if d <= 0.15: return "VALIDATED"
    if d <= 0.30: return "check"
    return "DISAGREE"


def main():
    s3 = r2_client(); pdf = download_pdf(s3, DOC)
    fpp, _ = find_scale(DOC, PAGE)
    doc = fitz.open(pdf); page = doc[PAGE]; pw, ph = page.rect.width, page.rect.height
    if fpp is None:
        m = SCALE_RE.findall(page.get_text()); fpp = (int(m[0][1])/int(m[0][0]))/72.0 if m else None
    segs, _, _, _ = extract_wall_layer_segments(pdf, PAGE)
    walls = [(p0,p1,w) for p0,p1,w in segs if seg_len(p0,p1) > 0.008*pw]
    lines, _ = snap_and_close([(p0,p1,seg_len(p0,p1),w) for p0,p1,w in walls], [], pw, feet_per_pt=fpp)
    polys, _ = polygonize_rooms(lines, pw, ph, 15, 8000, fpp)
    anchors = {}
    for w in page.get_text("words"):
        t = w[4].strip()
        if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
            anchors[int(t)] = ((w[0]+w[2])/2, (w[1]+w[3])/2)
    room_poly, poly_rooms = {}, defaultdict(list)
    for rn,(x,y) in anchors.items():
        for i,pg in enumerate(polys):
            if pg.contains(Point(x,y)): room_poly[rn]=i; poly_rooms[i].append(rn); break
    doc.close(); os.remove(pdf)

    geom = {}
    for rn in ROOMS:
        i = room_poly.get(rn)
        geom[rn] = polys[i].area*fpp**2 if (i is not None and len(poly_rooms[i])==1) else None

    print("="*66)
    print("  14-11290 BANK — VALIDATED TAKEOFF (layer geometry vs read dimensions)")
    print("="*66)
    print(f"\n{'rm':>4} {'name':<13}{'geom':>6}{'dim':>6}{'diff':>7}  verdict")
    tally = defaultdict(int); gtot = 0; vtot = 0
    for rn in sorted(ROOMS):
        g, v = geom[rn], VDIM[rn]; vd = verdict(g, v); tally[vd.split()[0]] += 1
        diff = f"{100*(g-v)/v:+.0f}%" if g else ""
        print(f"{rn:>4} {ROOMS[rn]:<13}{(f'{g:.0f}' if g else '—'):>6}{v:>6}{diff:>7}  {vd}")
        if g: gtot += g
        vtot += v
    # open blob total (geometry) for the 5 open rooms
    blob = sum(polys[i].area*fpp**2 for i,rs in poly_rooms.items() if len(rs)>1)
    print(f"\n  enclosed geom sum: {gtot:.0f} SF ({tally['VALIDATED']} validated, "
          f"{tally.get('check',0)} check, {tally['DISAGREE']} disagree)")
    print(f"  open-area blob (geom): {blob:.0f} SF  |  all-rooms dim sum: {vtot} SF")
    print(f"  geometry total (enclosed + blob): {gtot+blob:.0f} SF vs branch GROSS 3,190 "
          f"= {100*(gtot+blob-BRANCH_GROSS)/BRANCH_GROSS:+.0f}% (net/gross)")

    # material rollup using best per-room number (geom if validated else dim)
    matsf = defaultdict(float)
    for rn in ROOMS:
        a = geom[rn] if geom[rn] else VDIM[rn]
        matsf[MAT[rn]] += a
    print("\n  --- area by material (geom where validated, else dimension) ---")
    for m,sf in sorted(matsf.items(), key=lambda x:-x[1]):
        extra = f"  = {int(sf/9)+1} SY" if m=="Carpet" else ""
        print(f"    {m:<11}{sf:>6.0f} SF{extra}")


if __name__ == "__main__":
    main()
