#!/usr/bin/env python3
"""Validate SAM smoke results.json against the bundle contract (gate G0 dry-run check).

Checks:
  - every OK task x every prompt variant is present with >=1 candidate mask,
    OR is explicitly listed absent with a reason (no silent gaps);
  - every mask PNG exists and matches its viewport image dimensions;
  - every polygon round-trips px<->pdf within tolerance using transforms.json;
  - result rows carry the required schema fields.

Exit 0 = pass. Machine outputs only; this does not certify masks as truth.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

REQUIRED_ROW_FIELDS = ["task_id", "code", "page_index", "variant", "mask_index",
                       "mask_file", "sam_score", "area_px", "area_sf",
                       "mask_bbox_pdf", "polygon_px", "polygon_pdf"]
VARIANTS = ["point_only", "point_plus_negatives", "point_plus_box"]
TOL_PX = 0.01


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--results", required=True)
    args = ap.parse_args()

    tasks_doc = json.load(open(os.path.join(args.bundle, "tasks.json")))
    tr = json.load(open(os.path.join(args.bundle, "transforms.json")))
    res = json.load(open(os.path.join(args.results, "results.json")))
    per_task = tasks_doc.get("bundle_kind") == "per_task_crop_v1"
    if per_task:
        # G1b: transform (zoom/offset/size/ppf) keyed by task_id.
        task_tr = {tid: v for tid, v in tr["tasks"].items()}
        task_ppf = {t["task_id"]: t["transform"]["px_per_foot"]
                    for t in tasks_doc["tasks"] if t["status"] == "ok"}
    else:
        zoom = tr["zoom"]
        offsets = {int(k): v["pixel_offset_device"] for k, v in tr["pages"].items()}
        dims = {int(k): tuple(v["pixel_size"]) for k, v in tr["pages"].items()}  # (w,h)

    errors, checks = [], 0

    ok_tasks = [t for t in tasks_doc["tasks"] if t["status"] == "ok"]
    absent_tasks = [t for t in tasks_doc["tasks"] if t["status"] != "ok"]

    # 1. schema
    if res.get("schema") != "sam_smoke_results_v1":
        errors.append(f"bad result schema: {res.get('schema')}")

    # 2. every ok task x variant present
    seen = {}
    for r in res["results"]:
        seen.setdefault((r["task_id"], r["variant"]), 0)
        seen[(r["task_id"], r["variant"])] += 1
    for t in ok_tasks:
        for v in VARIANTS:
            checks += 1
            if seen.get((t["task_id"], v), 0) < 1:
                errors.append(f"missing masks for {t['task_id']} / {v}")

    # 3. absent tasks explicitly recorded with a reason
    absent_ids = {a["task_id"]: a.get("reason") for a in res.get("absent_tasks", [])}
    for t in absent_tasks:
        checks += 1
        if t["task_id"] not in absent_ids or not absent_ids[t["task_id"]]:
            errors.append(f"absent task not explicitly recorded with reason: {t['task_id']}")

    # 4. no stray masks for non-ok tasks
    ok_ids = {t["task_id"] for t in ok_tasks}
    for r in res["results"]:
        if r["task_id"] not in ok_ids:
            errors.append(f"mask row for non-ok task: {r['task_id']}")

    # 5. per-row: fields, mask file exists + dims, polygon round-trip
    for r in res["results"]:
        checks += 1
        for f in REQUIRED_ROW_FIELDS:
            if f not in r:
                errors.append(f"{r.get('task_id')}/{r.get('variant')}: missing field {f}")
        pi = r["page_index"]
        if per_task:
            tt = task_tr[r["task_id"]]
            r_zoom, (r_ox, r_oy), r_dims, r_ppf = (
                tt["zoom"], tt["offset"], tuple(tt["size"]), task_ppf[r["task_id"]])
        else:
            r_zoom, (r_ox, r_oy), r_dims, r_ppf = zoom, offsets[pi], dims[pi], 24.0
        mp = os.path.join(args.results, r["mask_file"])
        if not os.path.exists(mp):
            errors.append(f"mask file missing: {r['mask_file']}")
            continue
        w, h = Image.open(mp).size
        if (w, h) != r_dims:
            errors.append(f"{r['mask_file']}: dims {(w,h)} != image {r_dims}")
        # polygon round-trip px<->pdf
        for (px, py), (pdx, pdy) in zip(r["polygon_px"], r["polygon_pdf"]):
            rpx = pdx * r_zoom - r_ox
            rpy = pdy * r_zoom - r_oy
            if abs(rpx - px) > TOL_PX or abs(rpy - py) > TOL_PX:
                errors.append(f"{r['mask_file']}: polygon round-trip err "
                              f"({abs(rpx-px):.4f},{abs(rpy-py):.4f})px > {TOL_PX}")
                break
        # area sanity: SF must be non-negative and consistent with px at this ppf
        if r["area_px"] > 0:
            exp_sf = round(r["area_px"] / (r_ppf * r_ppf), 3)
            if abs(exp_sf - r["area_sf"]) > 0.02:
                errors.append(f"{r['mask_file']}: area_sf {r['area_sf']} != "
                              f"px/{r_ppf}^2 {exp_sf}")

    print(f"checks run: {checks}; ok tasks: {len(ok_tasks)}; absent: {len(absent_tasks)}; "
          f"masks: {len(res['results'])}")
    if errors:
        print(f"FAIL: {len(errors)} error(s)")
        for e in errors[:40]:
            print("  -", e)
        sys.exit(1)
    print("PASS: results.json valid against bundle contract")


if __name__ == "__main__":
    main()
