#!/usr/bin/env python3
"""One human-glance review image per surface (founder feedback 2026-07-20).

The per-edge proof strips are the wrong shape for humans: extreme aspect
ratios that no page layout can render sanely, and no room context. This
renders ONE composite per surface from existing gate results (no
re-measurement): the whole room crop with every edge color-coded by its
measured verdict, the deviation printed at each edge, and reference lines
drawn where they diverge. Edge strips remain on disk as click-through zooms.

Colors: green=pass_measured, orange=minor_adjustment, red=major_redraw,
gray=unresolved_evidence, purple=ambiguous_pending_reviewer.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
BASE = os.path.join(ROOT, "data", "sam_smoke", PERMIT)
OUT = os.path.join(BASE, "edge_gate_full")

VERDICT_COLORS = {
    "pass_measured": (0, 150, 60),
    "minor_adjustment": (235, 140, 0),
    "major_redraw": (220, 30, 30),
    "unresolved_evidence": (120, 120, 120),
    "ambiguous_pending_reviewer": (150, 60, 200),
}
REF_COLOR = (0, 200, 90)


def load_tasks():
    t = json.load(open(os.path.join(BASE, "bundle_g1b", "tasks.json")))
    tl = t["tasks"] if isinstance(t, dict) else t
    return {x["code"]: x for x in tl}


def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def main():
    gate = json.load(open(os.path.join(OUT, "gate_results.json")))
    raw = gate.get("surfaces") or {}
    surfaces = list(raw.values()) if isinstance(raw, dict) else raw
    tasks = load_tasks()
    f_lab = font(20)
    f_head = font(24)
    n = 0
    for s in surfaces:
        code = s.get("code")
        t = tasks.get(code)
        if not t or not s.get("edges"):
            continue
        tr = t["transform"]
        zoom, (ox, oy) = tr["zoom"], tr["crop_origin_pdf"]

        def px(pt):
            return ((pt[0] - ox) * zoom, (pt[1] - oy) * zoom)

        img = Image.open(os.path.join(BASE, "bundle_g1b", t["image"])).convert("RGB")
        d = ImageDraw.Draw(img)
        for e in s["edges"]:
            color = VERDICT_COLORS.get(str(e.get("verdict")), (0, 0, 0))
            p1, p2 = px(e["edge_p1_pdf"]), px(e["edge_p2_pdf"])
            # reference line first (under the edge), only when it diverges
            ref = e.get("reference_segment_pdf")
            if ref and e.get("verdict") not in (None, "pass_measured"):
                d.line([px(ref[0]), px(ref[1])], fill=REF_COLOR, width=3)
            d.line([p1, p2], fill=color, width=5)
            # deviation label at edge midpoint, offset perpendicular
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            L = max(1.0, (dx * dx + dy * dy) ** 0.5)
            nxv, nyv = -dy / L, dx / L
            lx, ly = mx + nxv * 18, my + nyv * 18
            dev = e.get("max_deviation_in")
            txt = f'e{e.get("edge_index")}: {dev:.1f}"' if isinstance(dev, (int, float)) else f'e{e.get("edge_index")}: ?'
            tb = d.textbbox((lx, ly), txt, font=f_lab)
            pad = 3
            d.rectangle([tb[0] - pad, tb[1] - pad, tb[2] + pad, tb[3] + pad], fill=(255, 255, 255))
            d.text((lx, ly), txt, fill=color, font=f_lab)
        # header strip
        head = f'{code}  {s.get("space_name") or ""}   ' \
               f'green=pass  orange=nudge  red=redraw  gray=unclear'
        hb = d.textbbox((8, 6), head, font=f_head)
        d.rectangle([0, 0, img.width, hb[3] + 10], fill=(20, 20, 20))
        d.text((8, 6), head, fill=(255, 255, 255), font=f_head)
        img.save(os.path.join(OUT, f"review_{code}.png"))
        n += 1
    print(f"rendered {n} surface review images -> {OUT}/review_<code>.png")


if __name__ == "__main__":
    main()
