#!/usr/bin/env python3
"""Closeability scan — the quality gate the segment-count test was missing.

For every permit that has a labeled floor_plan page, download the doc, take the
richest floor-plan page, and measure whether its wall linework actually
POLYGONIZES into rooms. This is what separates 26-10321 (clean NEW/EXIST WALL
2D layers → rooms close) from 25-33341 (`A - Walls - Exterior.3D` solid → 16k
fragments, nothing closes) even though both pass a wall-segment-count test.

Scale-free metrics (no fpp needed — we're scoring geometry structure, not SF):
  has_named_layer : any WALL_RE-named layer carried linework
  n_wall_segs     : long wall segments (> 0.008*pw)
  n_polys         : polygons formed
  n_mid           : polygons in the room band (0.2%–8% of the wall bbox)
  coverage        : sum(poly area) / wall-bbox area   (how much footprint tiled)
  largest_frac    : biggest poly / wall-bbox area      (1 blob vs many rooms)

We emit the raw metrics for all 74 and calibrate the USABLE cut against the two
known cases, rather than hard-coding a verdict blind. Output is append-only and
resumable. Nothing is written to the shared tables.
"""
import os, sys, csv, json, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.ops import unary_union, polygonize
from probe2_sf import ROOT, r2_client, download_pdf, snap_and_close, seg_len
from probe7_layer_walls import extract_wall_layer_segments

OUT = os.path.join(ROOT, "data", "triage", "closeability.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
FIELDS = ["permit", "doc_id", "page", "has_named_layer", "n_wall_segs", "n_polys",
          "n_mid", "coverage", "largest_frac", "layers", "note"]
_wlock = threading.Lock()


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


def targets():
    c = cur()
    c.execute("""SELECT d.permit_num pn, d.onestop_doc_id od, array_agg(DISTINCT p.page_index) pages
                 FROM estimate.document d
                 JOIN estimate.page p ON p.document_id=d.id
                 JOIN estimate.page_label pl ON pl.page_id=p.id
                 WHERE pl.category='floor_plan'
                 GROUP BY d.permit_num, d.onestop_doc_id""")
    return c.fetchall()


def score_page(pdf, pi):
    """Metrics for one page. Uses the union bbox of wall segments as the
    scale-free denominator (the drawn footprint), not the whole sheet."""
    pg = fitz.open(pdf)[pi]; pw, ph = pg.rect.width, pg.rect.height
    segs, _, _, used = extract_wall_layer_segments(pdf, pi)
    walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
    has_named = len(used) > 0 and len(walls) > 0
    if not walls:
        return dict(has_named_layer=has_named, n_wall_segs=0, n_polys=0, n_mid=0,
                    coverage=0.0, largest_frac=0.0, layers=used[:4])
    lines, _ = snap_and_close([(p0, p1, seg_len(p0, p1), w) for p0, p1, w in walls],
                              [], pw, feet_per_pt=0.1)  # fpp irrelevant to structure
    polys = list(polygonize(unary_union(lines)))
    xs = [c for p0, p1, w in walls for c in (p0[0], p1[0])]
    ys = [c for p0, p1, w in walls for c in (p0[1], p1[1])]
    bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    areas = [p.area for p in polys if p.area < 0.9 * bbox]  # drop the outer shell
    n_mid = sum(1 for a in areas if 0.002 * bbox <= a <= 0.08 * bbox)
    coverage = sum(areas) / bbox if areas else 0.0
    largest = (max(areas) / bbox) if areas else 0.0
    return dict(has_named_layer=has_named, n_wall_segs=len(walls), n_polys=len(polys),
                n_mid=n_mid, coverage=round(coverage, 3), largest_frac=round(largest, 3),
                layers=used[:4])


def run_one(t):
    pn, od, pages = t["pn"], t["od"], t["pages"]
    s3 = r2_client()
    try:
        pdf = download_pdf(s3, od)
    except Exception as e:
        return dict(permit=pn, doc_id=od, page=-1, has_named_layer=False, n_wall_segs=0,
                    n_polys=0, n_mid=0, coverage=0, largest_frac=0, layers="", note=f"dl_err:{type(e).__name__}")
    best = None
    try:
        for pi in pages:
            try:
                m = score_page(pdf, pi)
            except Exception:
                continue
            key = (m["n_mid"], m["coverage"])
            if best is None or key > best[1]:
                best = (pi, key, m)
    finally:
        try: os.remove(pdf)
        except OSError: pass
    if best is None:
        return dict(permit=pn, doc_id=od, page=-1, has_named_layer=False, n_wall_segs=0,
                    n_polys=0, n_mid=0, coverage=0, largest_frac=0, layers="", note="no_page_scored")
    pi, _, m = best
    return dict(permit=pn, doc_id=od, page=pi, note="", layers="|".join(m.pop("layers")), **m)


def done():
    if not os.path.exists(OUT):
        return set()
    with open(OUT) as f:
        return {r["permit"] for r in csv.DictReader(f)}


def main():
    ts = [t for t in targets() if t["pn"] not in done()]
    print(f"scanning {len(ts)} permits (resumable)", flush=True)
    write_header = not os.path.exists(OUT) or os.path.getsize(OUT) == 0
    f = open(OUT, "a", newline=""); w = csv.DictWriter(f, fieldnames=FIELDS)
    if write_header: w.writeheader(); f.flush()
    n = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(run_one, t): t for t in ts}
        for fut in as_completed(futs):
            r = fut.result()
            with _wlock:
                w.writerow(r); f.flush()
            n += 1
            if n % 10 == 0 or n == len(ts):
                print(f"[{n}/{len(ts)}] {r['permit']} named={r['has_named_layer']} "
                      f"mid={r['n_mid']} cov={r['coverage']}", flush=True)
    f.close()
    print("DONE ->", OUT, flush=True)


if __name__ == "__main__":
    main()
