#!/usr/bin/env python3
"""Post-GPU review tooling for the SAM 2.1 smoke test on permit 24-06748-RNVS.

Reads the runner's results.json (results_gpu/ from the pod, or the local fake
results/ for testing) plus the input bundle, and for EVERY task x variant x
candidate mask renders a reviewer crop:
  * the viewport image cropped to the mask bbox with generous padding,
  * the mask outline drawn in magenta,
  * the prompt (positive) point drawn in green,
  * a caption strip: room code + space name + variant + SAM score + computed SF.

Outputs under data/sam_smoke/24-06748-RNVS/review/:
  {task_id}/{variant}_m{k}.png     one crop per candidate mask
  review_index.json                task -> crops + metadata + the label-book
                                   checklist a reviewer must judge
  proposals_for_editor.json        task -> best-scoring mask polygon (PDF coords)
                                   per variant, ALL variants, machine_proposal

SELECTION LOCK: the "best" mask per variant is chosen by SAM'S OWN score ONLY.
Choosing by closeness to the schedule area is FORBIDDEN by the geometry-reboot
lock (the answer must not select the prediction). Proposals are machine
proposals, never human truth.

Usage:
  python3 scripts/make_sam_review_packets.py                 # auto: results_gpu/ else results/
  python3 scripts/make_sam_review_packets.py --results data/sam_smoke/24-06748-RNVS/results
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
SMOKE_DIR = os.path.join(ROOT, "data", "sam_smoke", PERMIT)
BUNDLE_DIR = os.path.join(SMOKE_DIR, "bundle")   # default (G0); override with --bundle
REVIEW_DIR = os.path.join(SMOKE_DIR, "review")

MAGENTA = (255, 0, 255)
GREEN = (0, 220, 0)
PAD_MIN = 45          # generous padding, px
PAD_FRAC = 0.18       # or 18% of bbox extent, whichever is larger
CAPTION_H = 46

# The label-book checklist a reviewer judges for every task (geometry-reboot
# review rubric: is the mask usable as an annotation-assistant proposal?).
CHECKLIST_ITEMS = [
    "closed",          # is the proposed region a single closed room?
    "contains-label",  # does it contain its own room-label text?
    "no-spill",        # does it avoid spilling into neighbouring rooms?
    "wall-face",       # does the boundary sit on the wall face (not mid-wall)?
    "door-splits",     # are door openings handled (not leaking through)?
    "area-sane",       # is the computed SF physically plausible for the room?
]


def safe_task(task_id):
    return "".join(c if c.isalnum() or c in "-." else "_" for c in task_id)


def resolve_results_dir(explicit):
    if explicit:
        return explicit
    gpu = os.path.join(SMOKE_DIR, "results_gpu")
    if os.path.exists(os.path.join(gpu, "results.json")):
        return gpu
    fake = os.path.join(SMOKE_DIR, "results")
    if os.path.exists(os.path.join(fake, "results.json")):
        return fake
    raise SystemExit("no results.json under results_gpu/ or results/ — run the "
                     "pod (deploy_sam_smoke.py) or the --fake runner first")


def load_font(size=18):
    for cand in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    return ImageFont.load_default()


def mask_bbox_px(mask):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def render_crop(viewport_rgb, mask, pos_points_px, caption_lines, font):
    """Return a PIL image: padded crop + magenta mask outline + green prompt
    point(s) + caption strip. `mask` is a full-viewport bool array."""
    from skimage import measure
    H, W = mask.shape
    bb = mask_bbox_px(mask)
    if bb is None:
        # empty mask — render a small placeholder centred on the prompt point
        px, py = (pos_points_px[0] if pos_points_px else (W // 2, H // 2))
        bb = (int(px) - 40, int(py) - 40, int(px) + 40, int(py) + 40)
    x0, y0, x1, y1 = bb
    pad = int(max(PAD_MIN, PAD_FRAC * max(x1 - x0, y1 - y0)))
    cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
    cx1, cy1 = min(W, x1 + pad), min(H, y1 + pad)

    crop = Image.fromarray(viewport_rgb[cy0:cy1, cx0:cx1].copy())
    draw = ImageDraw.Draw(crop)

    # magenta mask outline (all contours of the cropped mask)
    sub = mask[cy0:cy1, cx0:cx1]
    for c in measure.find_contours(sub.astype(float), 0.5):
        pts = [(float(col), float(row)) for row, col in c]
        if len(pts) >= 2:
            draw.line(pts + [pts[0]], fill=MAGENTA, width=2)

    # green prompt point(s), only if inside the crop
    for (px, py) in pos_points_px:
        lx, ly = px - cx0, py - cy0
        if 0 <= lx < crop.width and 0 <= ly < crop.height:
            r = 5
            draw.ellipse([lx - r, ly - r, lx + r, ly + r], fill=GREEN,
                         outline=(0, 90, 0), width=2)

    # caption strip beneath the crop
    out = Image.new("RGB", (crop.width, crop.height + CAPTION_H), (20, 20, 20))
    out.paste(crop, (0, 0))
    cd = ImageDraw.Draw(out)
    ty = crop.height + 4
    for line in caption_lines:
        cd.text((6, ty), line, fill=(240, 240, 240), font=font)
        ty += 19
    return out


def main():
    global BUNDLE_DIR, REVIEW_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", help="results dir (default: results_gpu/ else results/)")
    ap.add_argument("--bundle", help="bundle dir (default: bundle/; use bundle_g1b for G1b)")
    ap.add_argument("--review-out", help="review output dir (default: review/)")
    args = ap.parse_args()

    if args.bundle:
        BUNDLE_DIR = args.bundle if os.path.isabs(args.bundle) else os.path.join(ROOT, args.bundle)
    if args.review_out:
        REVIEW_DIR = args.review_out if os.path.isabs(args.review_out) else os.path.join(ROOT, args.review_out)

    results_dir = resolve_results_dir(args.results)
    res = json.load(open(os.path.join(results_dir, "results.json")))
    tasks_doc = json.load(open(os.path.join(BUNDLE_DIR, "tasks.json")))
    per_task = tasks_doc.get("bundle_kind") == "per_task_crop_v1"
    task_by_id = {t["task_id"]: t for t in tasks_doc["tasks"]}
    variants_order = res.get("variants", ["point_only", "point_plus_negatives",
                                          "point_plus_box"])
    font = load_font()
    print(f"[review] results={results_dir}  mode={res.get('mode')}  "
          f"masks={res.get('n_masks')}", flush=True)

    os.makedirs(REVIEW_DIR, exist_ok=True)
    viewports = {}

    def get_viewport(task, pi):
        # per_task (G1b): one crop image per task; legacy (G0): one viewport per page.
        if per_task:
            key, fname = task["task_id"], task["image"]
        else:
            key, fname = pi, f"viewport_p{pi}.png"
        if key not in viewports:
            viewports[key] = np.asarray(Image.open(os.path.join(BUNDLE_DIR, fname)).convert("RGB"))
        return viewports[key]

    # index task -> crops; also collect best-per-variant for proposals
    index = {}
    best = {}   # (task_id, variant) -> row with max sam_score
    n_crops = 0

    for r in res["results"]:
        tid = r["task_id"]
        variant = r["variant"]
        task = task_by_id.get(tid, {})
        # track best-scoring mask per (task, variant) by SAM score ONLY
        key = (tid, variant)
        if key not in best or r["sam_score"] > best[key]["sam_score"]:
            best[key] = r

        # load mask png
        mp = os.path.join(results_dir, r["mask_file"])
        mask = np.asarray(Image.open(mp).convert("L")) > 127
        pos = [tuple(p) for p in
               task.get("prompt_variants", {}).get(variant, {})
               .get("positive_points_px", [])]

        code = r.get("code", task.get("code", "?"))
        space = task.get("space_name", "")
        caption = [
            f"{code}  {space}".strip(),
            f"{variant}  m{r['mask_index']}  score={r['sam_score']:.3f}  "
            f"SF={r['area_sf']}",
        ]
        img = render_crop(get_viewport(task, r["page_index"]), mask, pos, caption, font)

        tdir = os.path.join(REVIEW_DIR, safe_task(tid))
        os.makedirs(tdir, exist_ok=True)
        rel = os.path.join(safe_task(tid), f"{variant}_m{r['mask_index']}.png")
        img.save(os.path.join(REVIEW_DIR, rel))
        n_crops += 1

        entry = index.setdefault(tid, {
            "task_id": tid,
            "code": code,
            "space_name": space,
            "page_index": r["page_index"],
            "sheet_number": task.get("sheet_number"),
            "level": task.get("level"),
            "anchor_provenance": task.get("anchor_provenance"),
            "crops": [],
            "checklist": CHECKLIST_ITEMS,
            "reviewer_note": "machine proposals only; not human truth",
        })
        entry["crops"].append({
            "variant": variant,
            "mask_index": r["mask_index"],
            "file": rel,
            "sam_score": r["sam_score"],
            "area_px": r["area_px"],
            "area_sf": r["area_sf"],
            "polygon_pdf_vertices": len(r.get("polygon_pdf", [])),
        })

    # tasks with no masks (absent / no_anchor) — record so nothing is silently dropped
    for t in tasks_doc["tasks"]:
        if t["task_id"] not in index:
            index[t["task_id"]] = {
                "task_id": t["task_id"],
                "code": t.get("code"),
                "space_name": t.get("space_name"),
                "page_index": t.get("page_index"),
                "status": t.get("status"),
                "crops": [],
                "checklist": CHECKLIST_ITEMS,
                "reviewer_note": "no anchor / no masks — draw from scratch",
            }

    # proposals_for_editor: best mask per variant (ALL variants), SAM score only
    proposals = {}
    for (tid, variant), row in best.items():
        task = task_by_id.get(tid, {})
        p = proposals.setdefault(tid, {
            "task_id": tid,
            "code": row.get("code", task.get("code")),
            "space_name": task.get("space_name"),
            "page_index": row["page_index"],
            "sheet_number": task.get("sheet_number"),
            "kind": "machine_proposal",
            "selection_rule": "max SAM score per variant; schedule area NEVER used",
            "variants": {},
        })
        p["variants"][variant] = {
            "best_mask_index": row["mask_index"],
            "sam_score": row["sam_score"],
            "area_sf": row["area_sf"],
            "area_px": row["area_px"],
            "mask_bbox_pdf": row.get("mask_bbox_pdf"),
            "polygon_pdf": row.get("polygon_pdf", []),
            "mask_file": row["mask_file"],
        }

    index_doc = {
        "schema": "sam_smoke_review_index_v1",
        "permit": PERMIT,
        "results_dir": os.path.relpath(results_dir, ROOT),
        "mode": res.get("mode"),
        "n_tasks": len(index),
        "n_crops": n_crops,
        "checklist_items": CHECKLIST_ITEMS,
        "tasks": index,
    }
    with open(os.path.join(REVIEW_DIR, "review_index.json"), "w") as f:
        json.dump(index_doc, f, indent=2)

    proposals_doc = {
        "schema": "sam_smoke_proposals_for_editor_v1",
        "permit": PERMIT,
        "mode": res.get("mode"),
        "kind": "machine_proposal",
        "selection_rule": "best mask per variant by SAM score ONLY; ALL variants "
                          "included; closeness-to-schedule-area selection is "
                          "forbidden by the lock",
        "variants": variants_order,
        "n_tasks": len(proposals),
        "proposals": proposals,
    }
    # default: SMOKE_DIR/proposals_for_editor.json (unchanged). With --review-out,
    # write alongside the review crops so a G1b test cannot clobber G0's proposals.
    proposals_dir = REVIEW_DIR if args.review_out else SMOKE_DIR
    with open(os.path.join(proposals_dir, "proposals_for_editor.json"), "w") as f:
        json.dump(proposals_doc, f, indent=2)

    print(f"[review] wrote {n_crops} crops across {len(index)} tasks -> {REVIEW_DIR}",
          flush=True)
    print(f"[review] review_index.json + proposals_for_editor.json written", flush=True)


if __name__ == "__main__":
    main()
