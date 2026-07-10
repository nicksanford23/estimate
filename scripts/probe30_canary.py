#!/usr/bin/env python3
"""Probe 30 Phase 3.5 -- canary SMOKE TEST (not a grade): bank p3 (14-11290-
NEWC, doc 1494156, page 3) + hotel p9 (17-35590-RNVS, doc 3523243, page 9)
through the MODEL-AS-ENGINE path. These pages carry real wall LAYERS (used
elsewhere as rules-path ground truth / regression canaries) -- here they are
just a structural stress test for the model path: no crash, sane room count/
SF, and (bonus, not required) how many of the known room-number anchors the
model-engine's rooms happen to contain.

Deletes fetched PDFs after use.
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joblib  # noqa: E402
import fitz  # noqa: E402
from shapely.geometry import Point  # noqa: E402

import probe2_sf  # noqa: E402
from probe2_sf import ROOT, r2_client, download_pdf, find_scale  # noqa: E402
from geometry_model import run_geometry_engine_model  # noqa: E402
from probe4_room_sf import ROOMS as BANK_ROOMS  # noqa: E402

OUT_DIR = os.path.join(ROOT, "data", "probe30", "canary")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR

BANK_DOC, BANK_PAGE = 1494156, 3
HOTEL_DOC, HOTEL_PAGE = 3523243, 9
KEYNOTE_RE = re.compile(r"^(\d{3})\.\d+$")

MODEL_PATH = os.path.join(ROOT, "models", "wall_model_v2.joblib")
SEG_RESULTS = os.path.join(ROOT, "data", "probe30", "segment_results.json")


def bank_anchors(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    anchors = {}
    for w in page.get_text("words"):
        t = w[4].strip()
        if t.isdigit() and int(t) in BANK_ROOMS and int(t) not in anchors:
            anchors[int(t)] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
    doc.close()
    return anchors


def hotel_anchors(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    anchors = defaultdict(list)
    for w in page.get_text("words"):
        t = w[4].strip()
        m = KEYNOTE_RE.match(t)
        if m:
            anchors[m.group(1)].append(((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
    doc.close()
    return anchors


def anchors_hit(rooms, anchors_dict):
    hit = defaultdict(set)
    for tok, pts in anchors_dict.items():
        pts = pts if isinstance(pts, list) else [pts]
        for (x, y) in pts:
            p = Point(x, y)
            for i, poly in enumerate(rooms):
                if poly.contains(p):
                    hit[i].add(tok)
                    break
    return hit


def run_canary(s3, clf, threshold, doc_id, page_index, name, anchor_fn):
    print(f"\n{'='*70}\n{name} canary (doc {doc_id} p{page_index}) [MODEL engine]\n{'='*70}")
    pdf = download_pdf(s3, doc_id)
    result = dict(name=name, doc_id=doc_id, page_index=page_index)
    try:
        fpp, scale_text = find_scale(doc_id, page_index)
        result["scale_text"] = scale_text
        if fpp is None:
            result["verdict"] = "scale_unverified"
            print("  NO SCALE FOUND -- smoke test cannot proceed")
            return result

        anchors = anchor_fn(pdf, page_index)
        anchor_points = [pt for pts in anchors.values() for pt in (pts if isinstance(pts, list) else [pts])]
        print(f"  scale={scale_text}  n_anchors={len(anchors)}")

        out, diag = run_geometry_engine_model(pdf, page_index, clf, fpp, anchor_points, threshold=threshold)
        result["diag"] = {k: v for k, v in diag.items()
                           if k not in ("anchor_cluster_false_positive_suspects",)}
        if out is None:
            result["verdict"] = diag.get("verdict", "no_rooms")
            print(f"  NO ROOMS CLOSED: {diag.get('reason')}")
            return result

        rooms = out["rooms_all"]
        total_sf = sum(p.area * fpp ** 2 for p in rooms)
        hit = anchors_hit(rooms, anchors)
        n_anchors_matched = len(set().union(*hit.values())) if hit else 0
        result.update(verdict="ran_ok", n_rooms=len(rooms), total_sf=round(total_sf, 1),
                      n_anchored_polys=len(hit), n_anchors_matched=n_anchors_matched,
                      n_anchors_total=len(anchors))
        print(f"  RAN OK: n_rooms={len(rooms)} total_sf={total_sf:.0f} "
              f"anchors_matched={n_anchors_matched}/{len(anchors)}")
        # sanity: no crash + room count/SF in a plausible band
        result["sane"] = (0 < len(rooms) < 500) and (0 < total_sf < 500000)
    except Exception as e:
        result["verdict"] = "CRASH"
        result["error"] = str(e)
        print(f"  CRASHED: {e}")
    finally:
        p = os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf")
        if os.path.exists(p):
            os.remove(p)
    return result


def main():
    clf = joblib.load(MODEL_PATH)
    seg_results = json.load(open(SEG_RESULTS))
    threshold = seg_results["fixed_model"]["canonical_threshold"]

    s3 = r2_client()
    bank = run_canary(s3, clf, threshold, BANK_DOC, BANK_PAGE, "bank", bank_anchors)
    hotel = run_canary(s3, clf, threshold, HOTEL_DOC, HOTEL_PAGE, "hotel", hotel_anchors)

    with open(os.path.join(OUT_DIR, "canary_model_results.json"), "w") as f:
        json.dump(dict(bank=bank, hotel=hotel), f, indent=2, default=str)

    print("\n=== CANARY SMOKE TEST VERDICTS (model engine) ===")
    print("bank:", bank.get("verdict"), "sane=" + str(bank.get("sane")))
    print("hotel:", hotel.get("verdict"), "sane=" + str(hotel.get("sane")))


if __name__ == "__main__":
    main()
