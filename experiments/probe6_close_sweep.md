# Probe 6 — Intervention as diagnosis: does better closing fix the core?

**Date:** 2026-07-08
**Sheet:** 14-11290-NEWC A-1.1 Branch (doc 1494156 p3), 1/4"=1'-0", 18 rooms
**Script:** `scripts/probe6_close_sweep.py`  ·  **Follows:** Probes 4 & 5

## Idea

Probe 5 couldn't pin the cause by counting segments. So instead of more
analysis, **intervene and measure**: sweep the wall-CLOSING parameters (endpoint
snap tolerance + door-gap width). If the no-polygon core rooms flip to `closed`
as we close harder, "gaps didn't close" was the cause. Geometry up to wall
candidates is held fixed; only `snap_and_close` changes per setting.

## Result

| Setting | snap | door_ft | closed | frag | merged | no-poly | change |
|---|---|---|---|---|---|---|---|
| baseline | .0025 | 4.5 | 11 | 2 | 0 | 5 | — |
| more-snap | .0050 | 4.5 | 11 | 2 | 0 | 5 | no change |
| bigger-gap | .0025 | 6.0 | 9 | 2 | 0 | 7 | **−restrooms** |
| snap+gap | .0050 | 6.0 | 9 | 2 | 0 | 7 | −restrooms |
| aggressive | .0080 | 6.0 | 9 | 2 | 0 | 7 | −restrooms |

## Finding — the gap hypothesis is DISPROVEN

- **More snapping: zero effect.** Walls aren't failing to close because endpoints
  don't-quite-meet.
- **Bigger door gaps: strictly worse.** No core room recovered; the restrooms
  *dropped out* (closing bigger gaps merged/broke them). Over-closing hurts.
- The 5 no-polygon core rooms (Jan, Elect/Data, Corridor, Lobby, Vestibule 101)
  stay failed under every setting.

So the residual failures are **not fixable by tuning closing parameters.**

## The real conclusion of the SF probe arc (4→5→6)

1. Rules-based geometry measures **~half the rooms correctly** on its own (clean
   rectangular offices) — genuinely useful.
2. The failures cluster in the **dense, hatched service core**, and — proven by
   intervention here — they are **not** fixable by parameter tuning (snap /
   gap-closing don't help and can hurt).
3. Therefore the residual bottleneck needs **smarter perception** — telling
   clutter / dotted-hatch / fixtures apart from walls — i.e. the ML/classifier
   work + the vision cross-check, **not more rules**.

That is the honest, earned bottom line: parameter tuning is exhausted; the next
real lever is perception (ML), and in the meantime the product ships as
**assisted takeoff** — auto-accept the ~half that measure, human-confirm the core.

## The script — `scripts/probe6_close_sweep.py`

```python
#!/usr/bin/env python3
"""Probe 6 — intervention as diagnosis. Re-run the room-matching while sweeping
the wall-CLOSING parameters (endpoint snap tolerance + door-gap width). If the
no-polygon core rooms flip to 'closed' as we close more aggressively, then
"gaps didn't close" was the real cause. If they don't (or we just get merges),
the cause is elsewhere (clutter/hatch). Geometry up to wall candidates is fixed;
only snap_and_close changes per setting.

Usage: python3 probe6_close_sweep.py
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from probe2_sf import (  # noqa: E402
    r2_client, download_pdf, extract_drawings, wall_candidates, suppress_hatches,
    snap_and_close, polygonize_rooms, find_scale, SCALE_RE,
)
from probe4_room_sf import ROOMS  # noqa: E402

DOC, PAGE = 1494156, 3

# (snap_tol_frac, door_ft) settings to sweep
SETTINGS = [
    ("baseline", 0.0025, 4.5),
    ("more-snap", 0.0050, 4.5),
    ("bigger-gap", 0.0025, 6.0),
    ("snap+gap", 0.0050, 6.0),
    ("aggressive", 0.0080, 6.0),
]


def evaluate(walls_clean, arcs, pw, ph, fpp, anchors, snap_tol, door_ft):
    lines, _ = snap_and_close(walls_clean, arcs, pw, snap_tol_frac=snap_tol,
                              door_ft=door_ft, feet_per_pt=fpp)
    polys, _ = polygonize_rooms(lines, pw, ph, 15, 8000, fpp)
    room_poly, poly_rooms = {}, defaultdict(list)
    for rn, (x, y) in anchors.items():
        for i, pg in enumerate(polys):
            if pg.contains(Point(x, y)):
                room_poly[rn] = i; poly_rooms[i].append(rn); break
    c = dict(closed=0, fragment=0, merged=0, no_polygon=0)
    closed_rooms = []
    for rn in ROOMS:
        if rn not in anchors:
            continue
        pi = room_poly.get(rn)
        if pi is None:
            c["no_polygon"] += 1
        elif len(poly_rooms[pi]) > 1:
            c["merged"] += 1
        else:
            area = polys[pi].area * fpp ** 2
            if area < 25:
                c["fragment"] += 1
            else:
                c["closed"] += 1
                closed_rooms.append(rn)
    return c, sorted(closed_rooms), len(polys)


def main():
    s3 = r2_client()
    pdf = download_pdf(s3, DOC)
    try:
        fpp, _ = find_scale(DOC, PAGE)
        if fpp is None:
            doc = fitz.open(pdf); m = SCALE_RE.findall(doc[PAGE].get_text()); doc.close()
            if m:
                fpp = (int(m[0][1]) / int(m[0][0])) / 72.0
        doc = fitz.open(pdf); page = doc[PAGE]
        anchors = {}
        for w in page.get_text("words"):
            t = w[4].strip()
            if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
                anchors[int(t)] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        doc.close()

        ex = extract_drawings(pdf, PAGE)
        walls, dom, thick = wall_candidates(ex)
        walls_clean, _ = suppress_hatches(walls, ex["pw"])

        print(f"anchors={len(anchors)}/18   (18 rooms)\n")
        print(f"{'setting':<12}{'snap':>7}{'door_ft':>8}  {'closed':>6}{'frag':>5}{'merged':>7}{'none':>5}   closed rooms")
        base_closed = None
        for name, snap, door in SETTINGS:
            c, closed_rooms, npoly = evaluate(walls_clean, ex["arcs"], ex["pw"], ex["ph"],
                                              fpp, anchors, snap, door)
            if base_closed is None:
                base_closed = set(closed_rooms)
            gained = sorted(set(closed_rooms) - base_closed)
            lost = sorted(base_closed - set(closed_rooms))
            tag = ""
            if gained:
                tag += f"  +{gained}"
            if lost:
                tag += f"  -{lost}"
            print(f"{name:<12}{snap:>7.4f}{door:>8.1f}  {c['closed']:>6}{c['fragment']:>5}"
                  f"{c['merged']:>7}{c['no_polygon']:>5}   {closed_rooms}{tag}")
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass


if __name__ == "__main__":
    main()
```
