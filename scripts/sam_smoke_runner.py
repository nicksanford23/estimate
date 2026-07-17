#!/usr/bin/env python3
"""SAM 2.1 room-segmentation smoke runner (gate G1 execution; G0 exercises it with --fake).

Runs ON the GPU pod against the bundle from build_sam_smoke_bundle.py, and ALSO
runs locally end-to-end with --fake (no torch / no sam2 import). For every task
and every prompt variant it saves up to 3 candidate masks (SAM multimask output),
one PNG each, plus a results.json row per (task, variant, mask):

  task_id, variant, mask_index, mask_file, sam_score,
  area_px, area_sf, mask_bbox_pdf, polygon_px, polygon_pdf.

There is NO selection logic anywhere: every candidate is saved. Choosing a
winner by closeness to the printed schedule area is forbidden by the lock.
Masks are machine proposals only; they are never human truth.

Usage (pod):   python scripts/sam_smoke_runner.py --bundle <dir> --out <dir> \
                   --checkpoint sam2.1_hiera_small.pt --model-cfg configs/sam2.1/sam2.1_hiera_s.yaml
Usage (local): python scripts/sam_smoke_runner.py --bundle <dir> --out <dir> --fake
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

RESULT_SCHEMA = "sam_smoke_results_v1"


def load_transforms(bundle):
    """Legacy G0 bundle: one global zoom + per-PAGE device offset."""
    tr = json.load(open(os.path.join(bundle, "transforms.json")))
    zoom = tr["zoom"]
    off = {int(k): v["pixel_offset_device"] for k, v in tr["pages"].items()}
    return zoom, off


def px_to_pdf(px, py, zoom, offset):
    ox, oy = offset
    return [(px + ox) / zoom, (py + oy) / zoom]


def polygonize(mask, zoom, offset):
    """Largest-contour polygon (marching squares) in px and pdf, simplified."""
    from skimage import measure
    from shapely.geometry import Polygon
    contours = measure.find_contours(mask.astype(float), 0.5)
    if not contours:
        return [], []
    # find_contours returns (row, col) = (y, x); pick the longest contour
    c = max(contours, key=len)
    ring_px = [[float(x), float(y)] for y, x in c]
    if len(ring_px) >= 4:
        poly = Polygon(ring_px)
        if poly.is_valid and poly.area > 0:
            poly = poly.simplify(1.5, preserve_topology=True)
            if poly.geom_type == "Polygon" and not poly.is_empty:
                ring_px = [[float(x), float(y)] for x, y in poly.exterior.coords]
    ring_pdf = [[round(v, 3) for v in px_to_pdf(x, y, zoom, offset)] for x, y in ring_px]
    ring_px = [[round(x, 3), round(y, 3)] for x, y in ring_px]
    return ring_px, ring_pdf


def mask_metrics(mask, zoom, offset, ppf=24.0):
    ys, xs = np.where(mask)
    area_px = int(mask.sum())
    area_sf = round(area_px / (ppf * ppf), 3)   # ppf px/ft -> ppf^2 px^2 per sq ft
    if area_px == 0:
        return area_px, area_sf, None
    x0, y0, x1, y1 = float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())
    c0 = px_to_pdf(x0, y0, zoom, offset)
    c1 = px_to_pdf(x1, y1, zoom, offset)
    bbox_pdf = [round(min(c0[0], c1[0]), 3), round(min(c0[1], c1[1]), 3),
                round(max(c0[0], c1[0]), 3), round(max(c0[1], c1[1]), 3)]
    return area_px, area_sf, bbox_pdf


# ---------------------------------------------------------------------------
# fake-mode synthetic mask generator (exercises the full I/O path, no GPU)
# ---------------------------------------------------------------------------
def fake_masks(variant_name, variant, img_shape, rng):
    h, w = img_shape
    pos = variant["positive_points_px"][0]
    cx, cy = pos
    # base radius: from box if present, else default ~7 ft (24 px/ft)
    if variant.get("box_px"):
        bx0, by0, bx1, by1 = variant["box_px"]
        rx, ry = abs(bx1 - bx0) / 2.0, abs(by1 - by0) / 2.0
    else:
        rx = ry = 7.0 * 24.0
    yy, xx = np.ogrid[:h, :w]
    masks, scores = [], []
    for i, scale in enumerate((0.6, 0.85, 1.0)):
        rxi = max(6.0, rx * scale * (0.9 + 0.2 * rng.random()))
        ryi = max(6.0, ry * scale * (0.9 + 0.2 * rng.random()))
        m = ((xx - cx) ** 2) / (rxi ** 2) + ((yy - cy) ** 2) / (ryi ** 2) <= 1.0
        masks.append(m)
        scores.append(round(0.55 + 0.12 * i + 0.05 * rng.random(), 4))
    return masks, scores


# ---------------------------------------------------------------------------
# real SAM 2.1 predictor (only imported when not --fake)
# ---------------------------------------------------------------------------
class SamPredictorWrapper:
    def __init__(self, checkpoint, model_cfg):
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = build_sam2(model_cfg, checkpoint, device=device)
        self.predictor = SAM2ImagePredictor(self.model)
        self._img_key = None

    def set_image(self, img_key, rgb):
        if self._img_key != img_key:
            self.predictor.set_image(rgb)
            self._img_key = img_key

    def predict(self, variant):
        pts = list(variant["positive_points_px"])
        labels = [1] * len(pts)
        for n in variant.get("negative_points_px", []):
            pts.append(n); labels.append(0)
        box = None
        if variant.get("box_px"):
            box = np.array(variant["box_px"], dtype=np.float32)
        masks, scores, _ = self.predictor.predict(
            point_coords=np.array(pts, dtype=np.float32),
            point_labels=np.array(labels, dtype=np.int64),
            box=box, multimask_output=True)
        return [m.astype(bool) for m in masks], [float(s) for s in scores]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--checkpoint")
    ap.add_argument("--model-cfg")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    import random
    rng = random.Random(args.seed)

    tasks_doc = json.load(open(os.path.join(args.bundle, "tasks.json")))
    # per_task_crop_v1 (G1b): one image + one affine (zoom/offset/ppf) PER TASK.
    # legacy G0: one global zoom + per-page offset + fixed 24 px/ft.
    per_task = tasks_doc.get("bundle_kind") == "per_task_crop_v1"
    if not per_task:
        zoom, offsets = load_transforms(args.bundle)
    mask_dir = os.path.join(args.out, "masks")
    os.makedirs(mask_dir, exist_ok=True)

    predictor = None
    if not args.fake:
        assert args.checkpoint and args.model_cfg, "real mode needs --checkpoint and --model-cfg"
        predictor = SamPredictorWrapper(args.checkpoint, args.model_cfg)

    imgs = {}
    def get_img(key, fname):
        if key not in imgs:
            imgs[key] = np.asarray(Image.open(os.path.join(args.bundle, fname)).convert("RGB"))
        return imgs[key]

    def task_transform(t):
        """Return (img_key, img_file, zoom, offset, ppf) for a task in either mode."""
        pi = t["page_index"]
        if per_task:
            tr = t["transform"]
            return (t["task_id"], t["image"], tr["zoom"], tr["offset"], tr["px_per_foot"])
        return (f"p{pi}", f"viewport_p{pi}.png", zoom, offsets[pi], 24.0)

    rows = []
    absent = []
    variants = ["point_only", "point_plus_negatives", "point_plus_box"]
    for t in tasks_doc["tasks"]:
        pi = t["page_index"]
        if t["status"] != "ok":
            absent.append({"task_id": t["task_id"], "reason": t.get("reason", "no_anchor")})
            continue
        img_key, img_file, t_zoom, t_off, t_ppf = task_transform(t)
        rgb = get_img(img_key, img_file)
        if not args.fake:
            predictor.set_image(img_key, rgb)
        for vname in variants:
            variant = t["prompt_variants"][vname]
            if args.fake:
                masks, scores = fake_masks(vname, variant, rgb.shape[:2], rng)
            else:
                masks, scores = predictor.predict(variant)
            for mi, (m, sc) in enumerate(zip(masks, scores)):
                fn = f"{t['code']}_p{pi}_{vname}_m{mi}.png"
                Image.fromarray((m.astype(np.uint8) * 255), "L").save(os.path.join(mask_dir, fn))
                area_px, area_sf, bbox_pdf = mask_metrics(m, t_zoom, t_off, t_ppf)
                poly_px, poly_pdf = polygonize(m, t_zoom, t_off)
                rows.append({
                    "task_id": t["task_id"], "code": t["code"], "page_index": pi,
                    "variant": vname, "mask_index": mi,
                    "mask_file": os.path.join("masks", fn),
                    "sam_score": sc,
                    "area_px": area_px, "area_sf": area_sf,
                    "mask_bbox_pdf": bbox_pdf,
                    "polygon_px": poly_px, "polygon_pdf": poly_pdf,
                    "schedule_area_sf_reference_DIAGNOSTIC_ONLY": None,
                })

    results = {
        "schema": RESULT_SCHEMA, "permit": tasks_doc["permit"],
        "mode": "fake" if args.fake else "sam2.1",
        "bundle_kind": tasks_doc.get("bundle_kind", "viewport_v1"),
        "px_per_foot": "per_task" if per_task else 24.0,
        "selection_policy": "NONE - every candidate mask saved; no winner chosen.",
        "variants": variants,
        "n_tasks_ok": sum(1 for t in tasks_doc["tasks"] if t["status"] == "ok"),
        "n_tasks_absent": len(absent),
        "absent_tasks": absent,
        "n_masks": len(rows),
        "results": rows,
    }
    os.makedirs(args.out, exist_ok=True)
    json.dump(results, open(os.path.join(args.out, "results.json"), "w"), indent=2)
    print(f"mode={'fake' if args.fake else 'sam2.1'}  ok_tasks={results['n_tasks_ok']} "
          f"absent={len(absent)}  masks={len(rows)}  -> {os.path.join(args.out,'results.json')}",
          flush=True)


if __name__ == "__main__":
    main()
