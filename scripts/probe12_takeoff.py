#!/usr/bin/env python3
"""End-to-end flooring TAKEOFF for 14-11290 — the capstone. Geometry (Probe 7
layers) gives area + perimeter; the finish schedule gives material per room. We
output the three real line-item types an estimator needs:
  AREA (SF, carpet also SY)  ·  BASE (LF = perimeter - door openings)  ·  TRANSITIONS.
And we validate total SF against the RECORDED 7,090 SF."""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.geometry import Point
from probe2_sf import ROOT, r2_client, download_pdf, snap_and_close, polygonize_rooms, find_scale, SCALE_RE, seg_len
from probe7_layer_walls import extract_wall_layer_segments
from probe8_layer_classes import classify_layer
from probe4_room_sf import ROOMS

DOC, PAGE = 1494156, 3
# Sheet A-0.1 "PROPOSED BUILDING AREA": Business 3,190 + Mercantile 3,900 = 7,090 (whole bldg).
# We take off ONLY the Business branch (sheet A-1.1, rooms 101-118) = 3,190 SF GROSS.
BRANCH_GROSS_SF = 3190
WHOLE_BUILDING_SF = 7090

# room -> (material, code) from the finish schedule (guides.ts)
MAT = {
 101:("Ceramic tile","CT-1"),102:("Ceramic tile","CT-1"),103:("Carpet","CP-2"),
 104:("Carpet","CP-1"),105:("Carpet","CP-1"),106:("Carpet","CP-1"),107:("Carpet","CP-1"),
 108:("Carpet","CP-1"),109:("Carpet","CP-1"),110:("Carpet","CP-2"),111:("Carpet","CP-2"),
 112:("Ceramic tile","CT-1"),113:("Resilient","RF-1"),114:("Carpet","CP-2"),
 115:("Resilient","RF-1"),116:("Resilient","RF-1"),117:("Carpet","CP-2"),118:("Resilient","RF-1"),
}
UNIT = {"Carpet":"SY","Ceramic tile":"SF","Resilient":"SF"}
WOOD_BASE = {105, 108}  # WB-1; else rubber cove RB-1


def main():
    s3 = r2_client(); pdf = download_pdf(s3, DOC)
    fpp, _ = find_scale(DOC, PAGE)
    doc = fitz.open(pdf); page = doc[PAGE]; pw, ph = page.rect.width, page.rect.height
    if fpp is None:
        m = SCALE_RE.findall(page.get_text())
        if m: fpp = (int(m[0][1]) / int(m[0][0])) / 72.0

    segs, _pw, _ph, _u = extract_wall_layer_segments(pdf, PAGE)
    walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
    lines, _ = snap_and_close([(p0, p1, seg_len(p0, p1), w) for p0, p1, w in walls], [], pw, feet_per_pt=fpp)
    polys, _ = polygonize_rooms(lines, pw, ph, 15, 8000, fpp)

    # doors: centroids of door-class drawings (for base deductions & transitions)
    doors = []
    for d in page.get_drawings():
        if classify_layer(d.get("layer")) != "door":
            continue
        xs, ys = [], []
        for it in d.get("items", []):
            for k in (1, 2, 3):
                if len(it) > k and hasattr(it[k], "x"):
                    xs.append(it[k].x); ys.append(it[k].y)
        if xs:
            doors.append((sum(xs)/len(xs), sum(ys)/len(ys)))

    anchors = {}
    for w in page.get_text("words"):
        t = w[4].strip()
        if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
            anchors[int(t)] = ((w[0]+w[2])/2, (w[1]+w[3])/2)
    doc.close(); os.remove(pdf)

    room_poly, poly_rooms = {}, defaultdict(list)
    for rn, (x, y) in anchors.items():
        for i, pg in enumerate(polys):
            if pg.contains(Point(x, y)):
                room_poly[rn] = i; poly_rooms[i].append(rn); break

    # doors per polygon (nearest boundary)
    doors_per_poly = defaultdict(int)
    for dx, dy in doors:
        p = Point(dx, dy)
        best, bi = 1e9, None
        for i, pg in enumerate(polys):
            dd = pg.exterior.distance(p)
            if dd < best: best, bi = dd, i
        if bi is not None and best < 6 / fpp:  # within ~6 ft of a room edge
            doors_per_poly[bi] += 1

    # ---- build rows ----
    by_mat_sf = defaultdict(float)     # cleanly-assigned floor area per material
    unsplit = []                       # open blobs (mixed material)
    total_sf = 0.0
    base_lf_total = 0.0
    rows = []
    for i, pg in enumerate(polys):
        rs = poly_rooms.get(i, [])
        area = pg.area * fpp**2
        perim = pg.exterior.length * fpp
        total_sf += area
        ndoor = doors_per_poly.get(i, 0)
        base_lf = max(0.0, perim - 3.0 * ndoor)     # deduct ~3 LF per door opening
        if len(rs) == 1:
            rn = rs[0]; mat, code = MAT[rn]
            by_mat_sf[mat] += area
            base_lf_total += base_lf
            rows.append((rn, ROOMS[rn], mat, code, area, base_lf, ndoor,
                         "WB-1" if rn in WOOD_BASE else "RB-1"))
        elif len(rs) > 1:
            mats = sorted({MAT[r][0] for r in rs})
            unsplit.append((sorted(rs), mats, area, base_lf))
            base_lf_total += base_lf

    # ---- print takeoff ----
    print(f"=== 14-11290 FLOORING TAKEOFF (geometry=Probe7 layers, material=finish schedule) ===")
    print(f"scale={1/fpp*12:.0f} in/ft check  fpp={fpp:.4f}  polygons={len(polys)}  doors_detected={len(doors)}\n")
    print(f"{'rm':>4} {'name':<13}{'material':<13}{'code':<6}{'area SF':>9}{'base LF':>9}{'doors':>6} base")
    for rn, nm, mat, code, area, blf, nd, bt in sorted(rows):
        print(f"{rn:>4} {nm:<13}{mat:<13}{code:<6}{area:>9.0f}{blf:>9.0f}{nd:>6}  {bt}")
    print("\n  OPEN AREAS (need finish-boundary split — mixed material):")
    for rs, mats, area, blf in unsplit:
        print(f"    rooms {rs}  ~{area:.0f} SF  base ~{blf:.0f} LF   materials: {', '.join(mats)}")

    print("\n=== AREA BY MATERIAL (cleanly enclosed rooms) ===")
    for mat, sf in sorted(by_mat_sf.items(), key=lambda x: -x[1]):
        extra = f"  = {sf/9:.0f} SY" if UNIT[mat] == "SY" else ""
        print(f"  {mat:<14}{sf:>8.0f} SF{extra}")
    unsplit_sf = sum(a for _, _, a, _ in unsplit)
    print(f"  (unsplit open areas: {unsplit_sf:.0f} SF — tile+carpet mix)")

    print("\n=== LINEAR / OTHER ===")
    print(f"  Base (cove/wood), gross perimeter less doors:  {base_lf_total:.0f} LF")
    diff_mats = 0
    for rs, mats, area, blf in unsplit:
        diff_mats += 1
    print(f"  Transitions: at every material change (tile↔carpet, resilient↔carpet)")
    print(f"    material zones present: Carpet / Ceramic tile / Resilient  -> strips TS-1/TS-2 at their borders")

    print("\n=== VALIDATION ===")
    print(f"  our total floor area (all polygons, NET): {total_sf:.0f} SF")
    print(f"  branch Business area (sheet A-0.1, GROSS): {BRANCH_GROSS_SF} SF")
    print(f"  delta: {total_sf - BRANCH_GROSS_SF:+.0f} SF  ({100*(total_sf-BRANCH_GROSS_SF)/BRANCH_GROSS_SF:+.0f}%)  "
          f"<- net-vs-gross gap, ~expected")
    print(f"  (NOT vs 7,090 = whole building incl 3,900 SF retail we didn't measure)")
    print(f"  caveat: total ~right can HIDE per-room fragments -> per-room check needed")


if __name__ == "__main__":
    main()
