#!/usr/bin/env python3
"""Probe 7 — use the PDF's own CAD LAYERS. The file tags every line with its
layer (09-MTL STUD WALLS, 03-CMU, 09-gyp board, 09-Stucco = walls; Attic Storage
Above / i-furn / dimensions / tags = clutter). Extract ONLY the wall layers,
polygonize that CLEAN linework, and re-match the 18 rooms. Tests whether the
clutter/hatch problem simply disappears when we respect the layers.

Usage: python3 probe7_layer_walls.py
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from probe2_sf import (  # noqa: E402
    r2_client, download_pdf, dominant_angle, snap_and_close, polygonize_rooms,
    find_scale, SCALE_RE, seg_len,
)
from probe4_room_sf import ROOMS  # noqa: E402

DOC, PAGE, ZOOM = 1494156, 3, 2.6
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "probe7")
os.makedirs(OUT, exist_ok=True)

WALL_RE = re.compile(
    r"WALL|CMU|STUD|GYP|STUCCO|WINDOW|STORE|GLAZ|GLASS|CURTAIN|MULLION|FRAME|DOOR",
    re.IGNORECASE)


def font(sz):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def extract_wall_layer_segments(pdf, page_index):
    doc = fitz.open(pdf)
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    segs = []          # (p0, p1, width)
    used_layers = set()
    for d in page.get_drawings():
        lay = d.get("layer") or ""
        if not WALL_RE.search(lay):
            continue
        used_layers.add(lay)
        width = d.get("width") or 0.0
        is_fill = d.get("fill") is not None and d.get("type") in ("f", "fs")
        for item in d.get("items", []):
            if item[0] == "l":
                p0, p1 = (item[1].x, item[1].y), (item[2].x, item[2].y)
                segs.append((p0, p1, width if width else 1.0))
            elif item[0] == "re":
                r = item[1]
                rw, rh = r.width, r.height
                short, long = min(rw, rh), max(rw, rh)
                if is_fill and long > 0 and short / pw < 0.02 and long / max(pw, ph) > 0.01:
                    cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
                    if rw >= rh:
                        segs.append(((r.x0, cy), (r.x1, cy), short))
                    else:
                        segs.append(((cx, r.y0), (cx, r.y1), short))
    doc.close()
    return segs, pw, ph, sorted(used_layers)


def main():
    s3 = r2_client()
    pdf = download_pdf(s3, DOC)
    try:
        fpp, scale_text = find_scale(DOC, PAGE)
        if fpp is None:
            doc = fitz.open(pdf); m = SCALE_RE.findall(doc[PAGE].get_text()); doc.close()
            if m:
                fpp = (int(m[0][1]) / int(m[0][0])) / 72.0

        segs, pw, ph, used = extract_wall_layer_segments(pdf, PAGE)
        print(f"wall-layer segments: {len(segs)}   from layers: {used}\n")

        # keep only reasonably long segments (drop tiny stubs)
        walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
        # feed straight into snap + polygonize (no thickness/angle filtering needed —
        # the layer already told us these are walls)
        lines, _ = snap_and_close([(p0, p1, seg_len(p0, p1), w) for p0, p1, w in walls],
                                  [], pw, feet_per_pt=fpp)
        polys, nfaces = polygonize_rooms(lines, pw, ph, 15, 8000, fpp)

        # room anchors
        doc = fitz.open(pdf); page = doc[PAGE]
        anchors = {}
        for w in page.get_text("words"):
            t = w[4].strip()
            if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
                anchors[int(t)] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        doc.close()

        room_poly, poly_rooms = {}, defaultdict(list)
        for rn, (x, y) in anchors.items():
            for i, pg in enumerate(polys):
                if pg.contains(Point(x, y)):
                    room_poly[rn] = i; poly_rooms[i].append(rn); break

        counts = dict(closed=0, fragment=0, merged=0, no_polygon=0)
        rows = []
        for rn, name in ROOMS.items():
            pi = room_poly.get(rn)
            if pi is None:
                counts["no_polygon"] += 1; rows.append((rn, name, "no_polygon", None))
            elif len(poly_rooms[pi]) > 1:
                counts["merged"] += 1; rows.append((rn, name, "merged", None))
            else:
                a = polys[pi].area * fpp ** 2
                if a < 25:
                    counts["fragment"] += 1; rows.append((rn, name, "fragment", round(a, 1)))
                else:
                    counts["closed"] += 1; rows.append((rn, name, "closed", round(a, 1)))

        # overlay
        doc = fitz.open(pdf); pm = doc[PAGE].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
        im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA"); doc.close()
        dd = ImageDraw.Draw(im, "RGBA"); fnt = font(int(6 * ZOOM))
        for pi, mates in poly_rooms.items():
            col = (210, 70, 60, 90) if len(mates) > 1 else (0, 170, 90, 90)
            pts = [(x * ZOOM, y * ZOOM) for x, y in polys[pi].exterior.coords]
            dd.polygon(pts, fill=col, outline=(0, 100, 60, 255))
        for rn, (x, y) in anchors.items():
            r = next(z for z in rows if z[0] == rn)
            lab = f"{rn} {r[3]:.0f}sf" if r[3] else f"{rn} {r[2]}"
            dd.text((x * ZOOM, y * ZOOM), lab, fill=(10, 20, 90, 255), font=fnt)
        im.convert("RGB").save(os.path.join(OUT, "layer_overlay.jpg"), "JPEG", quality=86)

        print(f"scale={scale_text}  polygons={len(polys)}  anchors={len(anchors)}/18\n")
        for rn, name, st, a in sorted(rows):
            print(f"  {rn} {name:<14}{st:<12}{(str(a)+' sf') if a else ''}")
        print(f"\n  >>> closed={counts['closed']}  fragment={counts['fragment']}  "
              f"merged={counts['merged']}  no_polygon={counts['no_polygon']}   (was 8-11 closed)")
        print(f"  overlay -> {os.path.relpath(os.path.join(OUT,'layer_overlay.jpg'))}")
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass


if __name__ == "__main__":
    main()
