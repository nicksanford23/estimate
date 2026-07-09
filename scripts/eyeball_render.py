#!/usr/bin/env python3
"""Eyeball-verification overlay renderer for the usability audit (slice work).

Reuses the exact scoring pipeline in scan_closeability_full.score_page_v2 /
extract_by_layer (which itself reuses probe7_layer_walls.WALL_RE +
probe2_sf.snap_and_close) so the polygons drawn are the SAME polygons the
gate scored -- not a fresh re-implementation. Renders the page image with
room-band ("mid") polygons filled green (these are what the gate counted
toward n_mid/cov_mid) and the largest blob outlined red (what largest_frac
measured), so an eyeball can judge real-rooms vs confetti directly against
the gate's own metrics.

Usage: python3 eyeball_render.py <permit> <doc_id> <page> <fpp> <out_jpg>
Downloads the PDF, renders, deletes the PDF. Idempotent (skips if out_jpg
already exists) unless --force given.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from shapely.ops import unary_union, polygonize  # noqa: E402
from probe2_sf import r2_client, download_pdf, snap_and_close, seg_len  # noqa: E402
from scan_closeability_full import extract_by_layer  # noqa: E402

ZOOM = 2.2
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(sz):
    return ImageFont.truetype(FONT_PATH, sz) if os.path.exists(FONT_PATH) else ImageFont.load_default()


def render(permit, doc_id, page, fpp, out_jpg, force=False):
    if os.path.exists(out_jpg) and not force:
        print(f"{permit} SKIP (exists)", flush=True)
        return

    s3 = r2_client()
    pdf = download_pdf(s3, doc_id)
    try:
        segs, pw, ph = extract_by_layer(pdf, page)
        walls = [(p0, p1, w, lay) for p0, p1, w, lay in segs if seg_len(p0, p1) > 0.008 * pw]
        if not walls:
            print(f"{permit} NO_WALL_SEGS pw={pw} ph={ph}", flush=True)
        xs = [c for p0, p1, w, lay in walls for c in (p0[0], p1[0])]
        ys = [c for p0, p1, w, lay in walls for c in (p0[1], p1[1])]
        bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys))) if walls else 1.0

        lines, _ = snap_and_close(
            [(p0, p1, seg_len(p0, p1), w) for p0, p1, w, lay in walls], [], pw,
            feet_per_pt=fpp)
        polys = list(polygonize(unary_union(lines))) if lines else []
        areas = [(p, p.area) for p in polys if p.area < 0.9 * bbox]
        mid = [(p, a) for p, a in areas if 0.002 * bbox <= a <= 0.08 * bbox]
        largest = max(areas, key=lambda pa: pa[1]) if areas else None

        doc = fitz.open(pdf)
        pg = doc[page]
        pm = pg.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
        im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
        doc.close()
        dd = ImageDraw.Draw(im, "RGBA")
        fnt = font(int(9 * ZOOM))

        for p, a in areas:
            if (p, a) in mid:
                continue
            pts = [(x * ZOOM, y * ZOOM) for x, y in p.exterior.coords]
            dd.polygon(pts, outline=(120, 120, 120, 160))

        for i, (p, a) in enumerate(mid, 1):
            pts = [(x * ZOOM, y * ZOOM) for x, y in p.exterior.coords]
            dd.polygon(pts, fill=(0, 170, 90, 95), outline=(0, 100, 60, 255))
            c = p.centroid
            sqft = a * fpp ** 2
            dd.text((c.x * ZOOM - 10, c.y * ZOOM - 8), f"{i}:{sqft:.0f}sf",
                     fill=(10, 20, 140, 255), font=fnt)

        if largest is not None:
            p, a = largest
            pts = [(x * ZOOM, y * ZOOM) for x, y in p.exterior.coords]
            dd.polygon(pts, outline=(210, 0, 0, 255))

        os.makedirs(os.path.dirname(out_jpg), exist_ok=True)
        im.convert("RGB").save(out_jpg, "JPEG", quality=86)
        print(f"{permit} OK n_mid={len(mid)} n_polys={len(polys)} "
              f"largest_frac={(largest[1] / bbox if largest else 0):.3f} -> {out_jpg}", flush=True)
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass


if __name__ == "__main__":
    permit, doc_id, page, fpp, out_jpg = sys.argv[1:6]
    force = "--force" in sys.argv
    render(permit, int(doc_id), int(page), float(fpp), out_jpg, force=force)
