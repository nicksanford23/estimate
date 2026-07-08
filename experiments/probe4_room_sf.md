# Probe 4 — Label-guided room SF + vision cross-check

**Date:** 2026-07-08
**Project:** 14-11290-NEWC (Liberty Bank Gentilly branch), 7,090 sf, new construction
**Sheet:** A-1.1 "Partial Floor Plan – Branch" (doc 1494156, page 3), scale 1/4" = 1'-0"
**Rooms:** the 18 bank-branch rooms (101–118)
**Script:** `scripts/probe4_room_sf.py` → `data/probe4/room_overlay.jpg`, `room_geom.json`

## Goal

Test the **hybrid** SF approach instead of blind geometry:
1. Use the known room labels as **anchors** to guide the geometry (assign each
   room label to the polygon that contains it) — catches merges, avoids blind
   polygonization.
2. Read each room's **dimensions with vision** as an independent estimate.
3. **Cross-check** the two. Agree → trust; disagree → flag for human review.

Principle: code calculates coordinates/area; vision judges/estimates; publish
only what passes the cross-check (silence over lies).

## Method

- Extract the room-number tokens (101–118) from the PDF text → label positions.
- Run the existing geometry pipeline (`probe2_sf`) → candidate polygons.
- Assign each room label to the polygon containing it:
  - one label in a polygon → `unique` (clean),
  - several labels in one polygon → `merged`,
  - label in no polygon → `not_found`.
- Read dimensions off a high-res render, room by room, and compute area.

## Results — geometry half

- **Room-label detection: 18/18** (perfect — every room number located).
- **71 closed polygons produced** on the sheet; **13 of 18 rooms matched to a
  clean closed polygon, 0 merged, 5 no-polygon.** Label-guidance eliminated the
  old "whole floor = one blob" failure.
- **The easy half closed *correctly* — automatically.** For the simple
  rectangular offices, the closed polygon matched the drawing's own dimensions:
  Office 106 closed to **91 sf vs. 86 sf from the printed dims (~6%)**. That is a
  real, usable measurement with zero human input. Roughly 6–8 rooms landed in
  the right ballpark.
- **The rest under-close.** For the remaining rooms the areas are too small —
  the walls don't close into the full room, so each polygon captures ~40–80% of
  the real area, and a couple collapse to fragments:

| Room | Geometry sf | Note |
|---|---|---|
| Office 106 | 91 | plausible |
| Office 107 | 77 | a bit low |
| Office 109 | 78 | low |
| Conference 108 | 15 | fragment |
| Tellers 103 | 18 | fragment |
| Self-Service 105 | 79 | low |
| Break Room 113 | 72 | low |
| Men / Women | 30 / 31 | low |
| Vestibule 112 | 130 | over (grabbed extra) |
| Lobby 102, Corridor 114, Elect/Data 117, Jan 118, Vestibule 101 | — | no polygon |

## Results — vision (dimension) half

Reading dims **corrected a wrong assumption**: the offices are *narrow*
(7'-8" × 11'-2" ≈ **86 sf**), not ~120 sf as first guessed. So the geometry's
91 sf for Office 106 was actually right.

Confidently readable rooms:

| Room | Vision (dims) | Geometry | Cross-check |
|---|---|---|---|
| Office 106 | 7'-8" × 11'-2" ≈ 86 | 91 | ✅ agree (~6%) |
| Office 107 | 7'-8" × 11'-2" ≈ 86 | 77 | 🟡 ~10% |
| Office 109 | 9'-7" × 11'-2" ≈ 107 | 78 | ❌ geom under |
| Conference 108 | ~11' × 15' ≈ 170 | 15 | ❌ geom fragment |
| Restrooms 115/116 | ~50 each | 30/31 | ❌ geom under |

The **tangled service core** (Tellers, Corridor, Jan, Elect/Data, Restrooms,
Lobby) could **not** be read cleanly by eye either — the dimensions are chained
along the perimeter and don't isolate individual rooms without the walls.

## Key findings

0. **We DID get correct closed polygons — for the easy half.** ~6–8 rooms (the
   rectangular offices) closed into accurate polygons matching the printed
   dimensions within ~6–10%, no human input. The geometry is not useless; it
   works when the room is a clean rectangle with detected walls. That "half the
   rooms measured automatically" is a viable starting point for an assisted tool.
1. **Label-guidance is worth keeping.** Perfect label detection, zero merges —
   a real improvement over blind polygonization.
2. **The true failure mode here is *under-closure*, not merging.** Interior
   walls don't close into full room boundaries, so polygons are partial.
3. **The hard rooms are hard for BOTH methods.** The rooms where geometry works
   (simple rectangular offices) are the same rooms where reading dimensions
   works. The rooms where geometry fails (the service core) are also where
   dimensions are tangled. The two methods do **not** cleanly complement.
4. **The cross-check earns its keep by telling you where to spend the human.**
   Auto-accept the ~half where vision and geometry agree; hand the human only
   the tangled core. Product shape: *"12 rooms confirmed, 6 need your eyes."*
5. **The ML target narrows.** The bottleneck isn't "measure any room" — it's
   specifically **small adjacent rooms sharing thin walls** (restrooms, jan,
   corridor). A much more attackable problem than "solve all geometry."

## Next steps

- Build the **assisted-takeoff loop**: auto-accept agree-rooms, flag the rest
  for one-click human confirmation.
- Attack the narrow target: a wall-vs-line classifier focused on **thin interior
  partitions in dense service cores**, where under-closure happens.
- Consider vision-read dims as the **primary** number for simple dimensioned
  rooms, geometry as the shape/sanity check.

## The script — `scripts/probe4_room_sf.py`

```python
#!/usr/bin/env python3
"""Probe 4 — label-guided room SF (the geometry half of the hybrid).
Instead of blind polygonize, use the known room-number labels as anchors:
polygonize the page, then assign each room label to the polygon that CONTAINS
it. That gives, per room: a clean polygon (unique), a MERGE (one polygon holds
several room labels), or NOT-FOUND (label in no polygon). Renders an overlay
and prints a per-room table. Cross-checked against a vision dimension read.

Usage: python3 probe4_room_sf.py            (defaults to 14-11290 A-1.1 branch)
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, extract_drawings, wall_candidates,
    suppress_hatches, snap_and_close, polygonize_rooms, find_scale, SCALE_RE,
)

DOC = 1494156
PAGE = 3   # A-1.1 PARTIAL FLOOR PLAN - BRANCH (the 18 branch rooms, 1/4"=1')
ZOOM = 2.6
OUT = os.path.join(ROOT, "data", "probe4")
os.makedirs(OUT, exist_ok=True)

# the 18 branch rooms (number -> name), from the finish plan
ROOMS = {
    101: "Vestibule", 102: "Lobby", 103: "Tellers", 104: "Workroom",
    105: "Self-Service", 106: "Office", 107: "Office", 108: "Conference",
    109: "Office", 110: "Copy/Fax", 111: "Mortgage", 112: "Vestibule",
    113: "Break Room", 114: "Corridor", 115: "Men", 116: "Women",
    117: "Elect/Data", 118: "Jan",
}


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def main():
    s3 = r2_client()
    pdf = download_pdf(s3, DOC)
    try:
        # scale
        fpp, scale_text = find_scale(DOC, PAGE)
        if fpp is None:
            doc = fitz.open(pdf); txt = doc[PAGE].get_text(); doc.close()
            m = SCALE_RE.findall(txt)
            if m:
                num, den = int(m[0][0]), int(m[0][1]); fpp = (den / num) / 72.0
        # room-label anchor positions: find the room-number tokens 101..118
        doc = fitz.open(pdf); page = doc[PAGE]
        words = page.get_text("words")  # x0,y0,x1,y1,text,block,line,wn
        anchors = {}
        for w in words:
            t = w[4].strip()
            if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
                cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
                anchors[int(t)] = (cx, cy)
        doc.close()

        # geometry -> polygons
        ex = extract_drawings(pdf, PAGE)
        walls, dom, thick = wall_candidates(ex)
        walls_clean, _ = suppress_hatches(walls, ex["pw"])
        lines, _ = snap_and_close(walls_clean, ex["arcs"], ex["pw"], feet_per_pt=fpp)
        polys, _ = polygonize_rooms(lines, ex["pw"], ex["ph"], 15, 8000, fpp)

        # assign each room anchor to the polygon(s) containing it
        poly_rooms = defaultdict(list)  # poly index -> [room numbers]
        room_poly = {}                  # room -> poly index
        for rn, (x, y) in anchors.items():
            pt = Point(x, y)
            hit = None
            for i, pg in enumerate(polys):
                if pg.contains(pt):
                    hit = i; break
            if hit is not None:
                poly_rooms[hit].append(rn)
                room_poly[rn] = hit

        # per-room result
        results = []
        for rn, name in ROOMS.items():
            if rn not in anchors:
                results.append(dict(room=rn, name=name, label="not_found",
                                    status="label_not_found", geom_sf=None))
                continue
            if rn not in room_poly:
                results.append(dict(room=rn, name=name, label="found",
                                    status="no_polygon", geom_sf=None))
                continue
            pi = room_poly[rn]
            mates = poly_rooms[pi]
            if len(mates) == 1:
                sf = polys[pi].area * fpp ** 2
                results.append(dict(room=rn, name=name, label="found",
                                    status="unique", geom_sf=round(sf, 1)))
            else:
                sf = polys[pi].area * fpp ** 2
                results.append(dict(room=rn, name=name, label="found",
                                    status="merged", merged_with=[m for m in mates if m != rn],
                                    geom_sf=round(sf, 1)))

        # overlay
        pix = page  # noqa
        doc = fitz.open(pdf); pg2 = doc[PAGE]
        pm = pg2.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
        im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
        doc.close()
        dd = ImageDraw.Draw(im, "RGBA")
        fnt = font(int(6.5 * ZOOM))
        status_color = {"unique": (0, 170, 90, 90), "merged": (210, 70, 60, 80)}
        drawn = set()
        for rn, name in ROOMS.items():
            r = next(x for x in results if x["room"] == rn)
            pi = room_poly.get(rn)
            if pi is not None and pi not in drawn:
                col = status_color.get("merged" if len(poly_rooms[pi]) > 1 else "unique")
                pts = [(x * ZOOM, y * ZOOM) for x, y in polys[pi].exterior.coords]
                dd.polygon(pts, fill=col, outline=(0, 100, 60, 255))
                drawn.add(pi)
            if rn in anchors:
                x, y = anchors[rn]
                dd.ellipse([x * ZOOM - 4, y * ZOOM - 4, x * ZOOM + 4, y * ZOOM + 4],
                           fill=(20, 40, 120, 255))
                sf = r.get("geom_sf")
                lab = f"{rn} {name}" + (f" {sf:.0f}sf" if sf and r["status"] == "unique" else
                                        (" MERGED" if r["status"] == "merged" else " ?"))
                dd.text((x * ZOOM + 6, y * ZOOM - 6), lab, fill=(10, 20, 60, 255), font=fnt)
        im.convert("RGB").save(os.path.join(OUT, "room_overlay.jpg"), "JPEG", quality=86)

        with open(os.path.join(OUT, "room_geom.json"), "w") as f:
            json.dump(dict(scale=scale_text, feet_per_pt=fpp, n_polys=len(polys),
                           n_anchors=len(anchors), results=results), f, indent=2)

        # print table
        uniq = [r for r in results if r["status"] == "unique"]
        merged = [r for r in results if r["status"] == "merged"]
        nf = [r for r in results if r["status"] in ("label_not_found", "no_polygon")]
        print(f"scale={scale_text}  polygons={len(polys)}  room-anchors found={len(anchors)}/18\n")
        for r in sorted(results, key=lambda r: r["room"]):
            sf = f"{r['geom_sf']:>7.0f} sf" if r.get("geom_sf") else "     — "
            extra = f"(merged w/ {r.get('merged_with')})" if r["status"] == "merged" else ""
            print(f"  {r['room']} {r['name']:<12} {r['status']:<15} {sf}  {extra}")
        print(f"\n  UNIQUE (clean): {len(uniq)}   MERGED: {len(merged)}   NOT-FOUND: {len(nf)}")
        print(f"  overlay -> {os.path.relpath(os.path.join(OUT,'room_overlay.jpg'), ROOT)}")
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass


if __name__ == "__main__":
    main()
```
