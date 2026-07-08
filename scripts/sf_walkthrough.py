#!/usr/bin/env python3
"""Learning walkthrough: emit the intermediate overlays the SF pipeline
normally throws away, so a non-technical reader can SEE each stage:
  A raw floor plan
  B + every vector segment the PDF hands us (looks like chaos)
  C + only the segments kept as wall candidates
  D + the room polygons we closed, with SF printed in each

Reuses the real pipeline functions from probe2_sf.py. Writes to
data/walkthrough_001/ and a stats.json. Usage:
  python3 sf_walkthrough.py [PERMIT DOC_ID PAGE_INDEX]
"""
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, SCALE_RE, r2_client, download_pdf, extract_drawings, wall_candidates,
    suppress_hatches, snap_and_close, polygonize_rooms, cluster_by_touching,
    find_scale,
)

PERMIT = sys.argv[1] if len(sys.argv) > 1 else "14-11290-NEWC"
DOC = int(sys.argv[2]) if len(sys.argv) > 2 else 1494156
PAGE = int(sys.argv[3]) if len(sys.argv) > 3 else 3
ZOOM = 2.4

OUT = os.path.join(ROOT, "data", f"walkthrough_{PERMIT}_p{PAGE}")
os.makedirs(OUT, exist_ok=True)


def base_image(pdf):
    doc = fitz.open(pdf)
    pg = doc[PAGE]
    pix = pg.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    doc.close()
    return im


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def draw_segs(im, segs, color, w=1):
    d = ImageDraw.Draw(im, "RGBA")
    for s in segs:
        p0, p1 = s[0], s[1]
        d.line([p0[0] * ZOOM, p0[1] * ZOOM, p1[0] * ZOOM, p1[1] * ZOOM], fill=color, width=w)


def save(im, name):
    path = os.path.join(OUT, name)
    im.convert("RGB").save(path, "JPEG", quality=82)
    return path


def main():
    s3 = r2_client()
    pdf = download_pdf(s3, DOC)
    stats = dict(permit=PERMIT, doc_id=DOC, page_index=PAGE)
    try:
        # --- scale (pagetext, else from the PDF's own text) ---
        feet_per_pt, scale_text = find_scale(DOC, PAGE)
        if feet_per_pt is None:
            doc = fitz.open(pdf)
            txt = doc[PAGE].get_text()
            doc.close()
            ms = SCALE_RE.findall(txt)
            if ms:
                num, den = int(ms[0][0]), int(ms[0][1])
                feet_per_pt = (den / num) / 72.0
                scale_text = f'{num}/{den}" = 1\'-0"'
        stats["scale_text"] = scale_text
        stats["feet_per_pt"] = feet_per_pt

        ex = extract_drawings(pdf, PAGE)
        pw, ph = ex["pw"], ex["ph"]
        all_segs = ex["line_segments"] + ex["fill_rect_edges"]
        stats["page_size_pts"] = [round(pw, 1), round(ph, 1)]
        stats["n_line_segments"] = len(ex["line_segments"])
        stats["n_fill_rect_edges"] = len(ex["fill_rect_edges"])
        stats["n_door_arcs"] = len(ex["arcs"])
        stats["is_vector"] = len(all_segs) > 50

        # --- A: raw ---
        raw = base_image(pdf)
        save(raw.copy(), "A_raw_plan.jpg")

        # --- B: all vectors ---
        b = raw.copy()
        draw_segs(b, ex["line_segments"], (40, 90, 210, 150), 1)
        draw_segs(b, ex["fill_rect_edges"], (210, 60, 60, 160), 2)
        save(b, "B_all_vectors.jpg")

        # --- C: wall candidates (after alignment/width filter + hatch removal) ---
        walls, dom, thick = wall_candidates(ex)
        walls_clean, n_hatch = suppress_hatches(walls, pw)
        stats["dominant_angle_deg"] = round(dom, 2)
        stats["n_wall_candidates"] = len(walls)
        stats["n_hatch_dropped"] = n_hatch
        stats["n_wall_candidates_clean"] = len(walls_clean)
        c = raw.copy()
        draw_segs(c, ex["line_segments"], (200, 200, 200, 70), 1)  # ghost of everything
        draw_segs(c, walls_clean, (0, 150, 90, 255), 3)            # the walls, bold
        save(c, "C_wall_candidates.jpg")

        # --- D: polygons + SF ---
        lines, gap = snap_and_close(walls_clean, ex["arcs"], pw, feet_per_pt=feet_per_pt or None)
        stats["gap_closing"] = gap
        rooms_all, n_faces = polygonize_rooms(
            lines, pw, ph, 15, 5000, feet_per_pt or 0.01)
        stats["n_polygon_faces"] = n_faces
        stats["n_rooms"] = len(rooms_all)

        d = raw.copy()
        dd = ImageDraw.Draw(d, "RGBA")
        total = 0.0
        if rooms_all and feet_per_pt:
            # keep only realistically room-sized closures (drop the whole-footprint
            # / notes-area over-closures that flood the page) for a legible picture
            rooms = [p for p in rooms_all if 15 <= p.area * feet_per_pt ** 2 <= 900]
            fnt = font(max(13, int(7 * ZOOM)))
            for poly in rooms:
                sqft = poly.area * (feet_per_pt ** 2)
                total += sqft
                pts = [(x * ZOOM, y * ZOOM) for x, y in poly.exterior.coords]
                dd.polygon(pts, fill=(0, 170, 90, 80), outline=(0, 130, 65, 255))
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                label = f"{sqft:.0f}"
                tb = dd.textbbox((0, 0), label, font=fnt)
                dd.text((cx - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2),
                        label, fill=(8, 50, 25, 255), font=fnt)
            stats["n_rooms_drawn"] = len(rooms)
            stats["total_sqft_rooms"] = round(total, 1)
        save(d, "D_detected_polygons.jpg")

        # --- a small raw-vector sample so the reader sees the real data shape ---
        sample = []
        for p0, p1, w in ex["line_segments"][:40]:
            sample.append(dict(
                kind="line",
                x1=round(p0[0], 1), y1=round(p0[1], 1),
                x2=round(p1[0], 1), y2=round(p1[1], 1),
                length_pts=round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1),
                stroke_width=round(w, 3),
            ))
        with open(os.path.join(OUT, "raw_vector_sample.json"), "w") as f:
            json.dump(sample, f, indent=2)

        stats["overlays"] = ["A_raw_plan.jpg", "B_all_vectors.jpg",
                             "C_wall_candidates.jpg", "D_detected_polygons.jpg"]
        with open(os.path.join(OUT, "stats.json"), "w") as f:
            json.dump(stats, f, indent=2)
        print(json.dumps(stats, indent=2, default=str))
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass


if __name__ == "__main__":
    main()
