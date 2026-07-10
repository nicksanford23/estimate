#!/usr/bin/env python3
"""Probe 30b -- label-quality spot check: render the page raster with the
WALL-LABELED (y=1) segments from the probe30 feature npz overlaid in red.
Full page + a zoom crop centered on the densest wall region.
Downloads each PDF from R2, deletes after. Output data/probe30b/*.png"""
import os, sys, glob
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from probe30_extract_worker import load_env, r2_client  # noqa
import fitz
from PIL import Image, ImageDraw

ENV = load_env()
OUTDIR = os.path.join(ROOT, "data", "probe30b")
TMP = "/tmp/claude-1000/-workspaces-estimate/cfaebbe4-655a-4986-8607-25a6d76540e7/scratchpad/p30b_pdfs"
os.makedirs(TMP, exist_ok=True)

PICKS = [  # permit -> reason recorded in the writeup
    "16-03050-NEWC", "17-09557-NEWC", "24-03784-RNVS",
    "13-44124-NEWC", "22-34220-RNVS", "20-50455-RNVS",
]


def render(permit):
    npz_path = glob.glob(os.path.join(ROOT, "data", "probe30", "features", f"{permit}_*.npz"))[0]
    d = np.load(npz_path)
    doc_id, page = int(d["doc_id"]), int(d["page"])
    p0, p1, y = d["p0"], d["p1"], d["y"]
    pw, ph = float(d["pw"]), float(d["ph"])

    pdf = os.path.join(TMP, f"{doc_id}.pdf")
    s3 = r2_client()
    s3.download_file(ENV["R2_BUCKET"], f"docs/{doc_id}.pdf", pdf)
    try:
        doc = fitz.open(pdf)
        pg = doc[page]
        zoom = 2400.0 / pw
        pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples).convert("RGB")
        doc.close()
    finally:
        os.remove(pdf)

    draw = ImageDraw.Draw(img)
    wall = y == 1
    for a, b in zip(p0[wall], p1[wall]):
        draw.line([a[0] * zoom, a[1] * zoom, b[0] * zoom, b[1] * zoom],
                  fill=(255, 0, 0), width=2)
    img.save(os.path.join(OUTDIR, f"labelcheck_{permit}_full.png"))

    # crop: densest wall region (median of wall midpoints), 30% of page width
    mids = (p0[wall] + p1[wall]) / 2.0
    cx, cy = np.median(mids[:, 0]) * zoom, np.median(mids[:, 1]) * zoom
    half = 0.15 * pw * zoom
    box = (max(0, cx - half), max(0, cy - half),
           min(img.width, cx + half), min(img.height, cy + half))
    crop = img.crop(tuple(int(v) for v in box))
    scale = 2000 / max(crop.width, 1)
    if scale > 1:
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
    crop.save(os.path.join(OUTDIR, f"labelcheck_{permit}_crop.png"))
    print(permit, doc_id, page, "walls:", int(wall.sum()), "/", len(y))


for p in PICKS:
    render(p)
