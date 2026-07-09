#!/usr/bin/env python3
"""Harvest LAYERED plans — the free wall-label training seed for Model 2.

Scans every document we have (ingested set, via R2) for pages that carry NAMED
wall layers with real wall linework. Those pages give wall labels with zero human
effort. Output: data/triage/layered_plans.csv (permit, doc, page, wall_segs,
layers) — the seed to train the wall/room model on. Resumable; re-run as more
plans download.
"""
import os, sys, csv, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from probe2_sf import ROOT, r2_client, download_pdf, seg_len
from probe7_layer_walls import extract_wall_layer_segments

OUT = os.path.join(ROOT, "data", "triage", "layered_plans.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
FIELDS = ["permit", "doc_id", "page", "wall_segs", "layers"]
WALL_MIN = 120           # a page needs at least this many long wall-layer segs
_lock = threading.Lock()


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
    c.execute("SELECT DISTINCT onestop_doc_id od, permit_num pn FROM estimate.document ORDER BY onestop_doc_id")
    return c.fetchall()


def done_docs():
    d = set()
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT)):
            d.add(str(r["doc_id"]))
    # also a sidecar of scanned-but-empty docs so we don't rescan them
    seen = OUT + ".seen"
    if os.path.exists(seen):
        d |= set(open(seen).read().split())
    return d


def mark_seen(doc_id):
    with _lock:
        open(OUT + ".seen", "a").write(f"{doc_id}\n")


def scan(t):
    od, pn = str(t["od"]), t["pn"]
    s3 = r2_client()
    try:
        pdf = download_pdf(s3, od)
    except Exception:
        return []
    rows = []
    try:
        doc = fitz.open(pdf)
        for pi in range(min(doc.page_count, 60)):
            try:
                pg = doc[pi]; pw = pg.rect.width
                segs, _, _, used = extract_wall_layer_segments(pdf, pi)
                n = sum(1 for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw)
                if used and n >= WALL_MIN:
                    rows.append(dict(permit=pn, doc_id=od, page=pi, wall_segs=n,
                                     layers="|".join(used[:5])))
            except Exception:
                continue
        doc.close()
    finally:
        try: os.remove(pdf)
        except OSError: pass
    return rows


def main():
    done = done_docs()
    ts = [t for t in targets() if str(t["od"]) not in done]
    print(f"scanning {len(ts)} docs for named wall layers (resumable)", flush=True)
    write_header = not os.path.exists(OUT) or os.path.getsize(OUT) == 0
    f = open(OUT, "a", newline=""); w = csv.DictWriter(f, fieldnames=FIELDS)
    if write_header: w.writeheader(); f.flush()
    n_layered = n_docs = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futmap = {ex.submit(scan, t): t for t in ts}
        for fut in as_completed(futmap):
            t = futmap[fut]
            rows = fut.result(); n_docs += 1
            if rows:
                with _lock:
                    for r in rows: w.writerow(r)
                    f.flush()
                n_layered += 1
            else:
                mark_seen(t["od"])   # scanned, no wall layers — don't rescan
            if n_docs % 25 == 0:
                print(f"[{n_docs}/{len(ts)}] layered docs so far: {n_layered}", flush=True)
    f.close()
    print(f"DONE: {n_layered} layered docs of {n_docs} scanned -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
