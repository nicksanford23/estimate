#!/usr/bin/env python3
"""Edge-by-edge outline INSPECTOR renderer (QC step of draft->inspect->repair).

One-shot whole-room review provably misses edge-level errors (room 206's left
edge ran through a wall yet passed a -2% area check AND a whole-room visual
review). This renderer forces per-edge attention: for each room it draws the
proposal polygon on the room crop and NUMBERS EVERY EDGE at its midpoint in
high contrast, so a reviewer must render one verdict per numbered edge.

Two modes:
  (default)  one inspection image per room ->
             data/sam_smoke/<permit>/inspection/inspect_<code>.png
  --edge CODE:IDX   enlarged single-edge strip (edge bbox + 60px padding,
             whole polygon faint, target edge bold) for close calls ->
             .../inspection/edge_<code>_<idx>.png

Coordinates: proposals store polygon_pdf; crop px = (pdf - crop_origin_pdf) *
zoom  (inverse of snap_polygon_walls.py). Machine observation only; nothing
here is truth -- everything routes to founder review.

Usage:
  edge_inspect_render.py --permit 24-06748-RNVS
  edge_inspect_render.py --permit 24-06748-RNVS --codes 206,100
  edge_inspect_render.py --permit 24-06748-RNVS --edge 206:3
  edge_inspect_render.py --permit 24-06748-RNVS \
      --proposals data/sam_smoke/24-06748-RNVS/inspection/repaired_proposals.json \
      --outdir data/sam_smoke/24-06748-RNVS/inspection --suffix _repaired
"""
import argparse
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

POLY_COLOR = (255, 40, 40)      # proposal outline: bright red
VERT_COLOR = (0, 200, 255)      # vertices: cyan
LABEL_TXT = (255, 235, 0)       # edge number text: yellow
LABEL_BG = (0, 0, 0)            # edge number background: black


def _font(size):
    try:
        return ImageFont.truetype(FONT_BOLD, size)
    except Exception:
        return ImageFont.load_default()


def load_tasks(permit):
    p = json.load(open(os.path.join(ROOT, "data", "sam_smoke", permit,
                                    "bundle_g1b", "tasks.json")))
    tl = p["tasks"] if isinstance(p, dict) else p
    return {t["code"]: t for t in tl}


def load_proposals(path):
    """Return {code: proposal_dict}. Accepts task_id-keyed or code-keyed."""
    d = json.load(open(path))
    out = {}
    for k, v in d.items():
        if not isinstance(v, dict):
            continue
        code = v.get("code") or k
        out[str(code)] = v
    return out


def poly_pdf_to_px(poly_pdf, transform):
    z = transform["zoom"]
    ox, oy = transform["crop_origin_pdf"]
    return [[(x - ox) * z, (y - oy) * z] for x, y in poly_pdf]


def _centroid(pts):
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


def _label_box(draw, cx, cy, text, font, W, H):
    """Draw a high-contrast number label centered near (cx, cy), clamped."""
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pad = 5
    bw, bh = tw + 2 * pad, th + 2 * pad
    x0 = min(max(cx - bw / 2, 1), W - bw - 1)
    y0 = min(max(cy - bh / 2, 1), H - bh - 1)
    draw.rectangle([x0, y0, x0 + bw, y0 + bh], fill=LABEL_BG,
                   outline=(255, 255, 255), width=1)
    draw.text((x0 + pad - tb[0], y0 + pad - tb[1]), text, fill=LABEL_TXT,
              font=font)


def render_room(code, poly_px, crop_path, out_path):
    img = Image.open(crop_path).convert("RGB")
    W, H = img.size
    d = ImageDraw.Draw(img)
    n = len(poly_px)
    # polygon outline
    d.polygon([tuple(p) for p in poly_px], outline=POLY_COLOR, width=3)
    # vertices
    for (x, y) in poly_px:
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=VERT_COLOR)
    # numbered edge midpoints, offset outward from centroid
    ctr = _centroid(poly_px)
    font = _font(26)
    for i in range(n):
        p1, p2 = poly_px[i], poly_px[(i + 1) % n]
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ox, oy = mx - ctr[0], my - ctr[1]
        L = math.hypot(ox, oy) or 1.0
        lx, ly = mx + ox / L * 26, my + oy / L * 26
        _label_box(d, lx, ly, str(i), font, W, H)
    img.save(out_path)
    return W, H


def render_edge_strip(code, poly_px, idx, crop_path, out_path):
    img = Image.open(crop_path).convert("RGB")
    W, H = img.size
    n = len(poly_px)
    p1, p2 = poly_px[idx % n], poly_px[(idx + 1) % n]
    pad = 60
    x0 = max(0, int(min(p1[0], p2[0]) - pad))
    y0 = max(0, int(min(p1[1], p2[1]) - pad))
    x1 = min(W, int(max(p1[0], p2[0]) + pad))
    y1 = min(H, int(max(p1[1], p2[1]) + pad))
    if x1 - x0 < 4 or y1 - y0 < 4:
        x0, y0, x1, y1 = 0, 0, W, H
    strip = img.crop((x0, y0, x1, y1))
    sw, sh = strip.size
    scale = max(1.0, min(8.0, 520.0 / max(1, min(sw, sh))))
    strip = strip.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
    d = ImageDraw.Draw(strip)

    def tf(p):
        return ((p[0] - x0) * scale, (p[1] - y0) * scale)

    # whole polygon faint
    d.polygon([tf(p) for p in poly_px], outline=(150, 150, 150), width=1)
    # target edge bold
    a, b = tf(p1), tf(p2)
    d.line([a, b], fill=POLY_COLOR, width=4)
    for pt in (a, b):
        d.ellipse([pt[0] - 5, pt[1] - 5, pt[0] + 5, pt[1] + 5], fill=VERT_COLOR)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    _label_box(d, mx, my - 24, f"edge {idx}", _font(28), *strip.size)
    strip.save(out_path)
    return strip.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--permit", default="24-06748-RNVS")
    ap.add_argument("--proposals", default=None,
                    help="proposals json (default results/proposals_for_editor.json)")
    ap.add_argument("--outdir", default=None,
                    help="output dir (default data/sam_smoke/<permit>/inspection)")
    ap.add_argument("--codes", default=None, help="comma list subset")
    ap.add_argument("--suffix", default="", help="filename suffix e.g. _repaired")
    ap.add_argument("--edge", default=None,
                    help="CODE:IDX render one enlarged edge strip")
    a = ap.parse_args()

    base = os.path.join(ROOT, "data", "sam_smoke", a.permit)
    prop_path = a.proposals or os.path.join(base, "results",
                                            "proposals_for_editor.json")
    outdir = a.outdir or os.path.join(base, "inspection")
    os.makedirs(outdir, exist_ok=True)
    tasks = load_tasks(a.permit)
    props = load_proposals(prop_path)

    if a.edge:
        code, idx = a.edge.split(":")
        idx = int(idx)
        t = tasks[code]
        poly_px = poly_pdf_to_px(props[code]["polygon_pdf"], t["transform"])
        crop = os.path.join(base, "bundle_g1b", t["image"])
        out = os.path.join(outdir, f"edge_{code}_{idx}{a.suffix}.png")
        sz = render_edge_strip(code, poly_px, idx, crop, out)
        print(f"edge {code}:{idx} -> {out} {sz}")
        return

    codes = a.codes.split(",") if a.codes else list(props.keys())
    for code in codes:
        if code not in props or code not in tasks:
            print(f"SKIP {code}: missing proposal or task")
            continue
        t = tasks[code]
        poly = props[code].get("polygon_pdf")
        if not poly:
            print(f"SKIP {code}: null polygon")
            continue
        poly_px = poly_pdf_to_px(poly, t["transform"])
        crop = os.path.join(base, "bundle_g1b", t["image"])
        out = os.path.join(outdir, f"inspect_{code}{a.suffix}.png")
        W, H = render_room(code, poly_px, crop, out)
        print(f"{code}: {len(poly_px)} edges -> inspect_{code}{a.suffix}.png ({W}x{H})")


if __name__ == "__main__":
    main()
