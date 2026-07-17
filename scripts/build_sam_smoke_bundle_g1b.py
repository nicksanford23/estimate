#!/usr/bin/env python3
"""Build the G1b SAM room-segmentation bundle for 24-06748-RNVS: PER-ROOM CROPS.

Local preparation ONLY. No GPU, no RunPod, no network, no secrets, no pip installs.

WHY G1b (see STATE.md "SAM smoke G0+G1 executed"): G1 fed SAM full viewport
strips (899x2506 px @ 24 px/ft). SAM downscales the longest side to 1024, so the
effective resolution collapsed to ~10 px/ft and walls became ~1 px -> hole-riddled
"confetti" masks. G1b HYPOTHESIS: hand SAM a tight per-room crop where the room
fills most of the frame; after SAM's internal 1024 resize the walls are still
several px thick, so the mask follows them.

This script REUSES the G0 bundle's resolved anchors + geometry boxes verbatim
(data/sam_smoke/24-06748-RNVS/bundle/tasks.json). It does NOT re-run anchor
resolution (same room-tag/door-tag rule, same visual_manual 209A/211, same
explicit no_anchor 210). It only re-frames each room as its own native-resolution
crop rendered fresh from the ORIGINAL PDF (fitz clip — never resampled from the
old PNGs).

Per task it writes, under data/sam_smoke/24-06748-RNVS/bundle_g1b/:
  - crop_<code>.png : one PNG per OK task, cropped from the source PDF. Crop window
    = the task's G0 geometry box (point_plus_box.box_pdf), each half-extent grown
    40%, re-centred on the room anchor, clamped to the viewport bbox. Render zoom
    is chosen PER CROP so the longest side lands near ~1000 px (SAM's native input;
    no downscale loss), clamped to [12, 48] px/ft. Actual px_per_ft recorded.
  - tasks.json    : same schema the runner consumes, PLUS per-task `image` and
    `transform` keys (bundle_kind="per_task_crop_v1"). Prompt variants recomputed
    in the crop's pixel space: (a) point only, (b) point + negatives (only OTHER
    rooms' anchors that fall INSIDE this crop), (c) point + box (the G0 geometry
    box transformed into crop px, clamped to the image). 210 stays no_anchor.
  - transforms.json : per-task forward/inverse affine + machine round-trip
    self-test (<0.01 px).
  - manifest.json : same fields as G0 (container image, checkpoint URLs, runner
    command updated for bundle_g1b, max runtime 60 min, budget cap $2, sha256 of
    every file).

Coordinate contract (matches G0's integer-offset form, exact round-trip):
  forward:  px = pdf * zoom - offset          (offset = fitz pixmap device origin)
  inverse:  pdf = (px + offset) / zoom
  crop_origin_pdf = offset / zoom             (== the crop's top-left in PDF space)
"""
import hashlib
import json
import os

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
PDF_PATH = os.path.join(ROOT, "data", "render_cache", "pdf", "7372349.pdf")
G0_BUNDLE = os.path.join(ROOT, "data", "sam_smoke", PERMIT, "bundle")
OUT_DIR = os.path.join(ROOT, "data", "sam_smoke", PERMIT, "bundle_g1b")

PT_PER_FOOT = 18.0            # 1/4" = 1'-0" -> 18 pdf points per foot (verified, G0)
TARGET_LONG_PX = 1000.0       # aim SAM's native 1024 input; longest crop side ~1000 px
PPF_MIN = 12.0               # never coarser than this (still > G1's ~10 px/ft effective)
PPF_MAX = 48.0               # never finer than this
PAD_FRAC = 0.40               # grow each box half-extent by 40%


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)

    g0 = json.load(open(os.path.join(G0_BUNDLE, "tasks.json")))
    g0_tr = json.load(open(os.path.join(G0_BUNDLE, "transforms.json")))
    viewport_by_page = {int(k): v["viewport_bbox_pdf"] for k, v in g0_tr["pages"].items()}

    g0_tasks = g0["tasks"]
    # every OK anchor in PDF space, for negative-point selection (only those that
    # fall inside a given crop are used as negatives for that crop).
    ok_anchors = {t["task_id"]: {"page_index": t["page_index"], "code": t["code"],
                                 "pdf": t["anchor_pdf"]}
                  for t in g0_tasks if t["status"] == "ok"}

    transforms = {"schema": "sam_smoke_transforms_g1b_v1", "permit": PERMIT,
                  "bundle_kind": "per_task_crop_v1", "pt_per_foot": PT_PER_FOOT,
                  "target_long_px": TARGET_LONG_PX, "ppf_min": PPF_MIN, "ppf_max": PPF_MAX,
                  "coordinate_contract": "px = pdf*zoom - offset ; pdf = (px+offset)/zoom",
                  "tasks": {}}

    tasks_out = []
    max_err = 0.0
    ppf_list = []

    for t in g0_tasks:
        tid = t["task_id"]
        pi = t["page_index"]
        code = t["code"]

        base = {"task_id": tid, "page_index": pi, "sheet_number": t["sheet_number"],
                "level": t["level"], "code": code, "space_name": t["space_name"],
                "anchor_provenance": t["anchor_provenance"], "status": t["status"]}

        if t["status"] != "ok":
            base["reason"] = t.get("reason")
            base["prompt_variants"] = {}
            tasks_out.append(base)
            continue

        anchor_pdf = t["anchor_pdf"]
        box_pdf = t["prompt_variants"]["point_plus_box"]["box_pdf"]  # [x0,y0,x1,y1]
        vb = viewport_by_page[pi]
        vx0, vy0 = vb["x"], vb["y"]
        vx1, vy1 = vb["x"] + vb["w"], vb["y"] + vb["h"]

        # ---- crop window: box half-extents grown 40%, centred on the anchor,
        #      clamped to the viewport bbox. -------------------------------------
        ax, ay = anchor_pdf
        half_w = (box_pdf[2] - box_pdf[0]) / 2.0 * (1.0 + PAD_FRAC)
        half_h = (box_pdf[3] - box_pdf[1]) / 2.0 * (1.0 + PAD_FRAC)
        cx0 = max(vx0, ax - half_w); cy0 = max(vy0, ay - half_h)
        cx1 = min(vx1, ax + half_w); cy1 = min(vy1, ay + half_h)
        crop_w_pt = cx1 - cx0
        crop_h_pt = cy1 - cy0

        # ---- per-crop zoom: longest side -> ~TARGET_LONG_PX, ppf clamped --------
        long_pt = max(crop_w_pt, crop_h_pt)
        zoom_raw = TARGET_LONG_PX / long_pt
        ppf_raw = zoom_raw * PT_PER_FOOT
        ppf = min(PPF_MAX, max(PPF_MIN, ppf_raw))
        zoom = ppf / PT_PER_FOOT
        ppf_clamped = ppf != ppf_raw

        # ---- render the crop fresh from the source PDF (fitz clip) --------------
        page = doc[pi]
        pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom),
                             clip=fitz.Rect(cx0, cy0, cx1, cy1), alpha=False)
        off_x, off_y = float(pm.x), float(pm.y)       # integer device origin
        W, H = pm.width, pm.height
        img_name = f"crop_{code}.png"
        pm.save(os.path.join(OUT_DIR, img_name))

        def to_px(x, y):
            return [x * zoom - off_x, y * zoom - off_y]

        def to_pdf(px, py):
            return [(px + off_x) / zoom, (py + off_y) / zoom]

        # round-trip self-test on the four crop corners + centre + anchor
        import random
        rng = random.Random(hash(tid) & 0xFFFFFFFF)
        for _ in range(500):
            px, py = rng.uniform(0, W), rng.uniform(0, H)
            bx, by = to_px(*to_pdf(px, py))
            max_err = max(max_err, abs(bx - px), abs(by - py))

        # ---- anchor + prompt variants in crop pixel space ----------------------
        apx = [round(v, 3) for v in to_px(ax, ay)]

        # negatives = OTHER ok anchors whose PDF point lands inside THIS crop
        negs_px, negs_pdf, negs_code = [], [], []
        for tid2, a2 in ok_anchors.items():
            if tid2 == tid or a2["page_index"] != pi:
                continue
            nx, ny = a2["pdf"]
            if cx0 <= nx <= cx1 and cy0 <= ny <= cy1:
                negs_px.append([round(v, 3) for v in to_px(nx, ny)])
                negs_pdf.append([round(nx, 3), round(ny, 3)])
                negs_code.append(a2["code"])

        # box variant = G0 geometry box transformed to crop px, clamped to image
        bx0, by0 = to_px(box_pdf[0], box_pdf[1])
        bx1, by1 = to_px(box_pdf[2], box_pdf[3])
        box_px = [round(max(0.0, min(W, bx0)), 3), round(max(0.0, min(H, by0)), 3),
                  round(max(0.0, min(W, bx1)), 3), round(max(0.0, min(H, by1)), 3)]
        box_clamped = (bx0 < 0 or by0 < 0 or bx1 > W or by1 > H)

        base.update({
            "image": img_name,
            "anchor_confidence": t.get("anchor_confidence"),
            "anchor_diag": t.get("anchor_diag"),
            "anchor_pdf": [round(ax, 3), round(ay, 3)],
            "anchor_px": apx,
            "transform": {
                "zoom": zoom, "px_per_foot": round(ppf, 4),
                "px_per_foot_unclamped": round(ppf_raw, 4), "ppf_clamped": ppf_clamped,
                "offset": [off_x, off_y], "size": [W, H],
                "crop_bbox_pdf": [round(cx0, 3), round(cy0, 3), round(cx1, 3), round(cy1, 3)],
                "crop_origin_pdf": [round(off_x / zoom, 3), round(off_y / zoom, 3)],
                "crop_wh_pt": [round(crop_w_pt, 3), round(crop_h_pt, 3)],
            },
            "prompt_variants": {
                "point_only": {
                    "positive_points_px": [apx],
                    "positive_points_pdf": [[round(ax, 3), round(ay, 3)]],
                    "negative_points_px": [], "box_px": None,
                },
                "point_plus_negatives": {
                    "positive_points_px": [apx],
                    "positive_points_pdf": [[round(ax, 3), round(ay, 3)]],
                    "negative_points_px": negs_px,
                    "negative_points_pdf": negs_pdf,
                    "negative_codes": negs_code,
                    "box_px": None,
                },
                "point_plus_box": {
                    "positive_points_px": [apx],
                    "positive_points_pdf": [[round(ax, 3), round(ay, 3)]],
                    "negative_points_px": [],
                    "box_px": box_px,
                    "box_pdf": [round(v, 3) for v in box_pdf],
                    "box_provenance": "geometry_only (G0 box transformed to crop px)",
                    "box_clamped_to_image": box_clamped,
                },
            },
        })
        tasks_out.append(base)

        transforms["tasks"][tid] = {
            "image": img_name, "code": code, "page_index": pi,
            "zoom": zoom, "px_per_foot": round(ppf, 4),
            "offset": [off_x, off_y], "size": [W, H],
            "forward_affine": {"px_x": [zoom, 0.0, -off_x], "px_y": [0.0, zoom, -off_y]},
            "inverse_affine": {"pdf_x": [1.0 / zoom, 0.0, off_x / zoom],
                               "pdf_y": [0.0, 1.0 / zoom, off_y / zoom]},
            "crop_bbox_pdf": [round(cx0, 3), round(cy0, 3), round(cx1, 3), round(cy1, 3)],
        }
        ppf_list.append(round(ppf, 2))
        print(f"{code:6s} p{pi} crop {W}x{H}px  ppf={ppf:.1f}"
              f"{' (clamped)' if ppf_clamped else ''}  negs={len(negs_code)}", flush=True)

    assert max_err < 0.01, f"round-trip error too large: {max_err}"
    transforms["roundtrip_selftest"] = {"n_points_per_task": 500,
                                        "max_error_px": max_err, "tolerance_px": 0.01,
                                        "passed": True}
    print(f"round-trip self-test: max_err={max_err:.3e}px < 0.01  OK", flush=True)

    ok = sum(1 for r in tasks_out if r["status"] == "ok")
    by_prov = {}
    for r in tasks_out:
        by_prov[r["anchor_provenance"]] = by_prov.get(r["anchor_provenance"], 0) + 1

    ppf_sorted = sorted(ppf_list)
    ppf_summary = {
        "n": len(ppf_list),
        "min": ppf_sorted[0] if ppf_sorted else None,
        "max": ppf_sorted[-1] if ppf_sorted else None,
        "median": ppf_sorted[len(ppf_sorted) // 2] if ppf_sorted else None,
        "n_at_ceiling_48": sum(1 for p in ppf_list if p >= PPF_MAX - 1e-6),
        "n_at_floor_12": sum(1 for p in ppf_list if p <= PPF_MIN + 1e-6),
        "values": ppf_sorted,
    }

    tasks_doc = {
        "schema": "sam_smoke_tasks_v1",
        "bundle_kind": "per_task_crop_v1",
        "permit": PERMIT,
        "gate": "G1b",
        "source_bundle": os.path.relpath(G0_BUNDLE, ROOT),
        "anchor_rule": g0.get("anchor_rule"),
        "reuse_note": "anchors + geometry boxes copied verbatim from the G0 bundle; "
                      "only the framing (per-room native-resolution crop) changed.",
        "crop_rule": f"box half-extents grown {int(PAD_FRAC*100)}%, re-centred on anchor, "
                     f"clamped to viewport; zoom -> longest side ~{int(TARGET_LONG_PX)}px, "
                     f"ppf clamped to [{PPF_MIN},{PPF_MAX}].",
        "counts": {"total": len(tasks_out), "ok": ok, "no_anchor": len(tasks_out) - ok,
                   "by_provenance": by_prov},
        "px_per_foot_summary": ppf_summary,
        "tasks": tasks_out,
    }

    json.dump(tasks_doc, open(os.path.join(OUT_DIR, "tasks.json"), "w"), indent=2)
    json.dump(transforms, open(os.path.join(OUT_DIR, "transforms.json"), "w"), indent=2)
    print(f"tasks: {ok}/{len(tasks_out)} anchored; by provenance {by_prov}", flush=True)
    print(f"ppf: min={ppf_summary['min']} median={ppf_summary['median']} "
          f"max={ppf_summary['max']} ceil48={ppf_summary['n_at_ceiling_48']} "
          f"floor12={ppf_summary['n_at_floor_12']}", flush=True)

    # ---- manifest -----------------------------------------------------------
    bundle_files = ["tasks.json", "transforms.json"] + sorted(
        f for f in os.listdir(OUT_DIR) if f.startswith("crop_") and f.endswith(".png"))
    file_hashes = {fn: {"sha256": sha256_file(os.path.join(OUT_DIR, fn)),
                        "bytes": os.path.getsize(os.path.join(OUT_DIR, fn))}
                   for fn in bundle_files}
    manifest = {
        "schema": "sam_smoke_manifest_v1",
        "permit": PERMIT,
        "gate": "G1b",
        "bundle_kind": "per_task_crop_v1",
        "purpose": "SAM 2.1 zero-shot room-segmentation, per-room native-resolution "
                   "crops (G1b). Machine proposals only; not human truth; cannot "
                   "promote SAM to production.",
        "container_image": "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
        "sam2_repo": "https://github.com/facebookresearch/sam2",
        "checkpoints": {
            "small": {"url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
                      "sha256": "FILL_AT_DOWNLOAD_ON_POD", "run_order": 1},
            "large": {"url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt",
                      "sha256": "FILL_AT_DOWNLOAD_ON_POD", "run_order": 2,
                      "condition": "run only after Small completes end-to-end"},
        },
        "python_deps_on_pod": ["torch (from container)", "sam2 (pip install from repo)",
                               "numpy", "pillow", "scikit-image", "shapely"],
        "runner_command": "python scripts/sam_smoke_runner.py "
                          "--bundle data/sam_smoke/24-06748-RNVS/bundle_g1b "
                          "--out data/sam_smoke/24-06748-RNVS/results_g1b "
                          "--checkpoint <sam2.1_hiera_small.pt> "
                          "--model-cfg configs/sam2.1/sam2.1_hiera_s.yaml",
        "runner_fake_command": "python scripts/sam_smoke_runner.py "
                               "--bundle data/sam_smoke/24-06748-RNVS/bundle_g1b "
                               "--out data/sam_smoke/24-06748-RNVS/results_g1b_fake --fake",
        "result_schema_version": "sam_smoke_results_v1",
        "max_runtime_minutes": 60,
        "budget_cap_usd": 2,
        "pt_per_foot": PT_PER_FOOT,
        "px_per_foot": "per_task (see tasks.json transform.px_per_foot)",
        "px_per_foot_summary": ppf_summary,
        "selection_policy": "NONE. Every candidate mask + score is saved. Choosing a "
                            "winner by closeness to schedule area is forbidden (lock).",
        "bundle_files": file_hashes,
        "anchor_summary": {"total_tasks": len(tasks_out), "anchored": ok,
                           "by_provenance": by_prov},
    }
    json.dump(manifest, open(os.path.join(OUT_DIR, "manifest.json"), "w"), indent=2)
    print("wrote manifest.json; bundle_g1b complete at", OUT_DIR, flush=True)


if __name__ == "__main__":
    main()
