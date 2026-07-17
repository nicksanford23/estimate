#!/usr/bin/env python3
"""Build the zero-GPU SAM room-segmentation smoke bundle for 24-06748-RNVS (gate G0).

Local preparation ONLY. No GPU, no RunPod, no network, no secrets. Reads the
geometry annotation packet + source PDF and writes, under
data/sam_smoke/24-06748-RNVS/bundle/:

  - viewport_p5.png .. viewport_p8.png : each confirmed viewport clip rasterized
    at a FIXED physical resolution of 24 px/ft (zoom = 24/18 vs PDF points), RGB,
    no annotations burned in.
  - tasks.json    : 36 room prompt tasks, each with prompt variants (point,
    point+negatives, point+geometric box). Coordinates in BOTH pixel and PDF space.
  - transforms.json : per-page pdf<->pixel affine (+inverse) with a machine
    round-trip self-test the script asserts.
  - manifest.json : container image, SAM 2.1 checkpoint URLs (+sha256 placeholders),
    runner command, result schema version, runtime/budget caps, bundle file sha256s.

ANCHOR RULE (duplicate-tag disambiguation, verified visually on all 4 sheets):
Each scheduled room code often matches 2 words inside the viewport. One is the
ROOM-NUMBER TAG (stacked NAME / CODE / "## SF", placed inside the room) and the
other is a DOOR TAG in the pattern "<code> | <letters>" sitting on a door/wall.
The room tag is the hit with an "SF" area token directly below it; the door tag
is the hit whose immediate right neighbour is the pipe "|". We select the room
tag. This is geometry/text only and never reads the schedule area value.

Three page-6 rooms (210, 209A, 211) have NO extractable text; they were placed
by visual inspection of the master-suite band (see G0_REPORT.md). 210 could not
be resolved as a distinct room at drawing scale and is recorded status=no_anchor
(an explicit gap, never a guess).
"""
import hashlib
import json
import os
import random

import fitz
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
PDF_PATH = os.path.join(ROOT, "data", "render_cache", "pdf", "7372349.pdf")
PACKET = os.path.join(ROOT, "data", "geometry_annotations",
                      f"{PERMIT}.geometry_annotation_packet_v1.json")
OUT_DIR = os.path.join(ROOT, "data", "sam_smoke", PERMIT, "bundle")

PT_PER_FOOT = 18.0          # 1/4" = 1'-0" -> 18 pdf points per foot (verified)
PX_PER_FOOT = 24.0          # fixed physical raster resolution
ZOOM = PX_PER_FOOT / PT_PER_FOOT   # 4/3

# Visual-manual anchors for the three no-text page-6 rooms (pdf points, fitz y-down).
# Placed by iterated crop-and-look on sheet A102 master suite; see G0_REPORT.md.
VISUAL_ANCHORS = {
    "211": {"pdf": (2304.0, 1263.0), "confidence": "high",
            "note": "WC compartment (right side of master-suite band); toilet fixture visible."},
    "209A": {"pdf": (2188.0, 1275.0), "confidence": "medium",
             "note": "Left circulation compartment of master-suite band (door swing from closet 212)."},
    # 210 CLOSET (7 SF) intentionally absent -> resolved as no_anchor below.
}
NO_ANCHOR = {
    "210": "7 SF closet not separately resolvable from HALL 209A / TOILET 211 at "
           "drawing scale; no extractable text. Explicit gap, not a guess.",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def has_sf_below(hit, words):
    """True if an 'SF' area token sits directly below this word (room-tag signal)."""
    for o in words:
        if o[1] > hit[3] - 1 and o[1] - hit[3] < 34 and not (o[2] < hit[0] - 8 or o[0] > hit[2] + 8):
            if o[4].strip().upper() == "SF":
                return True
    return False


def right_is_pipe(hit, words):
    """True if the immediate same-line right neighbour is a pipe (door-tag signal)."""
    cy = (hit[1] + hit[3]) / 2
    same = [o for o in words if o is not hit and abs(((o[1] + o[3]) / 2) - cy) < 6 and o[0] >= hit[2] - 1]
    same.sort(key=lambda o: o[0])
    return bool(same) and same[0][4].strip() == "|"


def resolve_text_anchor(code, words):
    """Return (cx, cy, diag) for the room-tag hit, or None. diag records the rule."""
    hits = [w for w in words if w[4].strip() == code]
    if not hits:
        return None
    room_hits = [h for h in hits if has_sf_below(h, words)]
    diag = {"n_hits": len(hits),
            "hit_centroids": [[round((h[0] + h[2]) / 2, 2), round((h[1] + h[3]) / 2, 2)] for h in hits],
            "rejected_door_tags": [[round((h[0] + h[2]) / 2, 2), round((h[1] + h[3]) / 2, 2)]
                                   for h in hits if right_is_pipe(h, words)]}
    if len(room_hits) == 1:
        chosen = room_hits[0]
        diag["rule"] = "room_tag=has_SF_below; rejected door tag(s) had right-neighbour '|'"
    elif len(room_hits) == 0 and len(hits) == 1:
        chosen = hits[0]           # single hit fallback (all verified as room tags)
        diag["rule"] = "single_hit_fallback"
    elif len(room_hits) > 1:
        # deterministic tie-break: the hit with a name word directly above it
        def name_above(h):
            return any(o[3] < h[1] + 1 and h[1] - o[3] < 34 and not (o[2] < h[0] - 8 or o[0] > h[2] + 8)
                       and not o[4].strip().isdigit() for o in words)
        room_hits.sort(key=lambda h: (not name_above(h), (h[0] + h[2]) / 2))
        chosen = room_hits[0]
        diag["rule"] = "multi_SF_below; tie-break=name_above then leftmost"
    else:
        return None
    diag["chosen"] = [round((chosen[0] + chosen[2]) / 2, 2), round((chosen[1] + chosen[3]) / 2, 2)]
    return (chosen[0] + chosen[2]) / 2, (chosen[1] + chosen[3]) / 2, diag


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    packet = json.load(open(PACKET))
    tasks_in = packet["tasks"]

    # group tasks by page
    pages = {}
    for t in tasks_in:
        pages.setdefault(t["page_index"], []).append(t)

    transforms = {"schema": "sam_smoke_transforms_v1", "permit": PERMIT,
                  "pt_per_foot": PT_PER_FOOT, "px_per_foot": PX_PER_FOOT,
                  "zoom": ZOOM, "pages": {}}

    # ---- render each viewport & build per-page affine -------------------------------
    page_px = {}   # page_index -> (offset_x, offset_y, w_px, h_px)
    for pi, ptasks in sorted(pages.items()):
        page = doc[pi]
        vb = ptasks[0]["viewport_bbox_pdf"]
        # render full page at ZOOM; device pixel = pdf_pt * ZOOM (fitz top-left origin)
        pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            arr = arr[:, :, :3]
        # integer viewport pixel box (deterministic; offset is integer)
        x0 = int(round(vb["x"] * ZOOM))
        y0 = int(round(vb["y"] * ZOOM))
        w_px = int(round(vb["w"] * ZOOM))
        h_px = int(round(vb["h"] * ZOOM))
        clip = arr[y0:y0 + h_px, x0:x0 + w_px, :].copy()
        from PIL import Image
        Image.fromarray(clip, "RGB").save(os.path.join(OUT_DIR, f"viewport_p{pi}.png"))
        page_px[pi] = (x0, y0, clip.shape[1], clip.shape[0])
        transforms["pages"][str(pi)] = {
            "sheet_number": ptasks[0]["sheet_number"],
            "viewport_bbox_pdf": vb,
            "pixel_size": [clip.shape[1], clip.shape[0]],
            "pixel_offset_device": [x0, y0],
            # forward:  px = pdf * zoom - offset ;  inverse: pdf = (px + offset) / zoom
            "forward_affine": {"px_x": [ZOOM, 0.0, -x0], "px_y": [0.0, ZOOM, -y0]},
            "inverse_affine": {"pdf_x": [1.0 / ZOOM, 0.0, x0 / ZOOM],
                               "pdf_y": [0.0, 1.0 / ZOOM, y0 / ZOOM]},
            "image": f"viewport_p{pi}.png",
        }
        print(f"page {pi} {ptasks[0]['sheet_number']}: viewport {clip.shape[1]}x{clip.shape[0]}px "
              f"offset=({x0},{y0})", flush=True)

    def pdf_to_px(pi, x, y):
        x0, y0, _, _ = page_px[pi]
        return (x * ZOOM - x0, y * ZOOM - y0)

    def px_to_pdf(pi, px, py):
        x0, y0, _, _ = page_px[pi]
        return ((px + x0) / ZOOM, (py + y0) / ZOOM)

    # ---- machine round-trip self-test ----------------------------------------------
    rng = random.Random(42)
    max_err = 0.0
    for pi in page_px:
        _, _, wpx, hpx = page_px[pi]
        for _ in range(2000):
            px, py = rng.uniform(0, wpx), rng.uniform(0, hpx)
            x, y = px_to_pdf(pi, px, py)
            bx, by = pdf_to_px(pi, x, y)
            max_err = max(max_err, abs(bx - px), abs(by - py))
    assert max_err < 0.01, f"round-trip error too large: {max_err}"
    transforms["roundtrip_selftest"] = {"n_points_per_page": 2000, "max_error_px": max_err,
                                        "tolerance_px": 0.01, "passed": True}
    print(f"round-trip self-test: max_err={max_err:.3e}px < 0.01  OK", flush=True)

    # ---- resolve anchors ------------------------------------------------------------
    anchors = {}   # task_id -> dict(status, code, page, pdf, px, provenance, confidence, diag)
    for pi, ptasks in sorted(pages.items()):
        page = doc[pi]
        vb = ptasks[0]["viewport_bbox_pdf"]
        vx0, vy0, vx1, vy1 = vb["x"], vb["y"], vb["x"] + vb["w"], vb["y"] + vb["h"]
        words = [w for w in page.get_text("words")
                 if w[0] >= vx0 and w[2] <= vx1 and w[1] >= vy0 and w[3] <= vy1]
        for t in ptasks:
            code = t["space"]["code"]
            tid = t["task_id"]
            if code in NO_ANCHOR:
                anchors[tid] = {"status": "no_anchor", "code": code, "page_index": pi,
                                "provenance": "none", "reason": NO_ANCHOR[code]}
                continue
            if code in VISUAL_ANCHORS:
                x, y = VISUAL_ANCHORS[code]["pdf"]
                anchors[tid] = {"status": "ok", "code": code, "page_index": pi,
                                "pdf": [x, y], "px": list(pdf_to_px(pi, x, y)),
                                "provenance": "visual_manual",
                                "confidence": VISUAL_ANCHORS[code]["confidence"],
                                "diag": {"note": VISUAL_ANCHORS[code]["note"]}}
                continue
            res = resolve_text_anchor(code, words)
            if res is None:
                anchors[tid] = {"status": "no_anchor", "code": code, "page_index": pi,
                                "provenance": "none",
                                "reason": "no matching word inside viewport"}
                continue
            x, y, diag = res
            anchors[tid] = {"status": "ok", "code": code, "page_index": pi,
                            "pdf": [round(x, 3), round(y, 3)], "px": list(pdf_to_px(pi, x, y)),
                            "provenance": "pdf_text", "confidence": "high", "diag": diag}

    # ---- build tasks with prompt variants ------------------------------------------
    def nearest_neighbor_ft(pi, code, x, y):
        best = None
        for tid2, a2 in anchors.items():
            if a2["status"] != "ok" or a2["page_index"] != pi or a2["code"] == code:
                continue
            ax, ay = a2["pdf"]
            d = ((ax - x) ** 2 + (ay - y) ** 2) ** 0.5 / PT_PER_FOOT
            if best is None or d < best:
                best = d
        return best

    tasks_out = []
    for t in tasks_in:
        tid = t["task_id"]
        code = t["space"]["code"]
        pi = t["page_index"]
        a = anchors[tid]
        row = {"task_id": tid, "page_index": pi, "sheet_number": t["sheet_number"],
               "level": t["level"], "code": code, "space_name": t["space"]["name"],
               "viewport_image": f"viewport_p{pi}.png",
               "anchor_provenance": a["provenance"], "status": a["status"]}
        if a["status"] != "ok":
            row["reason"] = a.get("reason")
            row["prompt_variants"] = {}
            tasks_out.append(row)
            continue
        row["anchor_confidence"] = a["confidence"]
        row["anchor_diag"] = a["diag"]
        px, py = a["px"]
        pdfx, pdfy = a["pdf"]
        row["anchor_pdf"] = [round(pdfx, 3), round(pdfy, 3)]
        row["anchor_px"] = [round(px, 3), round(py, 3)]

        # negatives = every OTHER ok anchor on this page
        negs_px, negs_pdf, negs_code = [], [], []
        for t2 in tasks_in:
            if t2["page_index"] != pi or t2["task_id"] == tid:
                continue
            a2 = anchors[t2["task_id"]]
            if a2["status"] != "ok":
                continue
            negs_px.append([round(a2["px"][0], 3), round(a2["px"][1], 3)])
            negs_pdf.append([round(a2["pdf"][0], 3), round(a2["pdf"][1], 3)])
            negs_code.append(a2["code"])

        # geometric box: half-size = clamp(1.4 * nearest-neighbour dist, 6ft, 40ft)
        nn_ft = nearest_neighbor_ft(pi, code, pdfx, pdfy)
        hs_ft = 20.0 if nn_ft is None else min(40.0, max(6.0, 1.4 * nn_ft))
        hs_pt = hs_ft * PT_PER_FOOT
        vb = t["viewport_bbox_pdf"]
        bx0 = max(vb["x"], pdfx - hs_pt); by0 = max(vb["y"], pdfy - hs_pt)
        bx1 = min(vb["x"] + vb["w"], pdfx + hs_pt); by1 = min(vb["y"] + vb["h"], pdfy + hs_pt)
        box_pdf = [round(bx0, 3), round(by0, 3), round(bx1, 3), round(by1, 3)]
        p0 = pdf_to_px(pi, bx0, by0); p1 = pdf_to_px(pi, bx1, by1)
        box_px = [round(p0[0], 3), round(p0[1], 3), round(p1[0], 3), round(p1[1], 3)]

        row["prompt_variants"] = {
            "point_only": {
                "positive_points_px": [[round(px, 3), round(py, 3)]],
                "positive_points_pdf": [[round(pdfx, 3), round(pdfy, 3)]],
                "negative_points_px": [], "box_px": None,
            },
            "point_plus_negatives": {
                "positive_points_px": [[round(px, 3), round(py, 3)]],
                "positive_points_pdf": [[round(pdfx, 3), round(pdfy, 3)]],
                "negative_points_px": negs_px,
                "negative_points_pdf": negs_pdf,
                "negative_codes": negs_code,
                "box_px": None,
            },
            "point_plus_box": {
                "positive_points_px": [[round(px, 3), round(py, 3)]],
                "positive_points_pdf": [[round(pdfx, 3), round(pdfy, 3)]],
                "negative_points_px": [],
                "box_px": box_px, "box_pdf": box_pdf,
                "box_provenance": "geometry_only",
                "box_half_size_ft": round(hs_ft, 3),
                "box_nearest_neighbor_ft": None if nn_ft is None else round(nn_ft, 3),
            },
        }
        tasks_out.append(row)

    ok = sum(1 for r in tasks_out if r["status"] == "ok")
    by_prov = {}
    for r in tasks_out:
        by_prov[r["anchor_provenance"]] = by_prov.get(r["anchor_provenance"], 0) + 1
    tasks_doc = {"schema": "sam_smoke_tasks_v1", "permit": PERMIT,
                 "source_packet": os.path.relpath(PACKET, ROOT),
                 "anchor_rule": "room_tag = code word with 'SF' token directly below; "
                                "door tag (right-neighbour '|') rejected. Schedule AREA VALUE never read.",
                 "px_per_foot": PX_PER_FOOT,
                 "counts": {"total": len(tasks_out), "ok": ok, "no_anchor": len(tasks_out) - ok,
                            "by_provenance": by_prov},
                 "tasks": tasks_out}

    json.dump(tasks_doc, open(os.path.join(OUT_DIR, "tasks.json"), "w"), indent=2)
    json.dump(transforms, open(os.path.join(OUT_DIR, "transforms.json"), "w"), indent=2)
    print(f"tasks: {ok}/{len(tasks_out)} anchored; by provenance {by_prov}", flush=True)

    # ---- manifest ------------------------------------------------------------------
    bundle_files = ["tasks.json", "transforms.json"] + [f"viewport_p{pi}.png" for pi in sorted(pages)]
    file_hashes = {fn: {"sha256": sha256_file(os.path.join(OUT_DIR, fn)),
                        "bytes": os.path.getsize(os.path.join(OUT_DIR, fn))} for fn in bundle_files}
    manifest = {
        "schema": "sam_smoke_manifest_v1",
        "permit": PERMIT,
        "gate": "G0",
        "purpose": "SAM 2.1 zero-shot room-segmentation smoke test (annotation-assistant probe). "
                   "Machine proposals only; not human truth; cannot promote SAM to production.",
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
        "runner_command": "python scripts/sam_smoke_runner.py --bundle data/sam_smoke/24-06748-RNVS/bundle "
                          "--out data/sam_smoke/24-06748-RNVS/results --checkpoint <sam2.1_hiera_small.pt> "
                          "--model-cfg configs/sam2.1/sam2.1_hiera_s.yaml",
        "runner_fake_command": "python scripts/sam_smoke_runner.py --bundle data/sam_smoke/24-06748-RNVS/bundle "
                               "--out data/sam_smoke/24-06748-RNVS/results --fake",
        "result_schema_version": "sam_smoke_results_v1",
        "max_runtime_minutes": 60,
        "budget_cap_usd": 2,
        "px_per_foot": PX_PER_FOOT,
        "pt_per_foot": PT_PER_FOOT,
        "selection_policy": "NONE. Every candidate mask + score is saved. Choosing a winner by "
                            "closeness to schedule area is forbidden (lock).",
        "bundle_files": file_hashes,
        "anchor_summary": {"total_tasks": len(tasks_out), "anchored": ok,
                           "by_provenance": by_prov},
    }
    json.dump(manifest, open(os.path.join(OUT_DIR, "manifest.json"), "w"), indent=2)
    print("wrote manifest.json; bundle complete at", OUT_DIR, flush=True)


if __name__ == "__main__":
    main()
