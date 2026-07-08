#!/usr/bin/env python3
"""THE ARTIFACT: PDF in -> fully-labeled training data out, zero human effort.
Left panel = the flattened floor plan (all black, layer info gone -- what the
82%-of-files model actually sees). Right panel = the SAME lines auto-colored by
class, derived for FREE from the CAD layers. That coloring is the training target."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from PIL import Image, ImageDraw, ImageFont
from collections import Counter
from probe2_sf import ROOT, r2_client, download_pdf
from probe8_layer_classes import classify_layer, COLOR, CLASSES

DOC, PAGE, Z = 1494156, 3, 3.2
OUT = os.path.join(ROOT, "data", "probe8"); os.makedirs(OUT, exist_ok=True)


def font(sz):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def draw_items(dd, d, color, z):
    for it in d.get("items", []):
        if it[0] == "l":
            dd.line([it[1].x*z, it[1].y*z, it[2].x*z, it[2].y*z], fill=color, width=2)
        elif it[0] == "re":
            r = it[1]; dd.rectangle([r.x0*z, r.y0*z, r.x1*z, r.y1*z], outline=color, width=2)
        elif it[0] == "c":
            pts = [(it[k].x*z, it[k].y*z) for k in range(1, 4)]
            dd.line(pts, fill=color, width=2)


def main():
    s3 = r2_client(); pdf = download_pdf(s3, DOC)
    doc = fitz.open(pdf); pg = doc[PAGE]
    W, H = int(pg.rect.width*Z), int(pg.rect.height*Z)
    drs = pg.get_drawings()

    # LEFT: everything black (the flattened input)
    left = Image.new("RGB", (W, H), "white"); dl = ImageDraw.Draw(left)
    # RIGHT: colored by class
    right = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(right)
    tally = Counter()
    # draw annotation/finish text noise FIRST (underneath), walls LAST (on top)
    order = ["annotation", "finish", "structure", "fixture", "furniture", "door", "wall"]
    byclass = {c: [] for c in CLASSES}
    for d in drs:
        cls = classify_layer(d.get("layer"))
        byclass[cls].append(d)
        tally[cls] += sum(1 for it in d.get("items", []) if it[0] in ("l","re","c"))
    for d in drs:
        draw_items(dl, d, (20, 20, 20), Z)          # left: all black
    for cls in order:
        col = COLOR[cls]
        for d in byclass[cls]:
            draw_items(dr, d, col, Z)               # right: by class
    doc.close(); os.remove(pdf)

    # stitch side by side with a labeled header band
    pad, band = 24, 130
    canvas = Image.new("RGB", (W*2 + pad*3, H + band + pad), "white")
    canvas.paste(left, (pad, band)); canvas.paste(right, (W + pad*2, band))
    dd = ImageDraw.Draw(canvas)
    big, med = font(46), font(30)
    dd.text((pad, 24), "FLATTENED PLAN  (what the model sees — layers gone)", fill=(20,20,20), font=big)
    dd.text((W + pad*2, 24), "AUTO-LABELED FROM CAD LAYERS  (free training target)", fill=(20,20,20), font=big)
    # legend
    lx = W + pad*2; ly = 78
    for cls in ["wall","door","fixture","furniture","structure","finish","annotation"]:
        dd.rectangle([lx, ly, lx+26, ly+26], fill=COLOR[cls])
        dd.text((lx+34, ly), f"{cls} ({tally[cls]})", fill=(30,30,30), font=med)
        lx += 34 + int(dd.textlength(f"{cls} ({tally[cls]})", font=med)) + 40
    out = os.path.join(OUT, "semantic_labels.jpg")
    canvas.save(out, "JPEG", quality=88)
    print("class element counts:", dict(tally.most_common()))
    print("saved ->", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
