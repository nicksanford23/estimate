#!/usr/bin/env python3
"""Hunt for per-room SF ground truth. Scan labeled schedule / life-safety / finish
pages across all downloaded permits; extract '<number> SF'-type area tokens and
room-schedule signals. Pages dense with per-room areas = candidate ground truth to
validate our geometry against."""
import os, re, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from probe2_sf import ROOT, r2_client

BUCKET = "nola-permit-docs"
AREA_RE = re.compile(r"(\d{2,4}(?:\.\d)?)\s*(?:S\.?\s?F\.?|SQ\.?\s*FT|SQUARE\s*FEET)\b", re.I)
SCHED_RE = re.compile(r"ROOM\s+FINISH\s+SCHEDULE|ROOM\s+SCHEDULE|FINISH\s+SCHEDULE|AREA\s+(?:SCHEDULE|TABULATION|ANALYSIS)|OCCUPAN", re.I)
TARGET = ("finish_schedule", "schedule_other", "life_safety", "finish_plan", "cover_index")


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def main():
    import psycopg2, psycopg2.extras
    cur = psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"""SELECT d.permit_num, d.onestop_doc_id od, p.page_index pi, pl.category
        FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
        JOIN estimate.page_label pl ON pl.page_id=p.id
        WHERE pl.category IN {TARGET} ORDER BY d.onestop_doc_id, p.page_index""")
    rows = cur.fetchall()
    bydoc = defaultdict(list)
    for r in rows:
        bydoc[r["od"]].append((r["pi"], r["category"], r["permit_num"]))
    print(f"scanning {len(rows)} schedule/life-safety pages across {len(bydoc)} docs...\n")

    s3 = r2_client()
    hits = []
    for od, pages in bydoc.items():
        try:
            data = s3.get_object(Bucket=BUCKET, Key=f"docs/{od}.pdf")["Body"].read()
            if data[:5] != b"%PDF-": continue
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception:
            continue
        for pi, cat, permit in pages:
            if pi >= doc.page_count: continue
            t = doc[pi].get_text()
            areas = AREA_RE.findall(t)
            sched = bool(SCHED_RE.search(t))
            # count DISTINCT plausible room areas (10-5000 SF)
            vals = [float(a) for a in areas if 10 <= float(a) <= 5000]
            if len(vals) >= 4 or (sched and len(vals) >= 2):
                hits.append((len(vals), sched, permit, pi, cat, sorted(set(round(v) for v in vals))[:12]))
        doc.close()

    hits.sort(reverse=True)
    print(f"{'#SF':>4} sched permit            page cat               sample areas")
    for n, sched, permit, pi, cat, sample in hits[:30]:
        print(f"{n:>4}  {'Y' if sched else '.'}   {permit:<16} p{pi:<3} {cat:<16} {sample}")
    print(f"\ntotal candidate pages (>=4 areas or schedule+2): {len(hits)}")
    print(f"unique permits with a candidate: {len(set(h[2] for h in hits))}")


if __name__ == "__main__":
    main()
