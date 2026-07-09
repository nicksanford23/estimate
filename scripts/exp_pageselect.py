"""EXPERIMENT (isolated). Test PAGE-SELECTION only, across all 25: for each
permit compare the OLD pick (page with most compact polygons) vs the NEW pick
(title score, then room-label density). Report which changed and whether the new
sheet looks better (more room labels, non-phasing/demo title). Not merged."""
import os, sys, re, json
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.ops import unary_union, polygonize
from probe2_sf import (ROOT, r2_client, download_pdf, extract_drawings,
    wall_candidates, suppress_hatches, snap_and_close)

BATCH = list(json.load(open(os.path.join(ROOT, "data", "triage", "label_batch25.json"))).keys())
TITLE_BAD = re.compile(r"phas|demo|overall|context|partition type|\bdetail|schedul|legend|"
                       r"\bnotes?\b|cover|index|\bsite\b|roof|ceiling|elevation|section", re.I)
TITLE_GOOD = re.compile(r"floor plan|enlarged|tenant|1st|2nd|3rd|first floor|second floor|"
                        r"level|unit|\bplan\b", re.I)
ROOM_NUM = re.compile(r"^\d{2,4}[A-Za-z]?$")
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


def tscore(t):
    t = t or ""
    return (2 if TITLE_GOOD.search(t) else 0) - (3 if TITLE_BAD.search(t) else 0)


def labels(pg):
    return sum(1 for w in pg.get_text("words") if ROOM_NUM.match(w[4].strip()))


def polys_on(pdf, pi):
    ex = extract_drawings(pdf, pi); pw, ph = ex["pw"], ex["ph"]
    walls, dom, thick = wall_candidates(ex); wc, _ = suppress_hatches(walls, pw)
    if not wc:
        return 0
    lines, _ = snap_and_close(wc, ex["arcs"], pw, feet_per_pt=0.1)
    ps = list(polygonize(unary_union(lines)))
    xs = [c for a, b, L, w in wc for c in (a[0], b[0])]
    ys = [c for a, b, L, w in wc for c in (a[1], b[1])]
    bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    return sum(1 for p in ps if 0.004 * bbox <= p.area <= 0.25 * bbox
               and p.length and 4 * PI2 * p.area / p.length ** 2 >= 0.25)


def run(pn):
    c = cur()
    c.execute("""SELECT DISTINCT d.onestop_doc_id od, p.page_index pi, pl.sheet_title st
                 FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
                 JOIN estimate.page_label pl ON pl.page_id=p.id
                 WHERE d.permit_num=%s AND pl.category='floor_plan'
                 ORDER BY p.page_index""", (pn,))
    cand = c.fetchall()
    if not cand:
        return dict(permit=pn, note="no floor plan")
    od = cand[0]["od"]
    s3 = r2_client(); pdf = download_pdf(s3, od); doc = fitz.open(pdf)
    rows = []
    for r in cand[:6]:
        try:
            np_ = polys_on(pdf, r["pi"]); lb = labels(doc[r["pi"]])
        except Exception:
            continue
        rows.append((r["pi"], r["st"] or "", np_, lb, tscore(r["st"])))
    doc.close(); os.remove(pdf)
    if not rows:
        return dict(permit=pn, note="no pages scored")
    old = max(rows, key=lambda x: x[2])                 # most polys
    # NEW: drop clearly-bad-title pages first (tscore>-1), then most room labels,
    # then most polys. Labels dominate title among plausible floor-plan sheets.
    new = max(rows, key=lambda x: (x[4] > -1, x[3], x[2]))
    return dict(permit=pn, changed=old[0] != new[0], n_pages=len(rows),
                old_pi=old[0], old_title=old[1][:24], old_labels=old[3],
                new_pi=new[0], new_title=new[1][:24], new_labels=new[3])


def main():
    rows = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in as_completed({ex.submit(run, pn): pn for pn in BATCH}):
            rows.append(f.result())
    rows.sort(key=lambda r: r["permit"])
    print(f"{'permit':<16}{'chg':>4}{'oldLbl':>7}{'newLbl':>7}  old→new sheet")
    changed = better = 0
    for r in rows:
        if r.get("note"):
            print(f"{r['permit']:<16}  {r['note']}"); continue
        mark = "YES" if r["changed"] else "."
        if r["changed"]:
            changed += 1
            if r["new_labels"] > r["old_labels"]:
                better += 1
        arrow = f"{r['old_title']}  ->  {r['new_title']}" if r["changed"] else r["new_title"]
        print(f"{r['permit']:<16}{mark:>4}{r['old_labels']:>7}{r['new_labels']:>7}  {arrow}")
    print(f"\npages changed: {changed}/25 ; of those, new page has MORE room labels: {better}")


if __name__ == "__main__":
    main()
