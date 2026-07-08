#!/usr/bin/env python3
"""Render a dimension-visible crop for ALL 18 branch rooms (enclosed + open), each
tagged with our geometry area when we have one. Feeds the vision fleet that reads
the printed dimensions -> per-room area -> the complete takeoff."""
import os, sys, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point
from probe2_sf import ROOT, r2_client, download_pdf, snap_and_close, polygonize_rooms, find_scale, SCALE_RE, seg_len
from probe7_layer_walls import extract_wall_layer_segments
from probe4_room_sf import ROOMS

DOC, PAGE, Z = 1494156, 3, 6.0
OUT = os.path.join(ROOT, "data", "probe15"); os.makedirs(OUT, exist_ok=True)


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

    segs, _pw, _ph, _u = extract_wall_layer_segments(pdf, PAGE)
    walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
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

    pm = page.get_pixmap(matrix=fitz.Matrix(Z, Z), alpha=False)
    full = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
    fnt = font(30)
    PAD_FT = 15.0
    manifest = []
    for rn, (ax, ay) in sorted(anchors.items()):
        i = room_poly.get(rn)
        single = i is not None and len(poly_rooms[i]) == 1
        if single:
            minx, miny, maxx, maxy = polys[i].bounds
            padx = (maxx-minx)*0.55 + 10; pady = (maxy-miny)*0.55 + 10
            geom = round(polys[i].area * fpp**2, 1)
        else:
            r = PAD_FT / fpp
            minx, miny, maxx, maxy = ax-r, ay-r, ax+r, ay+r
            padx = pady = 8
            geom = None
        box = (max(0, int((minx-padx)*Z)), max(0, int((miny-pady)*Z)),
               min(pm.width, int((maxx+padx)*Z)), min(pm.height, int((maxy+pady)*Z)))
        crop = full.crop(box).copy(); dd = ImageDraw.Draw(crop)
        if single:
            ox, oy = box[0], box[1]
            pts = [(x*Z-ox, y*Z-oy) for x, y in polys[i].exterior.coords]
            dd.line(pts + [pts[0]], fill=(220, 30, 30), width=3)
        tag = f"{rn} {ROOMS[rn]}  |  geom = {geom} SF" if single else f"{rn} {ROOMS[rn]}  |  OPEN (no single polygon)"
        dd.rectangle([0, 0, 640, 40], fill=(0, 0, 0)); dd.text((6, 5), tag, fill=(255, 255, 0), font=fnt)
        path = os.path.join(OUT, f"room_{rn}.png"); crop.save(path)
        manifest.append(dict(room=rn, name=ROOMS[rn], geom_sf=geom, open=not single,
                             path=os.path.relpath(path, ROOT)))
    doc.close(); os.remove(pdf)
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"), indent=2)
    print(f"rendered {len(manifest)} rooms -> data/probe15/")
    for m in manifest:
        print(f"  {m['room']} {m['name']:<13} geom={m['geom_sf']} open={m['open']}")


if __name__ == "__main__":
    main()
