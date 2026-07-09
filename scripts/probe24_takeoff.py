#!/usr/bin/env python3
"""Full layer-geometry takeoff on 26-10321-RNVN (multi-floor office reno, EXIST/NEW
WALL layers). Pick the richest floor-plan page, run the layer pipeline, per-room SF
via room-number anchors, per-room product-action state, overlay. Second building
after the bank."""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point
from probe2_sf import (ROOT, r2_client, download_pdf, snap_and_close, polygonize_rooms,
    find_scale, SCALE_RE, seg_len)
from probe7_layer_walls import extract_wall_layer_segments
import re
DOC = 9058456
OUT = os.path.join(ROOT, "data", "probe24"); os.makedirs(OUT, exist_ok=True)

def env():
    e={}
    for line in open(os.path.join(ROOT,".env")):
        line=line.strip()
        if line and not line.startswith("#") and "=" in line: k,v=line.split("=",1);e[k]=v
    return e
def font(sz):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(p,sz) if os.path.exists(p) else ImageFont.load_default()

def main():
    import psycopg2,psycopg2.extras
    cur=psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT p.page_index pi, pl.sheet_title FROM estimate.document d
      JOIN estimate.page p ON p.document_id=d.id JOIN estimate.page_label pl ON pl.page_id=p.id
      WHERE d.permit_num='26-10321-RNVN' AND pl.category='floor_plan' AND pl.source='claude-code'
      ORDER BY p.page_index""")
    fps=cur.fetchall()
    s3=r2_client(); pdf=download_pdf(s3,DOC); doc=fitz.open(pdf)
    # pick floor plan page with most wall-layer segments
    best=None
    for r in fps:
        pi=r['pi']; pg=doc[pi]; pw=pg.rect.width
        segs,_,_,_=extract_wall_layer_segments(pdf,pi)
        n=sum(1 for p0,p1,w in segs if seg_len(p0,p1)>0.008*pw)
        print(f"  floor p{pi} ({r['sheet_title']}): {n} wall segs")
        if best is None or n>best[1]: best=(pi,n,r['sheet_title'])
    PAGE=best[0]
    print(f"\n>>> takeoff on p{PAGE} ({best[2]}), {best[1]} wall segs\n")
    fpp,scale_txt=find_scale(DOC,PAGE)
    pg=doc[PAGE]; pw,ph=pg.rect.width,pg.rect.height
    if fpp is None:
        m=SCALE_RE.findall(pg.get_text()); fpp=(int(m[0][1])/int(m[0][0]))/72.0 if m else None
    if fpp is None:
        # VISION-READ scale off the trimmed page: A2.4 title block says
        # "SCALE: 1/8" = 1'-0"". On a single trimmed sheet we read the scale
        # by looking, not by regex-scraping messy vector text. 1/N" = 1'-0" => fpp = N/72.
        N=int(os.environ.get("SCALE_DENOM","8"))
        fpp=N/72.0; scale_txt=f'1/{N}"=1\'-0" (vision)'
    segs,_,_,used=extract_wall_layer_segments(pdf,PAGE)
    walls=[(p0,p1,w) for p0,p1,w in segs if seg_len(p0,p1)>0.008*pw]
    lines,_=snap_and_close([(p0,p1,seg_len(p0,p1),w) for p0,p1,w in walls],[],pw,feet_per_pt=fpp)
    polys,_=polygonize_rooms(lines,pw,ph,15,8000,fpp)
    # room-number anchors (digits)
    anchors={}
    for w in pg.get_text("words"):
        t=w[4].strip()
        if re.match(r'^\d{2,4}$',t) and t not in anchors:
            anchors[t]=((w[0]+w[2])/2,(w[1]+w[3])/2)
    room_poly,poly_rooms={},defaultdict(list)
    for rn,(x,y) in anchors.items():
        for i,pg2 in enumerate(polys):
            if pg2.contains(Point(x,y)): room_poly[rn]=i; poly_rooms[i].append(rn); break
    # per-room
    rooms=[]
    for rn,i in sorted(room_poly.items()):
        a=polys[i].area*fpp**2
        st="merged" if len(poly_rooms[i])>1 else ("fragment" if a<25 else "closed")
        rooms.append((rn,round(a),st))
    closed=[r for r in rooms if r[2]=="closed"]
    print(f"scale={scale_txt} fpp={fpp:.4f} layers={used}")
    print(f"polygons={len(polys)} anchors={len(anchors)} matched={len(room_poly)}")
    print(f"\n{'room':>6}{'SF':>7}  state")
    for rn,a,st in rooms: print(f"{rn:>6}{a:>7}  {st}")
    tot=sum(a for rn,a,st in closed)
    print(f"\nclosed rooms: {len(closed)}  merged: {sum(1 for r in rooms if r[2]=='merged')}  "
          f"fragment: {sum(1 for r in rooms if r[2]=='fragment')}")
    print(f"closed-room SF total: {tot}")
    # overlay
    Z=3.0
    pm=pg.get_pixmap(matrix=fitz.Matrix(Z,Z),alpha=False)
    im=Image.frombytes("RGB",(pm.width,pm.height),pm.samples).convert("RGBA")
    dd=ImageDraw.Draw(im,"RGBA"); fnt=font(int(6*Z))
    for i,mates in poly_rooms.items():
        col=(0,170,90,90) if len(mates)==1 else (220,60,50,90)
        pts=[(x*Z,y*Z) for x,y in polys[i].exterior.coords]
        dd.polygon(pts,fill=col,outline=(0,100,60,255))
    for rn,(x,y) in anchors.items():
        if rn in room_poly:
            a=next(z[1] for z in rooms if z[0]==rn)
            dd.text((x*Z,y*Z),f"{rn}:{a}",fill=(10,20,120,255),font=fnt)
    im.convert("RGB").save(os.path.join(OUT,f"takeoff_p{PAGE}.jpg"),"JPEG",quality=84)
    doc.close(); os.remove(pdf)
    print(f"overlay -> data/probe24/takeoff_p{PAGE}.jpg")

if __name__=="__main__": main()
