#!/usr/bin/env python3
"""Why do the 5 rooms MERGE under the layer approach? For each merged room-pair,
look at what's actually drawn between the two room labels and name the cause:
  (A) partition on a NON-wall layer we didn't grab  -> fix: broaden layer capture
  (B) partition IS on a wall layer but didn't close -> fix: better snap/close
  (C) nothing drawn between them                    -> the merge may be correct
Renders a zoom crop per merged blob so we can see it. 14-11290 p3."""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point, LineString
from shapely.strtree import STRtree
from probe2_sf import ROOT, r2_client, download_pdf, snap_and_close, polygonize_rooms, find_scale, SCALE_RE, seg_len
from probe7_layer_walls import extract_wall_layer_segments, WALL_RE  # reproduce Probe 7 exactly
from probe4_room_sf import ROOMS

DOC, PAGE, Z = 1494156, 3, 4.0
OUT = os.path.join(ROOT, "data", "probe11"); os.makedirs(OUT, exist_ok=True)


def font(sz):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def main():
    s3 = r2_client(); pdf = download_pdf(s3, DOC)
    fpp, _ = find_scale(DOC, PAGE)
    doc = fitz.open(pdf); page = doc[PAGE]; pw, ph = page.rect.width, page.rect.height
    if fpp is None:
        m = SCALE_RE.findall(page.get_text())
        if m: fpp = (int(m[0][1]) / int(m[0][0])) / 72.0

    # extract ALL line segments (with layer name) for the "what's drawn between" test
    all_segs, all_layers = [], []
    for d in page.get_drawings():
        lay = d.get("layer")
        for it in d.get("items", []):
            if it[0] != "l": continue
            p0, p1 = (it[1].x, it[1].y), (it[2].x, it[2].y)
            if seg_len(p0, p1) < 0.002 * pw: continue
            all_segs.append((p0, p1)); all_layers.append(lay or "(none)")

    # WALLS: reproduce Probe 7 EXACTLY (broad WALL_RE incl doors/frames + re fills)
    segs, _pw, _ph, used = extract_wall_layer_segments(pdf, PAGE)
    wall_walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
    lines, _ = snap_and_close([(p0, p1, seg_len(p0, p1), w) for p0, p1, w in wall_walls], [], pw, feet_per_pt=fpp)
    polys, _ = polygonize_rooms(lines, pw, ph, 15, 8000, fpp)

    def grabbed(lay):  # is this layer one Probe 7 already captures?
        return bool(WALL_RE.search(lay or ""))

    # room anchors
    anchors = {}
    for w in page.get_text("words"):
        t = w[4].strip()
        if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
            anchors[int(t)] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)

    room_poly, poly_rooms = {}, defaultdict(list)
    for rn, (x, y) in anchors.items():
        for i, pg in enumerate(polys):
            if pg.contains(Point(x, y)):
                room_poly[rn] = i; poly_rooms[i].append(rn); break

    n_in = len(room_poly); merged = {i: rs for i, rs in poly_rooms.items() if len(rs) > 1}
    n_closed = sum(1 for i, rs in poly_rooms.items() if len(rs) == 1)
    print(f"scale fpp={fpp:.4f}  polys={len(polys)}  anchors={len(anchors)}/18  in-a-poly={n_in}")
    print(f"single-room polys={n_closed}  merged blobs={len(merged)}  ->  "
          + "; ".join(f"poly{i}:{sorted(rs)}" for i, rs in merged.items()) + "\n")

    # spatial index over ALL segments for the "what's drawn between them" test
    geoms = [LineString([p0, p1]) for p0, p1 in all_segs]
    tree = STRtree(geoms)

    def between_cause(a, b):
        conn = LineString([a, b])
        idxs = tree.query(conn)
        cross_layers = defaultdict(int); wall_cross = 0; any_cross = 0
        for j in idxs:
            g = geoms[j]
            if g.crosses(conn):
                any_cross += 1
                lay = all_layers[j]
                cross_layers[lay] += 1
                if grabbed(lay): wall_cross += 1
        return wall_cross, any_cross, cross_layers

    print("=== per merged pair ===")
    diagnoses = []
    for i, rs in merged.items():
        rs = sorted(rs)
        for k in range(len(rs) - 1):
            for m2 in range(k + 1, len(rs)):
                ra, rb = rs[k], rs[m2]
                a, b = anchors[ra], anchors[rb]
                wc, ac, layers = between_cause(a, b)
                if wc > 0:
                    cause = "B: wall-layer partition PRESENT but didn't close (gap/dangling) -> fix snap/close"
                elif ac > 0:
                    top = sorted(layers.items(), key=lambda x: -x[1])[:3]
                    cause = f"A: partition on NON-wall layer(s) -> broaden capture: {top}"
                else:
                    cause = "C: nothing drawn between -> merge may be correct (one open space)"
                diagnoses.append((i, ra, rb, cause))
                print(f"  poly{i}  {ra} {ROOMS[ra]:<12} <-> {rb} {ROOMS[rb]:<12}  cross(wall={wc} any={ac})")
                print(f"        {cause}")

    # render a crop per merged blob
    pm = page.get_pixmap(matrix=fitz.Matrix(Z, Z), alpha=False)
    full = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
    fnt = font(int(7 * Z))
    for i, rs in merged.items():
        poly = polys[i]; minx, miny, maxx, maxy = poly.bounds
        pad = 30
        box = (max(0, int((minx - pad) * Z)), max(0, int((miny - pad) * Z)),
               min(pm.width, int((maxx + pad) * Z)), min(pm.height, int((maxy + pad) * Z)))
        crop = full.crop(box).copy(); dd = ImageDraw.Draw(crop, "RGBA")
        ox, oy = box[0], box[1]
        # shade the merged polygon
        pts = [(x * Z - ox, y * Z - oy) for x, y in poly.exterior.coords]
        dd.polygon(pts, fill=(220, 60, 50, 55), outline=(200, 40, 30, 255))
        # draw wall-layer segments green
        for p0, p1, _ in wall_walls:
            if minx - pad <= (p0[0] + p1[0]) / 2 <= maxx + pad and miny - pad <= (p0[1] + p1[1]) / 2 <= maxy + pad:
                dd.line([p0[0]*Z-ox, p0[1]*Z-oy, p1[0]*Z-ox, p1[1]*Z-oy], fill=(0, 160, 80, 230), width=2)
        # between-lines + anchors
        rsl = sorted(rs)
        for rn in rsl:
            x, y = anchors[rn]
            dd.ellipse([x*Z-ox-5, y*Z-oy-5, x*Z-ox+5, y*Z-oy+5], fill=(20, 40, 220, 255))
            dd.text((x*Z-ox+6, y*Z-oy-6), f"{rn} {ROOMS[rn]}", fill=(10, 20, 120, 255), font=fnt)
        for k in range(len(rsl) - 1):
            a = anchors[rsl[k]]; b = anchors[rsl[k+1]]
            dd.line([a[0]*Z-ox, a[1]*Z-oy, b[0]*Z-ox, b[1]*Z-oy], fill=(30, 60, 230, 200), width=2)
        crop.convert("RGB").save(os.path.join(OUT, f"merge_poly{i}_{'_'.join(map(str,rsl))}.jpg"), "JPEG", quality=88)

    doc.close(); os.remove(pdf)
    print(f"\ncrops -> {os.path.relpath(OUT, ROOT)}/  (green=wall segs, red=merged blob, blue=room anchors+link)")


if __name__ == "__main__":
    main()
