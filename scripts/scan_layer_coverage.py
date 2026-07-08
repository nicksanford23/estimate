#!/usr/bin/env python3
"""Measure the buckets: of our labeled floor plans (one page per unique permit),
how many carry usable WALL layers vs vector-without-layers vs scanned. Tells us
how much of the SF problem the 'layer trick' solves for free.
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from probe2_sf import ROOT, r2_client, download_pdf  # noqa: E402

WALL_RE = re.compile(r"WALL|CMU|STUD|GYP|STUCCO", re.IGNORECASE)


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def classify_page(pdf, pi):
    doc = fitz.open(pdf)
    if pi >= doc.page_count:
        doc.close(); return "page_missing", 0, 0
    page = doc[pi]
    drs = page.get_drawings()
    n_seg = sum(1 for d in drs for it in d.get("items", []) if it[0] == "l")
    wall_seg = 0
    any_layer = False
    for d in drs:
        lay = d.get("layer")
        if lay is not None:
            any_layer = True
        if lay and WALL_RE.search(lay):
            wall_seg += sum(1 for it in d.get("items", []) if it[0] == "l")
    doc.close()
    if n_seg < 50:
        return "scanned_or_flat", n_seg, wall_seg
    if not any_layer:
        return "vector_no_layers", n_seg, wall_seg
    if wall_seg > 0:
        return "layered_with_walls", n_seg, wall_seg
    return "layered_no_wall_layer", n_seg, wall_seg


def main():
    import psycopg2, psycopg2.extras
    cur = psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(
        cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT DISTINCT ON (d.permit_num) d.permit_num, d.onestop_doc_id od, p.page_index pi
        FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
        JOIN estimate.page_label pl ON pl.page_id=p.id
        WHERE pl.category='floor_plan'
        ORDER BY d.permit_num, p.page_index""")
    rows = cur.fetchall()
    print(f"checking one floor plan from each of {len(rows)} unique permits...\n")

    s3 = r2_client()
    tally = Counter()
    for i, r in enumerate(rows, 1):
        try:
            pdf = download_pdf(s3, r["od"])
            cls, nseg, wseg = classify_page(pdf, r["pi"])
            os.remove(pdf)
        except Exception as e:  # noqa: BLE001
            cls, nseg, wseg = "error", 0, 0
            print(f"  [{i}/{len(rows)}] {r['permit_num']:<16} ERROR {str(e)[:40]}")
            continue
        tally[cls] += 1
        print(f"  [{i}/{len(rows)}] {r['permit_num']:<16} {cls:<22} segs={nseg:<6} wall={wseg}")

    print("\n===== BUCKET TALLY (per unique permit) =====")
    total = sum(tally.values())
    for k, n in tally.most_common():
        print(f"  {n:>3}/{total}  ({100*n/total:.0f}%)  {k}")


if __name__ == "__main__":
    main()
