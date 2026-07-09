#!/usr/bin/env python3
"""Failure-mode census over the 25 hand-picked permits.

For each, run the measuring on its floor plan and record ONE plain-English
outcome — so we get a ranked list of what actually blocks us and how often,
instead of guessing. Also notes whether the permit has a finish schedule
(materials) and/or an area schedule (the answer key we can grade against).

Plain buckets:
  MEASURED        rooms close into plausible shapes -> we can measure SF now
  WONT_CLOSE      wall lines are there, but rooms don't close (open plan / gaps / 3D-solid)
  NO_WALL_TAGS    the plan never tags its walls -> nothing to trace (needs the model)
  NO_FLOOR_PLAN   no labeled floor plan page at all
"""
import os, sys, csv, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.ops import unary_union, polygonize
from probe2_sf import ROOT, r2_client, download_pdf, snap_and_close, seg_len
from probe7_layer_walls import extract_wall_layer_segments

BATCH = json.load(open(os.path.join(ROOT, "data", "triage", "label_batch25.json")))
PERMITS = list(BATCH.keys())
AREA_CSV = os.path.join(ROOT, "data", "triage", "area_schedule_candidates.csv")
OUT = os.path.join(ROOT, "data", "triage", "census_25.csv")


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


def score(pdf, pi):
    pg = fitz.open(pdf)[pi]; pw, ph = pg.rect.width, pg.rect.height
    segs, _, _, used = extract_wall_layer_segments(pdf, pi)
    walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
    if not (used and walls):
        return dict(named=False, mid=0, cover=0.0, largest=0.0, layers=used[:3])
    lines, _ = snap_and_close([(p0, p1, seg_len(p0, p1), w) for p0, p1, w in walls],
                              [], pw, feet_per_pt=0.1)
    polys = list(polygonize(unary_union(lines)))
    xs = [c for a, b, w in walls for c in (a[0], b[0])]
    ys = [c for a, b, w in walls for c in (a[1], b[1])]
    bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    # compactness guard: a "room" is a mid-band polygon that is NOT a thin sliver
    rooms = 0
    for p in polys:
        a = p.area
        if a >= 0.9 * bbox or not (0.004 * bbox <= a <= 0.25 * bbox):
            continue
        # Polsby-Popper compactness 4*pi*A/P^2 ; slivers (wall cavities) score low
        comp = 4 * 3.14159 * a / (p.length ** 2) if p.length else 0
        if comp >= 0.25:
            rooms += 1
    return dict(named=True, mid=rooms, cover=0.0, largest=0.0, layers=used[:3])


def main():
    c = cur()
    # area-schedule permits (answer keys) confirmed by vision this session
    area_permits = {"24-06233-RNVS", "24-06748-RNVS", "20-29653-RNVS", "16-17098-NEWC"}
    rows = []
    for pn in PERMITS:
        c.execute("""SELECT d.onestop_doc_id od, array_agg(DISTINCT p.page_index) pages
                     FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
                     JOIN estimate.page_label pl ON pl.page_id=p.id
                     WHERE d.permit_num=%s AND pl.category='floor_plan'
                     GROUP BY d.onestop_doc_id""", (pn,))
        fp = c.fetchall()
        c.execute("""SELECT count(*) n FROM estimate.page p JOIN estimate.document d ON p.document_id=d.id
                     JOIN estimate.page_label pl ON pl.page_id=p.id
                     WHERE d.permit_num=%s AND pl.category IN ('finish_schedule','finish_plan')""", (pn,))
        has_finish = c.fetchone()["n"] > 0
        if not fp:
            rows.append(dict(permit=pn, verdict="NO_FLOOR_PLAN", named="", rooms="",
                             layer="", finish="Y" if has_finish else "", area="")); continue
        od = fp[0]["od"]; pages = fp[0]["pages"]
        s3 = r2_client()
        try:
            pdf = download_pdf(s3, od)
        except Exception as e:
            rows.append(dict(permit=pn, verdict="dl_err", named="", rooms="", layer="",
                             finish="Y" if has_finish else "", area="")); continue
        best = None
        try:
            for pi in pages:
                try:
                    m = score(pdf, pi)
                except Exception:
                    continue
                if best is None or (m["named"], m["mid"]) > (best["named"], best["mid"]):
                    best = m
        finally:
            try: os.remove(pdf)
            except OSError: pass
        m = best or dict(named=False, mid=0, layers=[])
        layer = "|".join(m["layers"])
        is3d = ".3d" in layer.lower() or "3d" in layer.lower()
        if not m["named"]:
            verdict = "NO_WALL_TAGS"
        elif m["mid"] >= 4 and not is3d:
            verdict = "MEASURED"
        else:
            verdict = "WONT_CLOSE"
        rows.append(dict(permit=pn, verdict=verdict, named="Y" if m["named"] else "",
                         rooms=m["mid"], layer=layer[:30],
                         finish="Y" if has_finish else "", area="Y" if pn in area_permits else ""))
        print(f"{pn:<16} {verdict:<14} rooms={m['mid']} layer={layer[:28]}", flush=True)

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["permit", "verdict", "named", "rooms", "layer", "finish", "area"])
        w.writeheader(); [w.writerow(r) for r in rows]

    from collections import Counter
    cnt = Counter(r["verdict"] for r in rows)
    print("\n===== RANKED FAILURE-MODE CENSUS (25 permits) =====")
    for v, n in cnt.most_common():
        print(f"  {n:>2}  {v}")
    nf = sum(1 for r in rows if r["finish"] == "Y")
    print(f"\nhave a finish schedule/plan (materials readable): {nf}/25")
    print(f"have an area schedule (answer key): {sum(1 for r in rows if r['area']=='Y')}/25")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
