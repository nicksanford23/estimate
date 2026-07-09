#!/usr/bin/env python3
"""Fill data/triage/debug_25/{geometry,overlays} for all 25 permits: run the
thickness engine on each best floor-plan page, save the polygon result JSON and
a numbered-polygon overlay JPG. Resumable (skips permits already written)."""
import os, sys, json
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.ops import unary_union, polygonize
from probe2_sf import (ROOT, r2_client, download_pdf, extract_drawings,
    wall_candidates, suppress_hatches, snap_and_close)
from page_select import select_floor_plan_page

BATCH = json.load(open(os.path.join(ROOT, "data", "triage", "label_batch25.json")))
PERMITS = list(BATCH.keys())
DBG = os.path.join(ROOT, "data", "triage", "debug_25")
GEO = os.path.join(DBG, "geometry"); OVR = os.path.join(DBG, "overlays")
FP = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PI2 = 3.14159


def env():
    e = {}
    for l in open(os.path.join(ROOT, ".env")):
        l = l.strip()
        if l and not l.startswith("#") and "=" in l:
            k, v = l.split("=", 1); e[k] = v
    return e


def cur():
    import psycopg2, psycopg2.extras
    return psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def rooms_on(pdf, pi):
    ex = extract_drawings(pdf, pi); pw, ph = ex["pw"], ex["ph"]
    walls, dom, thick = wall_candidates(ex); wc, _ = suppress_hatches(walls, pw)
    if not wc:
        return pw, ph, [], 0, 0.0
    lines, _ = snap_and_close(wc, ex["arcs"], pw, feet_per_pt=0.1)
    polys = list(polygonize(unary_union(lines)))
    xs = [c for a, b, L, w in wc for c in (a[0], b[0])]
    ys = [c for a, b, L, w in wc for c in (a[1], b[1])]
    bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    rooms = []; largest = 0.0
    for p in polys:
        a = p.area; largest = max(largest, a / bbox)
        if a >= 0.9 * bbox or not (0.004 * bbox <= a <= 0.25 * bbox):
            continue
        if p.length and 4 * PI2 * a / p.length ** 2 >= 0.25:
            rooms.append(p)
    rooms.sort(key=lambda p: -p.area)
    return pw, ph, rooms, len(wc), round(largest, 2)


def run_one(pn):
    gpath = os.path.join(GEO, pn + ".json")
    if os.path.exists(gpath) and os.path.exists(os.path.join(OVR, pn + ".jpg")):
        return f"{pn} skip"
    c = cur()
    c.execute("""SELECT DISTINCT d.onestop_doc_id od, p.page_index pi, pl.sheet_title st
                 FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
                 JOIN estimate.page_label pl ON pl.page_id=p.id
                 WHERE d.permit_num=%s AND pl.category='floor_plan'
                 ORDER BY d.onestop_doc_id, p.page_index""", (pn,))
    fp = c.fetchall()
    if not fp:
        json.dump(dict(permit=pn, verdict="NO_FLOOR_PLAN", rooms_counted=0), open(gpath, "w"), indent=1)
        return f"{pn} no_fp"
    od = fp[0]["od"]
    pages_titles = [(r["pi"], r["st"]) for r in fp if r["od"] == od]
    s3 = r2_client(); pdf = download_pdf(s3, od); doc = fitz.open(pdf)
    # MERGED page-selection (page_select.py) — replaces "page with most polygons"
    pi = select_floor_plan_page(doc, pages_titles)
    try:
        pw, ph, rooms, nw, lg = rooms_on(pdf, pi)
    except Exception:
        doc.close(); os.remove(pdf)
        json.dump(dict(permit=pn, verdict="ERR", rooms_counted=0), open(gpath, "w"), indent=1)
        return f"{pn} err"
    # geometry json
    geo = dict(permit=pn, doc_id=od, floor_plan_page=pi, n_walls=nw, rooms_counted=len(rooms),
               largest_blob_frac=lg,
               polygons=[dict(id=i + 1, area_frac=round(p.area / (pw * ph), 4),
                              cx=round(p.centroid.x / pw, 3), cy=round(p.centroid.y / ph, 3))
                         for i, p in enumerate(rooms)])
    json.dump(geo, open(gpath, "w"), indent=1)
    # overlay
    Z = 2.2; pg = doc[pi]
    pm = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), alpha=False)
    im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
    dd = ImageDraw.Draw(im, "RGBA")
    fnt = ImageFont.truetype(FP, int(11 * Z)) if os.path.exists(FP) else ImageFont.load_default()
    for i, p in enumerate(rooms, 1):
        pts = [(x * Z, y * Z) for x, y in p.exterior.coords]
        dd.polygon(pts, fill=(0, 160, 90, 85), outline=(210, 0, 0, 255))
        c2 = p.centroid
        dd.text((c2.x * Z - 8, c2.y * Z - 10), str(i), fill=(0, 0, 160, 255), font=fnt)
    im.convert("RGB").save(os.path.join(OVR, pn + ".jpg"), "JPEG", quality=82)
    doc.close(); os.remove(pdf)
    return f"{pn} ok rooms={len(rooms)} walls={nw}"


def main():
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in as_completed({ex.submit(run_one, pn): pn for pn in PERMITS}):
            print(f.result(), flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
