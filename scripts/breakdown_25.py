#!/usr/bin/env python3
"""Room-by-room breakdown over the 25 hand-picked permits, using the THICKNESS-
based engine (the one that closed 8/18 rooms on the bank with no wall tags) —
so it attempts every plan, not just the layered ones.

Scale-free (closure doesn't need scale): for each permit's best floor-plan page
run extract -> wall_candidates -> suppress_hatches -> snap_and_close -> polygonize,
then count how many polygons are plausible, compact ROOMS (vs the outer shell,
slivers, or one giant open blob). Emits per-plan counts + a plain verdict so we
know WHERE to debug next.
"""
import os, sys, csv, json
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.ops import unary_union, polygonize
from probe2_sf import (ROOT, r2_client, download_pdf, extract_drawings,
    wall_candidates, suppress_hatches, snap_and_close, seg_len)

BATCH = json.load(open(os.path.join(ROOT, "data", "triage", "label_batch25.json")))
PERMITS = list(BATCH.keys())
OUT = os.path.join(ROOT, "data", "triage", "breakdown_25.csv")
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


def analyze(pdf, pi):
    ex = extract_drawings(pdf, pi)
    pw, ph = ex["pw"], ex["ph"]
    walls, dom, thick = wall_candidates(ex)
    walls_clean, _ = suppress_hatches(walls, pw)
    if not walls_clean:
        return dict(n_walls=0, rooms=0, polys=0, largest=0.0)
    lines, _ = snap_and_close(walls_clean, ex["arcs"], pw, feet_per_pt=0.1)
    polys = list(polygonize(unary_union(lines)))
    xs = [c for p0, p1, L, w in walls_clean for c in (p0[0], p1[0])]
    ys = [c for p0, p1, L, w in walls_clean for c in (p0[1], p1[1])]
    bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    rooms = 0; largest = 0.0
    for p in polys:
        a = p.area
        largest = max(largest, a / bbox)
        if a >= 0.9 * bbox or not (0.004 * bbox <= a <= 0.25 * bbox):
            continue
        comp = 4 * PI2 * a / (p.length ** 2) if p.length else 0
        if comp >= 0.25:            # compact enough to be a room, not a sliver
            rooms += 1
    return dict(n_walls=len(walls_clean), rooms=rooms, polys=len(polys), largest=round(largest, 2))


def verdict(m):
    if m["n_walls"] <= 40:
        return "FEW_WALLS_FOUND"        # engine barely found wall linework
    if m["rooms"] >= 6 and m["largest"] < 0.5:
        return "CLOSES_WELL"
    if m["rooms"] >= 2:
        return "PARTIAL"
    if m["largest"] >= 0.5:
        return "ONE_BIG_BLOB"           # open plan — everything is one polygon
    return "WALLS_BUT_NO_ROOMS"         # walls present, nothing closes (gaps/clutter)


def run_one(pn):
    c = cur()
    c.execute("""SELECT d.onestop_doc_id od, array_agg(DISTINCT p.page_index ORDER BY p.page_index) pages
                 FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
                 JOIN estimate.page_label pl ON pl.page_id=p.id
                 WHERE d.permit_num=%s AND pl.category='floor_plan' GROUP BY d.onestop_doc_id""", (pn,))
    fp = c.fetchall()
    if not fp:
        return dict(permit=pn, verdict="NO_FLOOR_PLAN", n_walls=0, rooms=0, polys=0, largest=0, page=-1)
    od, pages = fp[0]["od"], fp[0]["pages"][:3]
    s3 = r2_client()
    try:
        pdf = download_pdf(s3, od)
    except Exception:
        return dict(permit=pn, verdict="DL_ERR", n_walls=0, rooms=0, polys=0, largest=0, page=-1)
    best = None
    try:
        for pi in pages:
            try:
                m = analyze(pdf, pi)
            except Exception:
                continue
            if best is None or m["rooms"] > best[1]["rooms"]:
                best = (pi, m)
    finally:
        try: os.remove(pdf)
        except OSError: pass
    if best is None:
        return dict(permit=pn, verdict="ERR", n_walls=0, rooms=0, polys=0, largest=0, page=-1)
    pi, m = best
    return dict(permit=pn, verdict=verdict(m), page=pi, **m)


def main():
    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run_one, pn): pn for pn in PERMITS}
        for f in as_completed(futs):
            r = f.result(); rows.append(r)
            print(f"{r['permit']:<16} {r['verdict']:<18} rooms={r['rooms']:<3} "
                  f"walls={r['n_walls']:<4} biggest={r['largest']}", flush=True)
    rows.sort(key=lambda r: -r["rooms"])
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["permit", "verdict", "page", "n_walls", "rooms", "polys", "largest"])
        w.writeheader(); [w.writerow(r) for r in rows]
    from collections import Counter
    print("\n===== BREAKDOWN (25 permits, thickness engine) =====")
    for v, n in Counter(r["verdict"] for r in rows).most_common():
        print(f"  {n:>2}  {v}")
    total_rooms = sum(r["rooms"] for r in rows)
    got = [r for r in rows if r["rooms"] >= 2]
    print(f"\nplans that close >=2 rooms: {len(got)}/25")
    print(f"total rooms closed across all 25: {total_rooms}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
