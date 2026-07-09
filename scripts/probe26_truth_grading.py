#!/usr/bin/env python3
"""Probe 26 -- grade the RULES geometry path (probe2_sf/probe2b_sf lineage,
UNCHANGED engine: wall-candidate filter -> hatch suppression -> snap_and_close
-> polygonize, no layers) against the four truth_area answer-key permits.

Adaptations made EXPLICIT here (none touch the geometry engine itself):
  1. Room-number ANCHORING: instead of a generic room-number regex, each
     target page is searched for EXACT-STRING matches of the room codes
     already present in that permit's truth-key `rooms[].room` field
     (e.g. "B101", "A-101", "208"). This is what "match polygon->schedule
     row by room number" means once you actually have the schedule. A
     generic regex would also work but would need per-permit tuning
     (building-prefixed vs hyphenated vs plain-digit codes) -- tuning the
     MATCHER, not the geometry engine, is in scope and expected.
  2. NO "keep only the largest wall-graph cluster" step. probe2b/probe3
     assume one building per sheet and discard every cluster but the
     biggest (their `main_cluster` idea, meant to drop stray same-sheet
     detail blowups). Three of these four permits are explicitly
     MULTI-UNIT/MULTI-BUILDING SHEETS (24-06233 shows Buildings B+C
     together, 26-05332 shows Units A-D together, 20-29653 shows two
     units per floor together) -- each unit/building is its OWN
     legitimate, correctly-disconnected wall graph. Discarding all but
     the largest would silently zero out 50-75% of the addressable
     rooms before matching even starts. Every room-sized polygon
     (`polygonize_rooms` output, unfiltered by cluster) is a matching
     candidate; `cluster_by_touching` is used only for overlay grouping/
     diagnostics, never to drop polygons.
Everything else (wall_candidates two-tier filter, suppress_hatches_v2,
find_parallel_pairs, admit_minor, snap_and_close, polygonize_rooms, the
scale self-audit, build_grading_table) is imported and called exactly as
in probe2b_sf.py / probe3_sf.py.

Deletes fetched PDFs after use.
"""
import json
import os
import re
import statistics
import sys
from collections import defaultdict

import fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, extract_drawings, snap_and_close,
    polygonize_rooms, cluster_by_touching, find_scale, extract_dim_words,
    parse_ft_in,
)
from probe2b_sf import (  # noqa: E402
    two_tier_wall_candidates, find_parallel_pairs, admit_minor,
    build_grading_table,
)

TRUTH_DIR = os.path.join(ROOT, "data", "triage", "truth_area")
OUT_DIR = os.path.join(ROOT, "data", "probe26")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR  # so download_pdf() writes/cleans here

MERGE_OK_TOL = 0.15  # open-plan grouping is fine if blob sums to truth within 15%

# ---------------------------------------------------------------- config --
# Per permit: which page(s) address which truth rooms, and how a room's
# `room` (+ optional unit/building) truth key maps to the exact page-text
# token we search for.

PERMITS = [
    dict(
        permit="24-06233-RNVS", doc_id=6799291, truth="24-06233-RNVS.json",
        pages=[dict(page_index=10, sheet="A2.2 PROPOSED PLAN - BUILDING B, C")],
        room_token=lambda r: r["room"],                 # "B101", "C102B"
        page_for_room=lambda r: (6799291, 10),
        addressable=lambda r: r.get("building") in ("B", "C"),
        not_addressable_reason="no floor-plan sheet for Building {b} in this "
                                "document (doc 6799291 only contains Building "
                                "C architecturals + the B/C combined plan on "
                                "p10; Buildings A/D/F appear ONLY in the "
                                "finish schedule, likely covered by sibling "
                                "permits 24-06231/24-06235/24-06239-RNVS)",
        not_addressable_key=lambda r: r.get("building"),
    ),
    dict(
        permit="20-29653-RNVS", doc_id=None, truth="20-29653-RNVS.json",
        pages=[
            dict(page_index=0, doc_id=4941399, sheet="2nd floor plan.pdf"),
            dict(page_index=0, doc_id=4941401, sheet="3rd floor plan.pdf"),
        ],
        room_token=lambda r: r["room"],                  # "200", "300A"
        page_for_room=lambda r: ((4941399, 0) if r["room"][0] == "2" else
                                  (4941401, 0) if r["room"][0] == "3" else None),
        addressable=lambda r: r.get("unit") in ("1510B", "1514"),
        not_addressable_reason="no floor-plan document exists for unit {b} in "
                                "this permit's document set at all (only "
                                "'2nd floor plan.pdf' + '3rd floor plan.pdf' "
                                "exist, covering 1510B+1514; ground-floor "
                                "units 1510A/1512 have NO 1st-floor-plan doc)",
        not_addressable_key=lambda r: r.get("unit"),
    ),
    dict(
        permit="24-06748-RNVS", doc_id=7372349, truth="24-06748-RNVS.json",
        pages=[
            dict(page_index=5, sheet="A101 1ST FLOOR"),
            dict(page_index=6, sheet="A102 2ND FLOOR"),
            dict(page_index=7, sheet="A103 3RD FLOOR"),
            dict(page_index=8, sheet="A104 4TH AND 5TH FLOOR"),
        ],
        room_token=lambda r: r["room"],                   # "101", "405"
        page_for_room=lambda r: (7372349, {"01 LEVEL": 5, "02 LEVEL": 6,
                                  "03 LEVEL": 7, "04 LEVEL": 8}.get(r["level"])),
        addressable=lambda r: True,
        not_addressable_reason="", not_addressable_key=lambda r: None,
    ),
    dict(
        permit="26-05332-NEWC", doc_id=8929774, truth="26-05332-NEWC.json",
        pages=[dict(page_index=8, sheet="A2.1 FLOOR PLANS - PROPOSED")],
        room_token=lambda r: r["room"],                    # "A-101"
        page_for_room=lambda r: (8929774, 8),
        addressable=lambda r: True,
        not_addressable_reason="", not_addressable_key=lambda r: None,
    ),
]


def font(sz):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def load_truth(fname):
    return json.load(open(os.path.join(TRUTH_DIR, fname)))


def run_geometry_engine(pdf_path, page_index):
    """probe2b_sf's two-tier engine, called exactly as in probe2b_sf.py /
    probe3_sf.py -- no per-page tuning. Returns ALL room-sized polygons on
    the page (no cluster-dropping; see module docstring point 2)."""
    feet_per_pt = None
    extracted = extract_drawings(pdf_path, page_index)
    pw, ph = extracted["pw"], extracted["ph"]

    doc_id_for_scale = int(os.path.splitext(os.path.basename(pdf_path))[0])
    feet_per_pt, scale_text = find_scale(doc_id_for_scale, page_index)

    diag = dict(scale_text=scale_text, feet_per_pt=feet_per_pt)
    if feet_per_pt is None:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = "no scale note found in page text"
        return None, diag

    tiers = two_tier_wall_candidates(extracted, feet_per_pt)
    major_clean, minor_clean = tiers["major"], tiers["minor"]
    combined_clean = major_clean + minor_clean
    pairs = find_parallel_pairs(combined_clean, feet_per_pt)
    pair_member_segs = set()
    for a, b, *_ in pairs:
        pair_member_segs.add(a)
        pair_member_segs.add(b)

    centerlines, seen_keys = [], set()
    for a, b, horiz, lo, hi, c in pairs:
        p0, p1 = ((lo, c), (hi, c)) if horiz else ((c, lo), (c, hi))
        key = (horiz, round(c / 2.0), round(lo / 3.0), round(hi / 3.0))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        centerlines.append((p0, p1, hi - lo, 0.3))

    minor_unpaired = [s for s in minor_clean if s not in pair_member_segs]
    seed = major_clean + centerlines
    walls_final, n_added, n_left = admit_minor(seed, minor_unpaired, pw)

    lines_ls, gap_info = snap_and_close(walls_final, extracted["arcs"], pw, feet_per_pt=None)

    min_sqft, max_sqft = 15, 5000
    rooms_all, n_faces = polygonize_rooms(lines_ls, pw, ph, min_sqft, max_sqft, feet_per_pt)

    diag.update(
        n_major_clean=len(major_clean), n_minor_clean=len(minor_clean),
        n_parallel_pairs=len(pairs), n_minor_admitted=n_added,
        n_polygon_faces_total=n_faces, n_rooms_all=len(rooms_all),
        dominant_angle_deg=round(tiers["dom"], 3),
    )
    if not rooms_all:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = "no room-sized polygons closed at all"
        return None, diag

    largest_sqft = max(p.area * feet_per_pt ** 2 for p in rooms_all)
    total_sqft = sum(p.area * feet_per_pt ** 2 for p in rooms_all)
    audit_ok = 30 <= largest_sqft <= 10000 and 30 <= total_sqft <= 200000
    diag.update(largest_room_sqft=round(largest_sqft, 1),
                total_sqft_all_polys=round(total_sqft, 1), audit_ok=audit_ok)
    if not audit_ok:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = f"self-audit failed: largest={largest_sqft:.0f} total={total_sqft:.0f}"
        return None, diag

    diag["verdict"] = "engine_ok"
    return dict(rooms_all=rooms_all, extracted=extracted, feet_per_pt=feet_per_pt,
                lines_ls=lines_ls), diag


def find_room_anchors(pdf_path, page_index, target_tokens):
    """Exact-string match of room-code tokens against page word text.
    Returns {token: [(x,y), ...]} for tokens actually found on the page."""
    doc = fitz.open(pdf_path)
    pg = doc[page_index]
    words = pg.get_text("words")
    doc.close()
    hits = defaultdict(list)
    tokset = set(target_tokens)
    for w in words:
        t = w[4].strip()
        if t in tokset:
            hits[t].append(((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
    return hits


def grade_page(rooms_all, feet_per_pt, anchors, truth_rooms_for_page):
    """anchors: {token: [(x,y)]}. truth_rooms_for_page: list of truth room
    dicts whose room_token should be looked up on this page."""
    truth_by_token = {}
    for r in truth_rooms_for_page:
        truth_by_token[r["_token"]] = r

    poly_hits = defaultdict(set)   # poly_idx -> {tokens}
    ambiguous = {}                 # token -> [poly_idxs]
    not_in_any_poly = set()

    for token in truth_by_token:
        pts = anchors.get(token)
        if not pts:
            continue  # handled as NOT_ON_PAGE by caller
        hit_polys = set()
        for (x, y) in pts:
            p = Point(x, y)
            for i, poly in enumerate(rooms_all):
                if poly.contains(p):
                    hit_polys.add(i)
                    break
        if not hit_polys:
            not_in_any_poly.add(token)
        elif len(hit_polys) == 1:
            poly_hits[next(iter(hit_polys))].add(token)
        else:
            ambiguous[token] = sorted(hit_polys)
            poly_hits[sorted(hit_polys)[0]].add(token)

    rows = []
    for poly_idx, tokens in poly_hits.items():
        poly = rooms_all[poly_idx]
        sqft = poly.area * feet_per_pt ** 2
        tokens = sorted(tokens)
        if len(tokens) == 1:
            tr = truth_by_token[tokens[0]]
            truth_sf = tr["area_sf"]
            if truth_sf is None:
                rows.append(dict(kind="MATCHED_NO_AREA", tokens=tokens, poly_idx=poly_idx,
                                  computed_sqft=round(sqft, 1)))
                continue
            pct_err = round(100 * (sqft - truth_sf) / truth_sf, 1) if truth_sf else None
            rows.append(dict(kind="MATCHED", tokens=tokens, poly_idx=poly_idx,
                              computed_sqft=round(sqft, 1), truth_sqft=truth_sf,
                              pct_error=pct_err))
        else:
            truth_sum = sum((truth_by_token[t]["area_sf"] or 0) for t in tokens)
            pct_err = round(100 * (sqft - truth_sum) / truth_sum, 1) if truth_sum else None
            ok = truth_sum > 0 and abs(sqft - truth_sum) / truth_sum <= MERGE_OK_TOL
            rows.append(dict(kind="MERGED_OK" if ok else "MERGED_ERROR", tokens=tokens,
                              poly_idx=poly_idx, computed_sqft=round(sqft, 1),
                              truth_sqft_sum=round(truth_sum, 1), pct_error=pct_err))

    for token in not_in_any_poly:
        rows.append(dict(kind="MISSED_NO_POLYGON", tokens=[token], poly_idx=None,
                          truth_sqft=truth_by_token[token]["area_sf"]))

    tokens_found_on_page = set(anchors.keys()) & set(truth_by_token.keys())
    for token, tr in truth_by_token.items():
        if token not in tokens_found_on_page:
            rows.append(dict(kind="NOT_ON_PAGE", tokens=[token], poly_idx=None,
                              truth_sqft=tr["area_sf"]))

    unlabeled_polys = [i for i in range(len(rooms_all)) if i not in poly_hits]
    return rows, unlabeled_polys, ambiguous


def render_overlay(pdf_path, page_index, rooms_all, feet_per_pt, rows, out_path, unlabeled_polys):
    doc = fitz.open(pdf_path)
    pg = doc[page_index]
    Z = 1800 / pg.rect.width
    pm = pg.get_pixmap(matrix=fitz.Matrix(Z, Z))
    img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(overlay)
    fnt = font(14)

    color = dict(MATCHED=(0, 160, 0, 100), MATCHED_NO_AREA=(0, 160, 0, 100),
                 MERGED_OK=(0, 90, 200, 100), MERGED_ERROR=(220, 130, 0, 110))
    for row in rows:
        if row["poly_idx"] is None:
            continue
        poly = rooms_all[row["poly_idx"]]
        pts = [(x * Z, y * Z) for x, y in poly.exterior.coords]
        c = color.get(row["kind"], (150, 150, 150, 90))
        dd.polygon(pts, fill=c, outline=(0, 0, 0, 255))
        cen = poly.centroid
        label = "+".join(row["tokens"])
        sf = row.get("computed_sqft")
        dd.text((cen.x * Z, cen.y * Z), f"{label}\n{sf:.0f}sf" if sf else label,
                 fill=(0, 0, 0, 255), font=fnt)

    for i in unlabeled_polys:
        poly = rooms_all[i]
        pts = [(x * Z, y * Z) for x, y in poly.exterior.coords]
        dd.polygon(pts, fill=(200, 0, 0, 70), outline=(150, 0, 0, 255))
        cen = poly.centroid
        sqft = poly.area * feet_per_pt ** 2
        dd.text((cen.x * Z, cen.y * Z), f"UNLBL {sqft:.0f}sf", fill=(120, 0, 0, 255), font=fnt)

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(out_path)
    doc.close()


def process_permit(s3, cfg):
    permit = cfg["permit"]
    truth = load_truth(cfg["truth"])
    print(f"\n{'=' * 70}\n{permit}\n{'=' * 70}")

    # tag every truth room with its target page + not-addressable status
    for r in truth["rooms"]:
        r["_addressable"] = cfg["addressable"](r)
        r["_token"] = cfg["room_token"](r)
        r["_page_key"] = None
        if r["_addressable"]:
            r["_page_key"] = cfg["page_for_room"](r)

    not_addr = [r for r in truth["rooms"] if not r["_addressable"]]
    addr = [r for r in truth["rooms"] if r["_addressable"]]
    not_addr_by_key = defaultdict(list)
    for r in not_addr:
        not_addr_by_key[cfg["not_addressable_key"](r)].append(r)

    permit_result = dict(permit=permit, truth_total_sf=truth["total_sf"],
                          truth_n_rooms=len(truth["rooms"]),
                          n_not_addressable=len(not_addr),
                          not_addressable_by_key={
                              k: dict(n=len(v), sf=sum((x["area_sf"] or 0) for x in v),
                                      reason=cfg["not_addressable_reason"].format(b=k))
                              for k, v in not_addr_by_key.items()},
                          pages=[])

    all_rows = []
    for page_cfg in cfg["pages"]:
        pi = page_cfg["page_index"]
        doc_id = page_cfg.get("doc_id", cfg["doc_id"])
        tag = f"{permit}_{doc_id}_p{pi}"
        print(f"\n--- page {tag} ({page_cfg['sheet']}) ---")
        pdf_path = download_pdf(s3, doc_id)

        page_truth_rooms = [r for r in addr if r["_page_key"] == (doc_id, pi)]
        if not page_truth_rooms:
            # e.g. this specific sub-page has 0 target rooms mapped to it
            print("  (no truth rooms map to this page)")

        engine_out, diag = run_geometry_engine(pdf_path, pi)
        print("  engine diag:", json.dumps(diag, default=str))
        page_result = dict(doc_id=doc_id, page_index=pi, sheet=page_cfg["sheet"], diag=diag)

        if engine_out is None:
            page_result["verdict"] = diag["verdict"]
            page_result["rows"] = []
            permit_result["pages"].append(page_result)
            continue

        rooms_all = engine_out["rooms_all"]
        feet_per_pt = engine_out["feet_per_pt"]
        target_tokens = [r["_token"] for r in page_truth_rooms]
        anchors = find_room_anchors(pdf_path, pi, target_tokens)
        rows, unlabeled_polys, ambiguous = grade_page(rooms_all, feet_per_pt, anchors, page_truth_rooms)
        page_result["n_anchors_found_on_page"] = len(anchors)
        page_result["n_target_tokens"] = len(target_tokens)
        page_result["ambiguous_tokens"] = ambiguous
        page_result["n_unlabeled_polys"] = len(unlabeled_polys)
        page_result["unlabeled_polys_sqft"] = sorted(
            [round(rooms_all[i].area * feet_per_pt ** 2, 1) for i in unlabeled_polys], reverse=True)
        page_result["rows"] = rows
        page_result["verdict"] = "GRADED"

        # mandatory skill self-audit / dimension-string grading table
        dims = extract_dim_words(pdf_path, pi)
        dim_texts = sorted({d["text"] for d in dims})
        all_rooms_sorted = sorted(rooms_all, key=lambda p: -p.area)
        dim_grading = build_grading_table(all_rooms_sorted, feet_per_pt, dim_texts)
        page_result["dimension_grading_table"] = dim_grading

        overlay_path = os.path.join(OUT_DIR, f"overlay_{tag}.png")
        render_overlay(pdf_path, pi, rooms_all, feet_per_pt, rows, overlay_path, unlabeled_polys)
        page_result["overlay_path"] = os.path.relpath(overlay_path, ROOT)

        all_rows.extend(rows)
        permit_result["pages"].append(page_result)

        pdf_full = os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf")
        if os.path.exists(pdf_full):
            os.remove(pdf_full)

    # -------------------------------------------------------- rollup ----
    matched = [r for r in all_rows if r["kind"] in ("MATCHED", "MATCHED_NO_AREA")]
    merged_ok = [r for r in all_rows if r["kind"] == "MERGED_OK"]
    merged_err = [r for r in all_rows if r["kind"] == "MERGED_ERROR"]
    missed = [r for r in all_rows if r["kind"] == "MISSED_NO_POLYGON"]
    not_on_page = [r for r in all_rows if r["kind"] == "NOT_ON_PAGE"]

    errs = [abs(r["pct_error"]) for r in matched if r.get("pct_error") is not None]
    merge_errs = [abs(r["pct_error"]) for r in merged_err if r.get("pct_error") is not None]

    matched_computed = sum(r["computed_sqft"] for r in matched)
    matched_truth = sum(r.get("truth_sqft") or 0 for r in matched)
    merged_ok_computed = sum(r["computed_sqft"] for r in merged_ok)
    merged_ok_truth = sum(r["truth_sqft_sum"] for r in merged_ok)
    merged_err_computed = sum(r["computed_sqft"] for r in merged_err)
    merged_err_truth = sum(r["truth_sqft_sum"] for r in merged_err)

    addressable_truth_sf = sum((r["area_sf"] or 0) for r in addr)

    permit_result["summary"] = dict(
        n_addressable=len(addr),
        addressable_truth_sf=addressable_truth_sf,
        n_matched=len(matched),
        n_merged_ok_groups=len(merged_ok), n_merged_ok_rooms=sum(len(r["tokens"]) for r in merged_ok),
        n_merged_err_groups=len(merged_err), n_merged_err_rooms=sum(len(r["tokens"]) for r in merged_err),
        n_missed_no_polygon=len(missed),
        n_not_on_page=len(not_on_page),
        median_abs_pct_error_matched=round(statistics.median(errs), 1) if errs else None,
        median_abs_pct_error_merged_err=round(statistics.median(merge_errs), 1) if merge_errs else None,
        matched_computed_sf=round(matched_computed, 1), matched_truth_sf=round(matched_truth, 1),
        merged_ok_computed_sf=round(merged_ok_computed, 1), merged_ok_truth_sf=round(merged_ok_truth, 1),
        merged_err_computed_sf=round(merged_err_computed, 1), merged_err_truth_sf=round(merged_err_truth, 1),
        total_sf_delta_vs_addressable_truth=round(
            (matched_computed + merged_ok_computed + merged_err_computed) - addressable_truth_sf, 1),
    )
    print("\nSUMMARY:", json.dumps(permit_result["summary"], indent=2))
    return permit_result


def main():
    s3 = r2_client()
    results = []
    for cfg in PERMITS:
        r = process_permit(s3, cfg)
        results.append(r)

    with open(os.path.join(OUT_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    for f in os.listdir(PDF_TMP_DIR):
        os.remove(os.path.join(PDF_TMP_DIR, f))
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass

    print("\n\n=== ALL DONE ===")
    for r in results:
        print(r["permit"], r["summary"])


if __name__ == "__main__":
    main()
