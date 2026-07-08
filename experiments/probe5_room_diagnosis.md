# Probe 5 — Per-room failure diagnosis (and a negative result)

**Date:** 2026-07-08
**Project / sheet:** 14-11290-NEWC, A-1.1 Partial Floor Plan – Branch (doc 1494156 p3), 1/4"=1'-0"
**Script:** `scripts/probe5_room_diagnosis.py` → `data/probe5/diagnosis_overlay.jpg`, `room_diagnosis.json`
**Follows:** Probe 4 (label-guided room SF).

## Goal

For each of the 18 branch rooms, find *why* it closed / fragmented / failed —
so we can name real causes and target fixes instead of guessing. Specific
hypothesis to test: **failures come from thin interior walls being dropped by
the wall-width filter.**

## Method

- Reuse the pipeline; classify **every raw segment** near each room label as
  `wall` (kept), or dropped for a reason: `too_thin` (aligned + long enough +
  has width, but thinner than the wall clusters), `offaxis`, `zerowidth`,
  `short`.
- Count these in a ±13 ft box around each room's number.
- Render an overlay: **green = kept walls, orange = would-be walls dropped as
  too-thin** — so if the hypothesis is right, orange should trace the missing
  interior partitions in the failed rooms.

## Outcomes (solid)

**8 closed · 5 fragment · 5 no-polygon.**

| Outcome | Rooms |
|---|---|
| closed (correct-ish) | 104 Workroom, 105 Self-Service, 106/107/109 Office, 111 Mortgage, 112 Vestibule, 113 Break Room |
| fragment (too small) | 103 Tellers, 108 Conference, 110 Copy/Fax, 115 Men, 116 Women |
| no polygon | 101 Vestibule, 102 Lobby, 114 Corridor, 117 Elect/Data, 118 Jan |

## The negative result — the cheap diagnostic did NOT work

**The "count too-thin segments nearby" metric does not discriminate.** The
closed rooms have **as many or more** thin segments than the failed ones:

| Room | Outcome | too-thin segments nearby |
|---|---|---|
| Office 107 | **closed** | **41** |
| Office 106 | **closed** | 32 |
| Lobby 102 | no polygon | 27 |
| Corridor 114 | no polygon | 24 |
| Jan 118 | no polygon | 18 |
| Mortgage 111 | **closed** | 9 |

Office 107 (which closed fine) has *more* dropped-thin segments than every
failed room. So the auto-label the script printed ("MISSING THIN WALLS") is
**not supported** — thin lines (furniture, text, dimension ticks) are
everywhere, so counting them proves nothing. Lesson (per the diagnose-model
principle): the measurement didn't back the hypothesis, so we don't get to
claim it.

## What the overlay actually shows

- **Green traces the real walls well — including around the failed core rooms.**
  So the failure is **not** "walls weren't detected."
- **Fragments** have plenty of walls but **clutter inside** carves them up:
  Tellers (New Accounts Desk + counter), Conference (floor boxes, braces, the
  "CP-3 border" line), restrooms (sitting in a **dotted/stippled hatch** — the
  "attic storage / 1-hr construction" fill). *Interior clutter splits the room*
  holds up here.
- **No-polygon core** (Jan, Elect/Data, Corridor) are **small, inside that
  dotted-hatch block, with many door openings.** It's a **combination** (hatch
  noise + tiny rooms + many gaps), not one clean cause.

## Honest conclusion

- We now know the **outcome per room** precisely, and the clear **pattern**:
  clean rectangular rooms close; the **dense, hatched service core** fails.
- We do **not** have a *verified single cause per failed room*. The cheap
  automated diagnosis (thin-count) was insufficient, and the real failures are a
  **mix** (hatch + small rooms + many door gaps), which is harder to attribute
  per-room.

## What this changes about solutions

The target sharpens to the **service core**, not "generic geometry":
1. **Better hatch suppression for dotted/stippled fills** — ours handles
   parallel-line hatch, not dot patterns; the core is full of them.
2. **Gap-closing tuned for small rooms with many doors.**
3. Not a broad "wall-vs-line classifier" — the walls are mostly *found*; the
   problem is noise (hatch) and closure in tight, multi-door spaces.

To get true per-room causes, a better instrument would trace **the actual gap in
each failed room's wall loop** (which endpoints didn't connect), rather than
counting nearby segments.

## The script — `scripts/probe5_room_diagnosis.py`

```python
#!/usr/bin/env python3
"""Probe 5 — per-room failure diagnosis. For each of the 18 branch rooms, look
at the segments NEAR its label and classify why the room closed / fragmented /
failed. The key measurement: how many segments near the room are wall-like
(aligned + long enough) but were DROPPED for being too thin -> those are the
"missing interior walls". Renders an overlay: kept walls (green) vs the
too-thin-dropped would-be walls (orange), so the missing walls are visible.

Outputs: data/probe5/diagnosis_overlay.jpg, room_diagnosis.json + table.
Usage: python3 probe5_room_diagnosis.py
"""
import json
import math
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
    seg_len, seg_angle_mod90,
)
from probe4_room_sf import ROOMS  # noqa: E402

DOC, PAGE, ZOOM = 1494156, 3, 2.6
OUT = os.path.join(ROOT, "data", "probe5")
os.makedirs(OUT, exist_ok=True)


def font(sz):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def classify(p0, p1, w, dom, thick_set, pw):
    """Why is this raw segment a wall or not?"""
    L = seg_len(p0, p1)
    if L < 0.015 * pw:
        return "short"
    a = seg_angle_mod90(p0, p1)
    if a is None:
        return "short"
    d = min(abs(a - dom % 90), abs(a - dom % 90 - 90), abs(a - dom % 90 + 90))
    if d > 2.0:
        return "offaxis"
    if w <= 0:
        return "zerowidth"          # glyph/icon fill outline
    if not any(abs(w - c) <= max(0.15, c * 0.3) for c in thick_set):
        return "too_thin"           # aligned + long + has width, but thinner than walls
    return "wall"


def main():
    s3 = r2_client()
    pdf = download_pdf(s3, DOC)
    try:
        fpp, scale_text = find_scale(DOC, PAGE)
        if fpp is None:
            doc = fitz.open(pdf); m = SCALE_RE.findall(doc[PAGE].get_text()); doc.close()
            if m:
                fpp = (int(m[0][1]) / int(m[0][0])) / 72.0

        # room label anchors
        doc = fitz.open(pdf); page = doc[PAGE]
        words = page.get_text("words")
        anchors = {}
        for w in words:
            t = w[4].strip()
            if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
                anchors[int(t)] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        doc.close()

        ex = extract_drawings(pdf, PAGE)
        pw = ex["pw"]
        walls, dom, thick = wall_candidates(ex)
        walls_clean, _ = suppress_hatches(walls, pw)
        lines, _ = snap_and_close(walls_clean, ex["arcs"], pw, feet_per_pt=fpp)
        polys, _ = polygonize_rooms(lines, pw, ex["ph"], 15, 8000, fpp)

        # classify every raw segment
        classified = []
        for p0, p1, wd in ex["line_segments"]:
            c = classify(p0, p1, wd, dom, thick, pw)
            classified.append((p0, p1, wd, c))

        # match rooms to polygons
        room_poly = {}
        poly_rooms = defaultdict(list)
        for rn, (x, y) in anchors.items():
            for i, pg in enumerate(polys):
                if pg.contains(Point(x, y)):
                    room_poly[rn] = i; poly_rooms[i].append(rn); break

        radius = 13.0 / fpp  # ±13 ft neighborhood around each room label
        results = []
        for rn, name in ROOMS.items():
            if rn not in anchors:
                results.append(dict(room=rn, name=name, status="label_not_found"))
                continue
            x, y = anchors[rn]
            near = defaultdict(int)
            for p0, p1, wd, c in classified:
                mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
                if abs(mx - x) <= radius and abs(my - y) <= radius:
                    near[c] += 1
            pi = room_poly.get(rn)
            if pi is None:
                status, area = "no_polygon", None
            else:
                area = round(polys[pi].area * fpp ** 2, 1)
                status = "merged" if len(poly_rooms[pi]) > 1 else ("fragment" if area < 45 else "closed")
            # infer cause
            if status == "label_not_found":
                cause = "room number not read"
            elif status == "no_polygon" and near["too_thin"] >= 3:
                cause = "MISSING THIN WALLS (thin interior partitions dropped)"
            elif status == "no_polygon":
                cause = "no enclosing loop (angled/gaps/too few walls)"
            elif status == "fragment":
                cause = "interior clutter split the room (fixtures/braces/borders)"
            elif status == "merged":
                cause = "a shared wall was missed -> merged with neighbor"
            else:
                cause = "clean close"
            results.append(dict(room=rn, name=name, status=status, area_sf=area,
                                walls_kept=near["wall"], too_thin=near["too_thin"],
                                offaxis=near["offaxis"], zerowidth=near["zerowidth"],
                                cause=cause))

        # overlay: kept walls green, too-thin-dropped orange
        doc = fitz.open(pdf); pm = doc[PAGE].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
        im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA"); doc.close()
        dd = ImageDraw.Draw(im, "RGBA"); fnt = font(int(6 * ZOOM))
        for p0, p1, wd, c in classified:
            if c == "wall":
                dd.line([p0[0]*ZOOM, p0[1]*ZOOM, p1[0]*ZOOM, p1[1]*ZOOM], fill=(0, 160, 80, 220), width=3)
            elif c == "too_thin":
                dd.line([p0[0]*ZOOM, p0[1]*ZOOM, p1[0]*ZOOM, p1[1]*ZOOM], fill=(240, 120, 0, 230), width=3)
        for rn, (x, y) in anchors.items():
            r = next(z for z in results if z["room"] == rn)
            dd.text((x*ZOOM, y*ZOOM), f"{rn} {r['status']}", fill=(10, 20, 90, 255), font=fnt)
        im.convert("RGB").save(os.path.join(OUT, "diagnosis_overlay.jpg"), "JPEG", quality=86)

        with open(os.path.join(OUT, "room_diagnosis.json"), "w") as f:
            json.dump(dict(scale=scale_text, results=results), f, indent=2)

        print(f"legend: GREEN=kept walls  ORANGE=would-be walls dropped as too-thin\n")
        print(f"{'room':<20}{'status':<12}{'area':>6}  walls thin  cause")
        for r in sorted(results, key=lambda r: r["room"]):
            a = f"{r.get('area_sf') or '-':>6}"
            print(f"  {r['room']} {r['name']:<14}{r['status']:<12}{a}   "
                  f"{r.get('walls_kept','-'):>2}  {r.get('too_thin','-'):>3}  {r.get('cause','')}")
        print(f"\noverlay -> {os.path.relpath(os.path.join(OUT,'diagnosis_overlay.jpg'), ROOT)}")
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass


if __name__ == "__main__":
    main()
```
