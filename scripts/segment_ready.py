#!/usr/bin/env python3
"""Segment the READY permits: LAYERED (usable wall-centerline CAD layers on the
floor plan -> layer geometry works NOW) vs FLATTENED (no layers -> needs the ML
wall-model). Reads status board for done READY/READY_NO_FINISH permits, checks
their labeled floor_plan pages for wall-layer segments. Parallel."""
import os, sys, json
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from probe2_sf import ROOT, r2_client, seg_len
from probe8_layer_classes import classify_layer

WALL_MIN = 200
def env():
    e={}
    for line in open(os.path.join(ROOT,".env")):
        line=line.strip()
        if line and not line.startswith("#") and "=" in line: k,v=line.split("=",1);e[k]=v
    return e

def wall_segs(pg):
    pw=pg.rect.width; n=0; lays=set()
    for d in pg.get_drawings():
        if classify_layer(d.get("layer"))!="wall": continue
        for it in d.get("items",[]):
            if it[0]=="l" and seg_len((it[1].x,it[1].y),(it[2].x,it[2].y))>0.008*pw: n+=1; lays.add(d.get("layer"))
    return n, sorted(lays)

def main():
    import psycopg2, psycopg2.extras
    # READY permits from status board (latest status per permit)
    st={}
    for line in open(os.path.join(ROOT,"data","triage","permit_status.jsonl")):
        line=line.strip()
        if line: r=json.loads(line); st[r["permit"]]=r
    ready=[p for p,r in st.items() if r["status"]=="done" and (r.get("tier") or "").startswith("READY")]
    cur=psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    s3=r2_client()
    # floor_plan pages per permit (from labels), pick primary doc
    def scan(pn):
        cur2=psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur2.execute("""SELECT d.onestop_doc_id od, p.page_index pi FROM estimate.document d
          JOIN estimate.page p ON p.document_id=d.id JOIN estimate.page_label pl ON pl.page_id=p.id
          WHERE d.permit_num=%s AND pl.category='floor_plan' ORDER BY d.onestop_doc_id, p.page_index""",(pn,))
        fps=cur2.fetchall()
        if not fps: return pn,0,[],0
        best=0; blays=[]
        from collections import defaultdict
        bydoc=defaultdict(list)
        for r in fps: bydoc[r['od']].append(r['pi'])
        for od,pis in bydoc.items():
            try:
                data=s3.get_object(Bucket="nola-permit-docs",Key=f"docs/{od}.pdf")["Body"].read()
                doc=fitz.open(stream=data,filetype="pdf")
                for pi in pis[:6]:
                    if pi<doc.page_count:
                        n,lays=wall_segs(doc[pi])
                        if n>best: best=n; blays=lays[:2]
                doc.close()
            except Exception: pass
        return pn,best,blays,len(fps)
    results=list(ThreadPoolExecutor(max_workers=8).map(scan, ready))
    layered=[(p,n,l) for p,n,l,_ in results if n>=WALL_MIN]
    flattened=[(p,n) for p,n,l,_ in results if n<WALL_MIN]
    print(f"segmented {len(results)} READY permits:\n")
    print(f"== LAYERED ({len(layered)}) — layer geometry works NOW ==")
    for p,n,l in sorted(layered,key=lambda x:-x[1]): print(f"  {p:<16} wall_segs={n:<6} {l}")
    print(f"\n== FLATTENED ({len(flattened)}) — need ML wall-model (or dims) ==")
    for p,n in sorted(flattened,key=lambda x:-x[1]): print(f"  {p:<16} wall_segs={n}")

if __name__=="__main__": main()
