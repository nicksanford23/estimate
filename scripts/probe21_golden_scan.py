#!/usr/bin/env python3
"""Widened GOLDEN-SET scan across ALL downloaded permits. Per doc: find the best
wall-CENTERLINE page (usable layer geometry, not hatch) and the best per-room SF
schedule page (parseable room#->area). A permit is GOLDEN if it has both. This is
the definitive 'which permits validate the good path + seed ML'."""
import os, re, sys, threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from probe2_sf import ROOT, r2_client, seg_len
from probe8_layer_classes import classify_layer

BUCKET = "nola-permit-docs"
LOG = os.environ.get("GLOG", "/tmp/golden.log")
ROOMTOK = re.compile(r'^[A-Z]{0,2}-?\d{2,4}[A-Z]?$')
WALL_SEG_MIN = 200      # real floor-plan walls (filters hatch-only pages)
SF_ROOMS_MIN = 6        # a real per-room schedule
lock = threading.Lock()


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def parse_sched(words):
    rooms = [((w[1]+w[3])/2, w[0], w[4]) for w in words if ROOMTOK.match(w[4])]
    sf = []
    for w in words:
        if w[4].upper() in ("SF", "S.F."):
            yc, x = (w[1]+w[3])/2, w[0]
            cand = [(x-vw[2], int(vw[4])) for vw in words
                    if vw[4].isdigit() and abs((vw[1]+vw[3])/2 - yc) < 3 and vw[2] <= x and 0 <= x-vw[2] < 70]
            if cand: sf.append((yc, min(cand)[1]))
    gt = {}
    for yc, x, code in rooms:
        best = [(abs(yc-sy), a) for sy, a in sf if abs(yc-sy) < 4]
        if best and 5 <= min(best)[1] <= 5000 and code not in gt:
            gt[code] = min(best)[1]
    return len(gt), sum(gt.values())


def scan_doc(s3, doc_id):
    try:
        data = s3.get_object(Bucket=BUCKET, Key=f"docs/{doc_id}.pdf")["Body"].read()
        if data[:5] != b"%PDF-": return None
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        return None
    has_wall_ocg = any(classify_layer(v.get("name")) == "wall" for v in doc.get_ocgs().values())
    best_wall = (0, -1); best_sf = (0, -1, 0)
    for pi in range(min(doc.page_count, 40)):
        pg = doc[pi]
        r, tot = parse_sched(pg.get_text("words"))
        if r > best_sf[0]: best_sf = (r, pi, tot)
        if has_wall_ocg and pi < 30:
            pw = pg.rect.width; n = 0
            for d in pg.get_drawings():
                if classify_layer(d.get("layer")) != "wall": continue
                for it in d.get("items", []):
                    if it[0] == "l" and seg_len((it[1].x,it[1].y),(it[2].x,it[2].y)) > 0.008*pw:
                        n += 1
            if n > best_wall[0]: best_wall = (n, pi)
    doc.close()
    return doc_id, best_wall, best_sf


def main():
    s3 = r2_client(); ids = []; tok = None
    while True:
        kw = dict(Bucket=BUCKET, Prefix="docs/")
        if tok: kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            m = re.match(r"docs/(\d+)\.pdf$", o["Key"])
            if m: ids.append(int(m.group(1)))
        if r.get("IsTruncated"): tok = r["NextContinuationToken"]
        else: break
    import psycopg2, psycopg2.extras
    cur = psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT onestop_doc_id od, permit_num FROM estimate.document")
    permit = {r["od"]: r["permit_num"] for r in cur.fetchall()}

    # aggregate best wall + best sf per PERMIT across its docs
    pwall = defaultdict(lambda: (0, None, -1))   # permit -> (segs, doc, page)
    psf = defaultdict(lambda: (0, None, -1, 0))
    open(LOG, "w").write(f"scanning {len(ids)} docs for golden (walls+SF)...\n")
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(lambda d: scan_doc(s3, d), ids):
            done += 1
            if res:
                doc_id, (ws, wp), (sr, sp, st) = res
                p = permit.get(doc_id)
                if p:
                    if ws > pwall[p][0]: pwall[p] = (ws, doc_id, wp)
                    if sr > psf[p][0]: psf[p] = (sr, doc_id, sp, st)
            if done % 50 == 0:
                golden = [p for p in pwall if pwall[p][0] >= WALL_SEG_MIN and psf[p][0] >= SF_ROOMS_MIN]
                with lock, open(LOG, "a") as lg:
                    lg.write(f"  {done}/{len(ids)} docs | golden-so-far={len(golden)}\n")

    permits = set(pwall) | set(psf)
    golden = sorted(p for p in permits if pwall[p][0] >= WALL_SEG_MIN and psf[p][0] >= SF_ROOMS_MIN)
    wall_only = sum(1 for p in permits if pwall[p][0] >= WALL_SEG_MIN and psf[p][0] < SF_ROOMS_MIN)
    sf_only = sum(1 for p in permits if psf[p][0] >= SF_ROOMS_MIN and pwall[p][0] < WALL_SEG_MIN)
    with open(LOG, "a") as lg:
        lg.write("\n===== GOLDEN SCAN RESULT =====\n")
        lg.write(f"permits scanned: {len(permits)}\n")
        lg.write(f"wall-centerline permits (>= {WALL_SEG_MIN} segs): {sum(1 for p in permits if pwall[p][0]>=WALL_SEG_MIN)}\n")
        lg.write(f"per-room SF permits (>= {SF_ROOMS_MIN} rooms): {sum(1 for p in permits if psf[p][0]>=SF_ROOMS_MIN)}\n")
        lg.write(f"wall-only: {wall_only}   sf-only: {sf_only}\n")
        lg.write(f"\nGOLDEN (both): {len(golden)}\n")
        for p in golden:
            ws, wd, wp = pwall[p]; sr, sd, sp, st = psf[p]
            lg.write(f"  {p:<16} walls={ws}(doc {wd} p{wp})  sf_rooms={sr}/{st}SF(doc {sd} p{sp})\n")
    print("DONE", len(golden))


if __name__ == "__main__":
    main()
