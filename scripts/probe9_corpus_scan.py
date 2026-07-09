#!/usr/bin/env python3
"""FULL-CORPUS layer scan. For every downloaded PDF in R2, read its layer
directory (get_ocgs) from an in-memory stream -- no temp files, no render -- and
classify the layer NAMES against the estimator ontology. Answers: how many of
the ~2,329 downloaded projects carry usable WALL layers (the free-training-data
well), plus door/finish/furniture coverage. Streams in parallel."""
import os, re, sys, threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from probe2_sf import ROOT, r2_client
from probe8_layer_classes import classify_layer

BUCKET = "nola-permit-docs"
LOG = os.environ.get("SCANLOG", "/tmp/corpus_scan.log")
lock = threading.Lock()


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def list_downloaded(s3):
    ids = []
    tok = None
    while True:
        kw = dict(Bucket=BUCKET, Prefix="docs/")
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            m = re.match(r"docs/(\d+)\.pdf$", o["Key"])
            if m:
                ids.append(int(m.group(1)))
        if r.get("IsTruncated"):
            tok = r["NextContinuationToken"]
        else:
            break
    return ids


def scan_one(s3, doc_id):
    try:
        data = s3.get_object(Bucket=BUCKET, Key=f"docs/{doc_id}.pdf")["Body"].read()
        if data[:5] != b"%PDF-":
            return doc_id, None
        doc = fitz.open(stream=data, filetype="pdf")
        classes = Counter()
        for v in doc.get_ocgs().values():
            classes[classify_layer(v.get("name"))] += 1
        doc.close()
        return doc_id, classes
    except Exception:
        return doc_id, None


def main():
    s3 = r2_client()
    ids = list_downloaded(s3)
    # doc_id -> permit
    import psycopg2, psycopg2.extras
    cur = psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(
        cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT onestop_doc_id od, permit_num FROM estimate.document")
    permit = {r["od"]: r["permit_num"] for r in cur.fetchall()}

    open(LOG, "w").write(f"downloaded PDFs in R2: {len(ids)}\n")
    done = Counter()
    wall_docs = []
    rich = Counter()
    n = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(scan_one, s3, d) for d in ids]
        for f in as_completed(futs):
            doc_id, classes = f.result()
            n += 1
            if classes is None:
                done["unreadable"] += 1
            else:
                has_wall = classes.get("wall", 0) > 0
                done["wall" if has_wall else "no_wall"] += 1
                if has_wall:
                    wall_docs.append(doc_id)
                    for c in ("door", "finish", "furniture", "fixture"):
                        if classes.get(c, 0) > 0:
                            rich[c] += 1
            if n % 100 == 0:
                permits_wall = {permit.get(d) for d in wall_docs} - {None}
                with lock, open(LOG, "a") as lg:
                    lg.write(f"[{n}/{len(ids)}] wall_docs={done['wall']} "
                             f"no_wall={done['no_wall']} unreadable={done['unreadable']} "
                             f"| unique wall-permits so far={len(permits_wall)}\n")

    permits_all = {permit.get(d) for d in ids} - {None}
    permits_wall = {permit.get(d) for d in wall_docs} - {None}
    with open(LOG, "a") as lg:
        lg.write("\n===== FULL CORPUS RESULT =====\n")
        lg.write(f"downloaded docs: {len(ids)}  (unique permits: {len(permits_all)})\n")
        lg.write(f"docs WITH named wall layers: {done['wall']}  "
                 f"({100*done['wall']/max(1,len(ids)):.0f}%)\n")
        lg.write(f"UNIQUE PERMITS with a wall-layered doc: {len(permits_wall)}  "
                 f"({100*len(permits_wall)/max(1,len(permits_all)):.0f}% of downloaded permits)\n")
        lg.write(f"unreadable: {done['unreadable']}\n\n")
        lg.write("of the wall-layered docs, how many also carry:\n")
        for c in ("door", "finish", "furniture", "fixture"):
            lg.write(f"  {c}: {rich[c]}/{done['wall']} ({100*rich[c]/max(1,done['wall']):.0f}%)\n")
    print("DONE")


if __name__ == "__main__":
    main()
