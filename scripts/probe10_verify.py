#!/usr/bin/env python3
"""Verification pass: turn '44 wall-NAME matches' into a CONFIRMED count. For one
wall-layered doc per permit, render every page's vector geometry and count REAL
wall segments (on wall-classed layers, length-filtered) on the best page. A permit
is confirmed only if walls are actually DRAWN, not just named."""
import os, sys, threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from probe2_sf import ROOT, r2_client, seg_len
from probe8_layer_classes import classify_layer

BUCKET = "nola-permit-docs"
LOG = os.environ.get("VLOG", "/tmp/verify.log")
lock = threading.Lock()


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def fetch(s3, doc_id):
    return s3.get_object(Bucket=BUCKET, Key=f"docs/{doc_id}.pdf")["Body"].read()


def has_wall_name(s3, doc_id):
    """Return True if the doc has a wall-named layer. Do NOT retain bytes (OOM)."""
    try:
        data = fetch(s3, doc_id)
        if data[:5] != b"%PDF-":
            return False
        doc = fitz.open(stream=data, filetype="pdf")
        nwall = sum(1 for v in doc.get_ocgs().values() if classify_layer(v.get("name")) == "wall")
        doc.close()
        return nwall > 0
    except Exception:
        return False


def best_wall_page(data):
    """Return (max wall-seg count on any page, page_index, layers)."""
    doc = fitz.open(stream=data, filetype="pdf")
    best = (0, -1, [])
    for pi in range(doc.page_count):
        pg = doc[pi]
        pw = pg.rect.width
        n = 0; lays = set()
        for d in pg.get_drawings():
            if classify_layer(d.get("layer")) != "wall":
                continue
            for it in d.get("items", []):
                if it[0] == "l" and seg_len((it[1].x, it[1].y), (it[2].x, it[2].y)) > 0.008 * pw:
                    n += 1; lays.add(d.get("layer"))
        if n > best[0]:
            best = (n, pi, sorted(lays))
    doc.close()
    return best


def main():
    s3 = r2_client()
    # downloaded ids + permit map
    ids = []
    tok = None
    import re
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

    open(LOG, "w").write(f"finding wall-named docs among {len(ids)} downloaded...\n")
    # one wall-named doc per permit (store only the doc_id, never the bytes)
    per_permit = {}
    def check(d):
        return d, has_wall_name(s3, d)
    n = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for d, ok in ex.map(check, ids):
            n += 1
            if ok:
                p = permit.get(d)
                if p and p not in per_permit:
                    per_permit[p] = d
            if n % 300 == 0:
                with lock, open(LOG, "a") as lg:
                    lg.write(f"  scanned {n}/{len(ids)}, wall-permits found={len(per_permit)}\n")
    with open(LOG, "a") as lg:
        lg.write(f"\nwall-NAME permits: {len(per_permit)}. Now confirming real geometry...\n\n")

    # confirm geometry per permit (re-stream by doc_id here — bytes not retained)
    results = []
    def confirm(item):
        p, d = item
        try:
            nseg, pi, lays = best_wall_page(fetch(s3, d))
        except Exception:
            nseg, pi, lays = -1, -1, []
        return p, d, nseg, pi, lays
    with ThreadPoolExecutor(max_workers=8) as ex:
        for p, d, nseg, pi, lays in ex.map(confirm, list(per_permit.items())):
            results.append((p, d, nseg, pi, lays))
            with lock, open(LOG, "a") as lg:
                tag = "CONFIRMED" if nseg >= 100 else ("weak" if nseg >= 20 else "trace/none")
                lg.write(f"  {p:<16} doc={d:<9} wall_segs={nseg:<6} p{pi:<3} {tag}  {lays[:3]}\n")

    conf = sum(1 for r in results if r[2] >= 100)
    weak = sum(1 for r in results if 20 <= r[2] < 100)
    none = sum(1 for r in results if r[2] < 20)
    with open(LOG, "a") as lg:
        lg.write("\n===== VERIFIED RESULT =====\n")
        lg.write(f"wall-NAME permits checked: {len(results)}\n")
        lg.write(f"  CONFIRMED (>=100 real wall segs): {conf}\n")
        lg.write(f"  weak (20-99):                     {weak}\n")
        lg.write(f"  trace/none (<20):                 {none}\n")
    print("DONE")


if __name__ == "__main__":
    main()
