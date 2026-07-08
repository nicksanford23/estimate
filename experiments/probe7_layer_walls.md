# Probe 7 — Use the PDF's own CAD layers (the real unlock)

**Date:** 2026-07-08
**Sheet:** 14-11290-NEWC A-1.1 Branch (doc 1494156 p3), 1/4"=1'-0", 18 rooms
**Script:** `scripts/probe7_layer_walls.py`  ·  **Follows / overturns:** Probes 4–6

## The discovery

This CAD-exported PDF carries its original **layers** — **1,427 optional-content
groups**, and *every drawing path is tagged with its layer*. The names are the
architect's CAD layers:

- **Walls:** `09-MTL STUD WALLS` (interior partitions), `03-CMU`, `09-gyp board`,
  `09-Stucco`, `05-METAL STUD WALLS`, `MD Wall`
- **Envelope:** `08-WINDOWS`, `08-DOORS`, `DBD EXT VEST FRAME`
- **The clutter that broke us — each on its OWN layer:** `Attic Storage Above`
  (the dotted hatch, 4,994 paths), `i-furn`, `15-PLUMB FIXTURES`, `i-millwork`,
  `01-Dimension 48`, `01-Tags`, `01-NOTES_48`.

We had been *ignoring* this and trying to re-derive "wall vs clutter" from a
flattened render. The file already did it for us.

## Method

Extract **only** the wall + envelope layers (regex `WALL|CMU|STUD|GYP|STUCCO|
WINDOW|STORE|GLAZ|GLASS|CURTAIN|MULLION|FRAME|DOOR`), skip everything else, then
snap + polygonize that clean linework and re-match the 18 rooms. No thickness or
angle filtering needed — the layer already certifies these are walls.

## Result

| Approach | closed | fragment | merged | no-polygon |
|---|---|---|---|---|
| Rules (Probe 4, best) | ~8 | ~5 | 0 | 5 (core impossible) |
| Wall layers only | 7 | 0 | 0 | 11 (offices open at storefront) |
| **Wall + envelope layers** | **12** | **1** | **5** | **0** |

**Every one of the 18 rooms now forms a polygon (0 unclosed).** 12 are clean and
correct: Offices 119/124/125 sf, **Conference 213 sf** (was a 15 sf fragment),
restrooms 51/54, Break Room 111, Corridor 47, Workroom 164, Elect/Data 36.

The 5 `merged` are mostly **genuinely open-plan**: Lobby + Tellers is one open
banking hall (no wall between them — that's real). Self-Service / Copy-Fax /
Mortgage are open alcoves; some may need one more layer.

## Why this overturns the earlier conclusion

Probe 6 concluded "the dense service core needs ML." **That was wrong for this
file.** The core failed only because we flattened away the layer information and
then tried to reconstruct it. The moment we respect the layers:
- The dotted-hatch problem vanishes (it's on `Attic Storage Above`).
- The interior partitions appear (they're on `09-MTL STUD WALLS`).
- The impossible core rooms (Jan, Elect/Data, Corridor, restrooms) close cleanly.

**For a vector PDF that carries layers, layer-based extraction beats BOTH rules
and ML** — because the wall/clutter separation is already encoded, exactly, by
the person who drew it.

## The revised strategy

1. **Layer-first.** If the PDF has usable OCG layers, extract wall+envelope
   layers and polygonize. This should handle the large fraction of
   modern CAD-exported permit sets.
2. **ML/vision only as fallback**, for:
   - **flattened / scanned PDFs** (no layers) — the ~1-in-6 case,
   - **open-plan disambiguation** (Lobby/Tellers merges — which walls, if any,
     divide an open area) and net-vs-gross finish area.
3. The vision cross-check still guards published numbers.

## Open items

- Map the exact wall layer set robustly across projects (layer names vary by
  firm; need a small ontology or a per-project layer picker).
- Resolve the open-plan merges (is a merge a real open space or a missing layer?).
- Test on a second project to see how common/clean the layers are.
- Measure closed areas against the printed dimensions (grading), as always.

## The script — `scripts/probe7_layer_walls.py`

```python
#!/usr/bin/env python3
"""Probe 7 — use the PDF's own CAD LAYERS. The file tags every line with its
layer (09-MTL STUD WALLS, 03-CMU, 09-gyp board, 09-Stucco = walls; Attic Storage
Above / i-furn / dimensions / tags = clutter). Extract ONLY the wall layers,
polygonize that CLEAN linework, and re-match the 18 rooms. Tests whether the
clutter/hatch problem simply disappears when we respect the layers.

Usage: python3 probe7_layer_walls.py
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from probe2_sf import (  # noqa: E402
    r2_client, download_pdf, dominant_angle, snap_and_close, polygonize_rooms,
    find_scale, SCALE_RE, seg_len,
)
from probe4_room_sf import ROOMS  # noqa: E402

DOC, PAGE, ZOOM = 1494156, 3, 2.6
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "probe7")
os.makedirs(OUT, exist_ok=True)

WALL_RE = re.compile(
    r"WALL|CMU|STUD|GYP|STUCCO|WINDOW|STORE|GLAZ|GLASS|CURTAIN|MULLION|FRAME|DOOR",
    re.IGNORECASE)


def font(sz):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def extract_wall_layer_segments(pdf, page_index):
    doc = fitz.open(pdf)
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    segs = []          # (p0, p1, width)
    used_layers = set()
    for d in page.get_drawings():
        lay = d.get("layer") or ""
        if not WALL_RE.search(lay):
            continue
        used_layers.add(lay)
        width = d.get("width") or 0.0
        is_fill = d.get("fill") is not None and d.get("type") in ("f", "fs")
        for item in d.get("items", []):
            if item[0] == "l":
                p0, p1 = (item[1].x, item[1].y), (item[2].x, item[2].y)
                segs.append((p0, p1, width if width else 1.0))
            elif item[0] == "re":
                r = item[1]
                rw, rh = r.width, r.height
                short, long = min(rw, rh), max(rw, rh)
                if is_fill and long > 0 and short / pw < 0.02 and long / max(pw, ph) > 0.01:
                    cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
                    if rw >= rh:
                        segs.append(((r.x0, cy), (r.x1, cy), short))
                    else:
                        segs.append(((cx, r.y0), (cx, r.y1), short))
    doc.close()
    return segs, pw, ph, sorted(used_layers)


def main():
    s3 = r2_client()
    pdf = download_pdf(s3, DOC)
    try:
        fpp, scale_text = find_scale(DOC, PAGE)
        if fpp is None:
            doc = fitz.open(pdf); m = SCALE_RE.findall(doc[PAGE].get_text()); doc.close()
            if m:
                fpp = (int(m[0][1]) / int(m[0][0])) / 72.0

        segs, pw, ph, used = extract_wall_layer_segments(pdf, PAGE)
        print(f"wall-layer segments: {len(segs)}   from layers: {used}\n")

        # keep only reasonably long segments (drop tiny stubs)
        walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
        # feed straight into snap + polygonize (no thickness/angle filtering needed —
        # the layer already told us these are walls)
        lines, _ = snap_and_close([(p0, p1, seg_len(p0, p1), w) for p0, p1, w in walls],
                                  [], pw, feet_per_pt=fpp)
        polys, nfaces = polygonize_rooms(lines, pw, ph, 15, 8000, fpp)

        # room anchors
        doc = fitz.open(pdf); page = doc[PAGE]
        anchors = {}
        for w in page.get_text("words"):
            t = w[4].strip()
            if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
                anchors[int(t)] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        doc.close()

        room_poly, poly_rooms = {}, defaultdict(list)
        for rn, (x, y) in anchors.items():
            for i, pg in enumerate(polys):
                if pg.contains(Point(x, y)):
                    room_poly[rn] = i; poly_rooms[i].append(rn); break

        counts = dict(closed=0, fragment=0, merged=0, no_polygon=0)
        rows = []
        for rn, name in ROOMS.items():
            pi = room_poly.get(rn)
            if pi is None:
                counts["no_polygon"] += 1; rows.append((rn, name, "no_polygon", None))
            elif len(poly_rooms[pi]) > 1:
                counts["merged"] += 1; rows.append((rn, name, "merged", None))
            else:
                a = polys[pi].area * fpp ** 2
                if a < 25:
                    counts["fragment"] += 1; rows.append((rn, name, "fragment", round(a, 1)))
                else:
                    counts["closed"] += 1; rows.append((rn, name, "closed", round(a, 1)))

        # overlay
        doc = fitz.open(pdf); pm = doc[PAGE].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
        im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA"); doc.close()
        dd = ImageDraw.Draw(im, "RGBA"); fnt = font(int(6 * ZOOM))
        for pi, mates in poly_rooms.items():
            col = (210, 70, 60, 90) if len(mates) > 1 else (0, 170, 90, 90)
            pts = [(x * ZOOM, y * ZOOM) for x, y in polys[pi].exterior.coords]
            dd.polygon(pts, fill=col, outline=(0, 100, 60, 255))
        for rn, (x, y) in anchors.items():
            r = next(z for z in rows if z[0] == rn)
            lab = f"{rn} {r[3]:.0f}sf" if r[3] else f"{rn} {r[2]}"
            dd.text((x * ZOOM, y * ZOOM), lab, fill=(10, 20, 90, 255), font=fnt)
        im.convert("RGB").save(os.path.join(OUT, "layer_overlay.jpg"), "JPEG", quality=86)

        print(f"scale={scale_text}  polygons={len(polys)}  anchors={len(anchors)}/18\n")
        for rn, name, st, a in sorted(rows):
            print(f"  {rn} {name:<14}{st:<12}{(str(a)+' sf') if a else ''}")
        print(f"\n  >>> closed={counts['closed']}  fragment={counts['fragment']}  "
              f"merged={counts['merged']}  no_polygon={counts['no_polygon']}   (was 8-11 closed)")
        print(f"  overlay -> {os.path.relpath(os.path.join(OUT,'layer_overlay.jpg'))}")
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass


if __name__ == "__main__":
    main()
```

---

## Coverage reality check (added after testing 51 unique permits)

`scripts/scan_layer_coverage.py` checked one floor plan from each of the **51
unique permits** we've labeled. Result:

| bucket | share | meaning |
|---|---|---|
| vector overall | 50/51 (98%) | only 1 scanned — good |
| **kept named CAD layers** | **8/51 (16%)** | layer trick works, free + exact |
| flattened to one blank layer | 42/51 (82%) | layer names destroyed at export; trick gives nothing |

**The layer trick is real but NOT universal.** It worked perfectly on the
Liberty Bank file, but ~82% of exports collapse every line onto a single unnamed
layer (`''`), so there's no wall layer to grab. The clutter/wall separation is
gone again for those.

**Revised strategy (corrected):**
1. **Detect + use layers where present (~1 in 6 files)** — free, exact.
2. For the ~82% flattened files, we still need to *find* the walls → rules
   (got ~half the rooms) + ML/vision for the rest.
3. **The 16% layered files are a FREE labeled training set**: render the flat
   version as input, take the wall layers as the answer, and train a wall-finder
   that works on the flattened 82%. That is the highest-value use of the layered
   files — they teach the model for the ones that lost their layers.

So the layer discovery didn't remove the ML need — it **supplies the free labels
that make the ML cheap.**
