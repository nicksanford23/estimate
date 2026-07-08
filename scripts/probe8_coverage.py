#!/usr/bin/env python3
"""Across the layered projects (one floor plan per unique permit that HAS named
wall layers), tally how many also carry usable DOOR / FINISH / FURNITURE layers
-- i.e. how much of the RICH signal (not just walls) actually generalizes."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from collections import Counter, defaultdict
from probe2_sf import ROOT, r2_client, download_pdf
from probe8_layer_classes import classify_layer, CLASSES


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def class_counts(pdf, pi):
    doc = fitz.open(pdf)
    if pi >= doc.page_count:
        doc.close(); return None
    pg = doc[pi]
    c = Counter()
    for d in pg.get_drawings():
        n = sum(1 for it in d.get("items", []) if it[0] in ("l", "re", "c"))
        c[classify_layer(d.get("layer"))] += n
    doc.close()
    return c


def main():
    import psycopg2, psycopg2.extras
    cur = psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(
        cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT DISTINCT ON (d.permit_num) d.permit_num, d.onestop_doc_id od, p.page_index pi
        FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
        JOIN estimate.page_label pl ON pl.page_id=p.id
        WHERE pl.category='floor_plan' ORDER BY d.permit_num, p.page_index""")
    rows = cur.fetchall()
    s3 = r2_client()
    layered = []
    print(f"scanning {len(rows)} permits for layered ones with rich signal...\n")
    for r in rows:
        try:
            pdf = download_pdf(s3, r["od"]); cc = class_counts(pdf, r["pi"]); os.remove(pdf)
        except Exception as e:
            continue
        if not cc or cc.get("wall", 0) == 0:
            continue  # only the projects where walls are on named layers
        layered.append((r["permit_num"], cc))
        present = [c for c in ("wall","door","finish","furniture","fixture","structure") if cc.get(c,0) > 20]
        print(f"  {r['permit_num']:<16} walls={cc.get('wall',0):<6} " +
              "  ".join(f"{c}={cc.get(c,0)}" for c in ("door","finish","furniture","fixture","structure")))

    print(f"\n===== {len(layered)} layered projects — how many ALSO carry each class (>20 elems) =====")
    for c in ("door","finish","furniture","fixture","structure"):
        n = sum(1 for _, cc in layered if cc.get(c, 0) > 20)
        print(f"  {n}/{len(layered)}  have usable {c} layers")


if __name__ == "__main__":
    main()
