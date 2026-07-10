#!/usr/bin/env python3
"""Probe 30 follow-up -- DUAL-engine canary SMOKE TEST (not a grade): bank p3
(14-11290-NEWC doc 1494156) + hotel p9 (17-35590-RNVS doc 3523243) through
BOTH engines + takeoff.reconcile_dual_engines (the same function `takeoff.py
run --engine dual` uses). Pass bar: no crash, sane bounds, and NO REGRESSION
vs the rules-v4 canary numbers (dual's auto-eligible room set must not lose
v4 rooms -- rescued/demoted polygons only ever ADD review candidates).

Note these two pages route to the LAYER path inside takeoff.py proper (so
`run` never runs dual on them) -- this exercises the dual rules-path
machinery on them directly, as the probe29/probe30 canaries did for v4/model.

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

import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, find_scale, extract_drawings, extract_dim_words,
)
from geometry_v4 import run_geometry_engine_v4  # noqa: E402
from geometry_model import run_geometry_engine_model  # noqa: E402
from probe4_room_sf import ROOMS as BANK_ROOMS  # noqa: E402
import takeoff  # noqa: E402

OUT_DIR = os.path.join(ROOT, "data", "probe30", "canary")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp_dual")
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
        if t.isdigit() and int(t) in BANK_ROOMS and t not in anchors:
            anchors[t] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
    doc.close()
    return anchors


def hotel_anchors(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    anchors = defaultdict(list)
    for w in page.get_text("words"):
        m = KEYNOTE_RE.match(w[4].strip())
        if m:
            anchors[m.group(1)].append(((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
    doc.close()
    return dict(anchors)


def run_canary(s3, clf, threshold, doc_id, page_index, name, anchor_fn):
    print(f"\n{'=' * 70}\n{name} canary (doc {doc_id} p{page_index}) [DUAL]\n{'=' * 70}")
    pdf = download_pdf(s3, doc_id)
    result = dict(name=name, doc_id=doc_id, page_index=page_index)
    try:
        fpp, scale_text = find_scale(doc_id, page_index)
        if fpp is None:
            result["verdict"] = "scale_unverified"
            return result
        anchors = anchor_fn(pdf, page_index)
        anchor_points = [pt for pts in anchors.values()
                          for pt in (pts if isinstance(pts, list) else [pts])]

        extracted = extract_drawings(pdf, page_index)
        out4, diag4 = run_geometry_engine_v4(extracted, fpp, anchor_points)
        outm, diagm = run_geometry_engine_model(pdf, page_index, clf, fpp,
                                                 anchor_points, threshold=threshold)
        rooms4 = out4["rooms_all"] if out4 else []
        roomsm = outm["rooms_all"] if outm else []
        dim_words = extract_dim_words(pdf, page_index)
        final_polys, poly_engine, poly_notes, recon = takeoff.reconcile_dual_engines(
            "v4", rooms4, "model", roomsm, anchors, fpp, dim_words=dim_words)

        auto_eligible = [i for i, n in enumerate(poly_notes) if not n]
        total_sf = sum(final_polys[i].area * fpp ** 2 for i in auto_eligible)
        n_v4_kept = sum(1 for i in auto_eligible if poly_engine[i] in ("v4", "both"))
        result.update(
            verdict="ran_ok",
            reconcile={k: v for k, v in recon.items() if k != "principal_region"},
            n_rooms_v4=len(rooms4), n_rooms_model=len(roomsm),
            n_polys_final=len(final_polys),
            n_auto_eligible=len(auto_eligible),
            n_v4_polys_kept_auto_eligible=n_v4_kept,
            n_review_flagged=len(final_polys) - len(auto_eligible),
            auto_eligible_total_sf=round(total_sf, 1),
            sane=(0 < len(final_polys) < 500) and (0 < total_sf < 500000),
            v4_room_loss=(recon["winner"] == "v4" and
                           len(auto_eligible) + recon["n_winner_quality_demoted"]
                           + recon["n_disagree_demoted"] < len(rooms4)),
        )
        print(json.dumps({k: result[k] for k in ("verdict", "reconcile", "n_rooms_v4",
                                                  "n_rooms_model", "n_polys_final",
                                                  "n_auto_eligible", "n_review_flagged",
                                                  "auto_eligible_total_sf", "sane")},
                          indent=1, default=str))
    except Exception as e:
        import traceback
        result["verdict"] = "CRASH"
        result["error"] = str(e)
        traceback.print_exc()
    finally:
        p = os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf")
        if os.path.exists(p):
            os.remove(p)
    return result


def main():
    clf = joblib.load(MODEL_PATH)
    threshold = json.load(open(SEG_RESULTS))["fixed_model"]["canonical_threshold"]
    s3 = r2_client()
    bank = run_canary(s3, clf, threshold, BANK_DOC, BANK_PAGE, "bank", bank_anchors)
    hotel = run_canary(s3, clf, threshold, HOTEL_DOC, HOTEL_PAGE, "hotel", hotel_anchors)
    with open(os.path.join(OUT_DIR, "canary_dual_results.json"), "w") as f:
        json.dump(dict(bank=bank, hotel=hotel), f, indent=2, default=str)
    print("\n=== DUAL CANARY VERDICTS ===")
    for n, r in (("bank", bank), ("hotel", hotel)):
        print(n, r.get("verdict"), "sane=" + str(r.get("sane")))
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass


if __name__ == "__main__":
    main()
