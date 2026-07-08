#!/usr/bin/env python3
"""The complete end-to-end takeoff for 14-11290 branch — geometry + vision fleet
adjudicated. Three unit types (area by material, base LF, transitions) + honest
per-room confidence + validation vs the 3,190 SF branch GROSS."""
import math

# room: (area_sf, W_ft, L_ft, material, code, base_type, source, conf)
# source: geom=geometry clean, agree=geom+vision agree, vision=vision-corrected,
#         open=geometry blob split by material (est)
R = {
 101:(78, 9.8, 8.5, "Ceramic tile","CT-1","RB-1","vision","low"),
 102:(304,None,None,"Ceramic tile","CT-1","RB-1","open","low"),
 103:(336,None,None,"Carpet","CP-2","RB-1","open","low"),
 104:(164,13.9,11.8,"Carpet","CP-1","RB-1","agree","med"),
 105:(286,None,None,"Carpet","CP-1","WB-1","open","low"),
 106:(119,10.7,11.2,"Carpet","CP-1","RB-1","agree","high"),
 107:(122,10.7,11.2,"Carpet","CP-1","RB-1","agree","med"),
 108:(216,11.5,18.8,"Carpet","CP-1","WB-1","agree","med"),
 109:(118,10.0,11.5,"Carpet","CP-1","RB-1","geom","low"),
 110:(386,None,None,"Carpet","CP-2","RB-1","open","low"),
 111:(228,None,None,"Carpet","CP-2","RB-1","open","low"),
 112:(73, 10.0,7.6,"Ceramic tile","CT-1","RB-1","agree","med"),
 113:(112,11.5,10.0,"Resilient","RF-1","RB-1","agree","med"),
 114:(45, 5.0,9.0,"Carpet","CP-2","RB-1","geom","low"),
 115:(52, 6.5,8.0,"Resilient","RF-1","RB-1","agree","med"),
 116:(54, 6.5,8.3,"Resilient","RF-1","RB-1","agree","med"),
 117:(38, 7.7,5.0,"Carpet","CP-2","RB-1","agree","high"),
 118:(24, 5.3,4.5,"Resilient","RF-1","RB-1","agree","med"),
}
NAME = {101:"Vestibule",102:"Lobby",103:"Tellers",104:"Workroom",105:"Self-Service",
 106:"Office",107:"Office",108:"Conference",109:"Office",110:"Copy/Fax",111:"Mortgage",
 112:"Vestibule",113:"Break Room",114:"Corridor",115:"Men",116:"Women",117:"Elect/Data",118:"Jan"}
BRANCH_GROSS = 3190
UNIT = {"Carpet":"SY","Ceramic tile":"SF","Resilient":"SF"}

def perim(rn):
    a,W,L,*_ = R[rn]
    if W and L: return 2*(W+L)
    return 4.4*math.sqrt(a)   # est for open/blob rooms

print("="*78)
print("  FLOORING TAKEOFF — Liberty Bank Branch  (permit 14-11290-NEWC, sheet A-1.1)")
print("  method: CAD-layer geometry + Claude vision dimension read, adjudicated")
print("="*78)
print(f"\n{'rm':>4} {'name':<13}{'material':<14}{'code':<6}{'area SF':>8}{'base LF':>8}  src/conf")
tot_area=0; base_by={}; mat_sf={}
for rn in sorted(R):
    a,W,L,mat,code,bt,src,conf = R[rn]
    p = perim(rn)-3  # less one door
    tot_area+=a; mat_sf[mat]=mat_sf.get(mat,0)+a
    base_by[bt]=base_by.get(bt,0)+p
    print(f"{rn:>4} {NAME[rn]:<13}{mat:<14}{code:<6}{a:>8}{p:>8.0f}  {src}/{conf}")

print("\n--- AREA BY MATERIAL ---")
for mat,sf in sorted(mat_sf.items(),key=lambda x:-x[1]):
    extra = f"   = {math.ceil(sf/9)} SY (order unit)" if UNIT[mat]=="SY" else ""
    print(f"  {mat:<14}{sf:>6} SF{extra}")

print("\n--- BASE (LINEAR) ---")
for bt,lf in sorted(base_by.items()):
    label = "Rubber cove RB-1" if bt=="RB-1" else "Wood base WB-1"
    print(f"  {label:<18}{lf:>6.0f} LF")
print(f"  {'TOTAL base':<18}{sum(base_by.values()):>6.0f} LF  (gross perimeter less ~1 door/room)")

print("\n--- TRANSITIONS (at material changes) ---")
tile=[r for r in R if R[r][3]=='Ceramic tile']; resil=[r for r in R if R[r][3]=='Resilient']
print(f"  tile<->carpet + resilient<->carpet thresholds: ~{len(tile)+len(resil)} locations, strips TS-1/TS-2")

print("\n--- TOTAL & VALIDATION ---")
print(f"  total floor area (NET):        {tot_area:>6} SF")
print(f"  branch Business area (GROSS):  {BRANCH_GROSS:>6} SF   (sheet A-0.1)")
print(f"  delta: {tot_area-BRANCH_GROSS:+.0f} SF  ({100*(tot_area-BRANCH_GROSS)/BRANCH_GROSS:+.0f}%)  <- net-vs-gross, ~expected")
n_low=sum(1 for r in R if R[r][7]=='low')
print(f"\n  confidence: {sum(1 for r in R if R[r][7]=='high')} high, "
      f"{sum(1 for r in R if R[r][7]=='med')} med, {n_low} low "
      f"(open areas + fragment-corrected rooms are the low ones)")
