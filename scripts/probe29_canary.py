#!/usr/bin/env python3
"""Probe 29 (Task A) -- regression canaries for the v4 engine (directional
proximity-reconnection fix on top of probe28's anchor-cluster filter),
extending probe28_canary.py's bank+hotel methodology with a v4 variant.

Adds `filter_anchor_clusters_v4` alongside probe28's `filter_anchor_clusters`
(v3, unchanged) on the SAME v2_gated geometry already computed for each
canary page -- same anchors, same rooms, only the anchor-cluster membership
step differs (v3 strict-touching vs v4 directional-proximity-reconnect).

Deletes fetched PDFs after use.
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from shapely.geometry import Point  # noqa: E402

import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, extract_drawings, find_scale,
    polygonize_rooms, snap_and_close,
)
from probe2b_sf import two_tier_wall_candidates, find_parallel_pairs, admit_minor  # noqa: E402
from geometry_v2 import snap_and_close_v2, filter_cavity_hatch  # noqa: E402
from geometry_v3 import filter_anchor_clusters  # noqa: E402
from geometry_v4 import filter_anchor_clusters_v4  # noqa: E402
from probe4_room_sf import ROOMS as BANK_ROOMS  # noqa: E402
from probe28_canary import build_seed, grade_bank  # noqa: E402 -- reused verbatim

OUT_DIR = os.path.join(ROOT, "data", "probe29")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR

BANK_DOC, BANK_PAGE = 1494156, 3
HOTEL_DOC, HOTEL_PAGE = 3523243, 9
KEYNOTE_RE = re.compile(r"^(\d{3})\.\d+$")


def run_bank_canary():
    s3 = r2_client()
    pdf = download_pdf(s3, BANK_DOC)
    results = {}
    try:
        fpp, scale_text = find_scale(BANK_DOC, BANK_PAGE)
        extracted = extract_drawings(pdf, BANK_PAGE)
        pw, ph = extracted["pw"], extracted["ph"]

        doc = fitz.open(pdf)
        page = doc[BANK_PAGE]
        anchors = {}
        for w in page.get_text("words"):
            t = w[4].strip()
            if t.isdigit() and int(t) in BANK_ROOMS and int(t) not in anchors:
                anchors[int(t)] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        doc.close()
        anchor_points = list(anchors.values())

        walls_final, tiers = build_seed(extracted, fpp)
        print(f"[bank] scale={scale_text} n_major_clean={len(tiers['major'])} "
              f"n_minor_clean={len(tiers['minor'])} anchors={len(anchors)}/18\n")

        # v2_gated geometry -- identical base for v3 and v4
        lines_ls, gap_info = snap_and_close_v2(walls_final, extracted["arcs"], pw,
                                                feet_per_pt=fpp, gap_ft=3.25, density_pctile=80)
        rooms_pre, n_faces = polygonize_rooms(lines_ls, pw, ph, 15, 8000, fpp)
        rooms_v2filtered, killed, _ = filter_cavity_hatch(rooms_pre, fpp)
        c_v2, closed_v2 = grade_bank(rooms_v2filtered, anchors, fpp)

        # v3 (unchanged, from probe28)
        ac3 = filter_anchor_clusters(rooms_v2filtered, anchor_points, fpp)
        rooms_v3 = [rooms_v2filtered[i] for i in ac3["kept_idx"]]
        c_v3, closed_v3 = grade_bank(rooms_v3, anchors, fpp)
        killed_sf3 = sum(rooms_v2filtered[i].area * fpp ** 2 for i in ac3["killed_idx"])

        # v4 (this probe -- directional proximity reconnection)
        ac4 = filter_anchor_clusters_v4(rooms_v2filtered, anchor_points, fpp)
        rooms_v4 = [rooms_v2filtered[i] for i in ac4["kept_idx"]]
        c_v4, closed_v4 = grade_bank(rooms_v4, anchors, fpp)
        review_sf4 = sum(rooms_v2filtered[i].area * fpp ** 2 for i in ac4["review_killed_idx"])
        artifact_sf4 = sum(rooms_v2filtered[i].area * fpp ** 2 for i in ac4["artifact_idx"])

        print(f"--- [bank] v2_gated (pre-anchor-filter) --- closed={c_v2['closed']} no_poly={c_v2['no_polygon']}")
        print(f"--- [bank] v3 (touching anchor filter) --- closed={c_v3['closed']} no_poly={c_v3['no_polygon']} "
              f"killed={len(ac3['killed_idx'])}polys/{killed_sf3:.0f}sf "
              f"suspects={len(ac3['false_positive_suspects'])}")
        print(f"--- [bank] v4 (directional proximity reconnect) --- closed={c_v4['closed']} no_poly={c_v4['no_polygon']} "
              f"reconnected_islands={ac4['n_reconnected_islands']} "
              f"review_killed={len(ac4['review_killed_idx'])}polys/{review_sf4:.0f}sf "
              f"artifact={len(ac4['artifact_idx'])}polys/{artifact_sf4:.0f}sf")

        results["v2_gated"] = dict(closed=c_v2["closed"], no_polygon=c_v2["no_polygon"], closed_rooms=closed_v2)
        results["v3_anchor_filtered"] = dict(
            closed=c_v3["closed"], no_polygon=c_v3["no_polygon"], closed_rooms=closed_v3,
            n_polys_killed=len(ac3["killed_idx"]), sf_killed=round(killed_sf3, 1),
            false_positive_suspects=ac3["false_positive_suspects"],
            regression_vs_v2=(c_v3["closed"] < c_v2["closed"]))
        results["v4_proximity_reconnect"] = dict(
            closed=c_v4["closed"], no_polygon=c_v4["no_polygon"], closed_rooms=closed_v4,
            n_reconnected_islands=ac4["n_reconnected_islands"],
            reconnected_diag=ac4["reconnected_diag"],
            n_polys_review_killed=len(ac4["review_killed_idx"]), sf_review_killed=round(review_sf4, 1),
            n_polys_artifact=len(ac4["artifact_idx"]), sf_artifact=round(artifact_sf4, 1),
            false_positive_suspects=ac4["false_positive_suspects"],
            regression_vs_v3=(c_v4["closed"] < c_v3["closed"]),
            regression_vs_v2=(c_v4["closed"] < c_v2["closed"]))

        def render(rooms, anchors_by_poly, out_path):
            doc = fitz.open(pdf)
            pg = doc[BANK_PAGE]
            Z = 1800 / pg.rect.width
            pm = pg.get_pixmap(matrix=fitz.Matrix(Z, Z))
            img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            dd = ImageDraw.Draw(overlay)
            try:
                fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            except Exception:
                fnt = ImageFont.load_default()
            for i, poly in enumerate(rooms):
                pts = [(x * Z, y * Z) for x, y in poly.exterior.coords]
                rns = anchors_by_poly.get(i)
                sqft = poly.area * fpp ** 2
                if rns:
                    color = (0, 160, 0, 100) if len(rns) == 1 else (220, 130, 0, 110)
                    label = "+".join(str(r) for r in rns) + f"\n{sqft:.0f}sf"
                else:
                    color = (150, 150, 150, 50)
                    label = None
                dd.polygon(pts, fill=color, outline=(0, 0, 0, 200))
                if label:
                    cen = poly.centroid
                    dd.text((cen.x * Z, cen.y * Z), label, fill=(0, 0, 0, 255), font=fnt)
            out = Image.alpha_composite(img, overlay).convert("RGB")
            out.save(out_path)
            doc.close()

        anchors_by_poly = defaultdict(list)
        for rn, (x, y) in anchors.items():
            pt = Point(x, y)
            for i, pg_ in enumerate(rooms_v4):
                if pg_.contains(pt):
                    anchors_by_poly[i].append(rn)
                    break
        render(rooms_v4, anchors_by_poly,
               os.path.join(OUT_DIR, f"overlay_bank-canary_{BANK_DOC}_p{BANK_PAGE}_v4_proximity_reconnect.png"))

    finally:
        p = os.path.join(PDF_TMP_DIR, f"{BANK_DOC}.pdf")
        if os.path.exists(p):
            os.remove(p)
    return results


def run_hotel_canary():
    s3 = r2_client()
    pdf = download_pdf(s3, HOTEL_DOC)
    results = {}
    try:
        fpp, scale_text = find_scale(HOTEL_DOC, HOTEL_PAGE)
        extracted = extract_drawings(pdf, HOTEL_PAGE)
        pw, ph = extracted["pw"], extracted["ph"]

        doc = fitz.open(pdf)
        page = doc[HOTEL_PAGE]
        anchors = defaultdict(list)
        for w in page.get_text("words"):
            t = w[4].strip()
            m = KEYNOTE_RE.match(t)
            if m:
                anchors[m.group(1)].append(((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
        doc.close()
        anchor_points = [pt for pts in anchors.values() for pt in pts]
        print(f"[hotel] scale={scale_text} derived {len(anchors)} room-number anchors from "
              f"decimal finish-keynote tags: {sorted(anchors)}\n")

        walls_final, tiers = build_seed(extracted, fpp)

        def anchors_hit(rooms):
            hit = defaultdict(set)
            for tok, pts in anchors.items():
                for (x, y) in pts:
                    p = Point(x, y)
                    for i, poly in enumerate(rooms):
                        if poly.contains(p):
                            hit[i].add(tok)
                            break
            return hit

        lines_ls, gap_info = snap_and_close_v2(walls_final, extracted["arcs"], pw,
                                                feet_per_pt=fpp, gap_ft=3.25, density_pctile=80)
        rooms_pre, n_faces = polygonize_rooms(lines_ls, pw, ph, 15, 5000, fpp)
        rooms_v2, killed, _ = filter_cavity_hatch(rooms_pre, fpp)
        hit_v2 = anchors_hit(rooms_v2)
        n_anchors_matched_v2 = len(set().union(*hit_v2.values())) if hit_v2 else 0

        ac3 = filter_anchor_clusters(rooms_v2, anchor_points, fpp)
        rooms_v3 = [rooms_v2[i] for i in ac3["kept_idx"]]
        killed_sf3 = sum(rooms_v2[i].area * fpp ** 2 for i in ac3["killed_idx"])
        hit_v3 = anchors_hit(rooms_v3)
        n_anchors_matched_v3 = len(set().union(*hit_v3.values())) if hit_v3 else 0

        ac4 = filter_anchor_clusters_v4(rooms_v2, anchor_points, fpp)
        rooms_v4 = [rooms_v2[i] for i in ac4["kept_idx"]]
        review_sf4 = sum(rooms_v2[i].area * fpp ** 2 for i in ac4["review_killed_idx"])
        artifact_sf4 = sum(rooms_v2[i].area * fpp ** 2 for i in ac4["artifact_idx"])
        hit_v4 = anchors_hit(rooms_v4)
        n_anchors_matched_v4 = len(set().union(*hit_v4.values())) if hit_v4 else 0

        print(f"--- [hotel] v2_gated --- n_rooms={len(rooms_v2)} anchors_matched={n_anchors_matched_v2}/{len(anchors)}")
        print(f"--- [hotel] v3 (touching) --- n_rooms={len(rooms_v3)} anchors_matched={n_anchors_matched_v3}/{len(anchors)} "
              f"killed={len(ac3['killed_idx'])}polys/{killed_sf3:.0f}sf suspects={len(ac3['false_positive_suspects'])}")
        print(f"--- [hotel] v4 (directional proximity) --- n_rooms={len(rooms_v4)} anchors_matched={n_anchors_matched_v4}/{len(anchors)} "
              f"reconnected={ac4['n_reconnected_islands']} "
              f"review_killed={len(ac4['review_killed_idx'])}polys/{review_sf4:.0f}sf "
              f"artifact={len(ac4['artifact_idx'])}polys/{artifact_sf4:.0f}sf")

        results["v2_gated"] = dict(n_rooms=len(rooms_v2), n_anchors_matched=n_anchors_matched_v2)
        results["v3_anchor_filtered"] = dict(
            n_rooms_post=len(rooms_v3), n_anchors_matched=n_anchors_matched_v3,
            n_polys_killed=len(ac3["killed_idx"]), sf_killed=round(killed_sf3, 1),
            false_positive_suspects=ac3["false_positive_suspects"],
            regression_vs_v2=(n_anchors_matched_v3 < n_anchors_matched_v2))
        results["v4_proximity_reconnect"] = dict(
            n_rooms_post=len(rooms_v4), n_anchors_matched=n_anchors_matched_v4,
            n_reconnected_islands=ac4["n_reconnected_islands"], reconnected_diag=ac4["reconnected_diag"],
            n_polys_review_killed=len(ac4["review_killed_idx"]), sf_review_killed=round(review_sf4, 1),
            n_polys_artifact=len(ac4["artifact_idx"]), sf_artifact=round(artifact_sf4, 1),
            false_positive_suspects=ac4["false_positive_suspects"],
            regression_vs_v3=(n_anchors_matched_v4 < n_anchors_matched_v3),
            regression_vs_v2=(n_anchors_matched_v4 < n_anchors_matched_v2))

        def render(rooms, hit, out_path):
            doc = fitz.open(pdf)
            pg = doc[HOTEL_PAGE]
            Z = 1800 / pg.rect.width
            pm = pg.get_pixmap(matrix=fitz.Matrix(Z, Z))
            img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            dd = ImageDraw.Draw(overlay)
            try:
                fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
            except Exception:
                fnt = ImageFont.load_default()
            for i, poly in enumerate(rooms):
                pts = [(x * Z, y * Z) for x, y in poly.exterior.coords]
                toks = hit.get(i)
                sqft = poly.area * fpp ** 2
                color = (0, 160, 0, 100) if toks else (150, 150, 150, 50)
                dd.polygon(pts, fill=color, outline=(0, 0, 0, 200))
                if toks:
                    cen = poly.centroid
                    dd.text((cen.x * Z, cen.y * Z), "+".join(sorted(toks)) + f"\n{sqft:.0f}sf",
                             fill=(0, 0, 0, 255), font=fnt)
            out = Image.alpha_composite(img, overlay).convert("RGB")
            out.save(out_path)
            doc.close()

        render(rooms_v4, hit_v4,
               os.path.join(OUT_DIR, f"overlay_hotel-canary_{HOTEL_DOC}_p{HOTEL_PAGE}_v4_proximity_reconnect.png"))

    finally:
        p = os.path.join(PDF_TMP_DIR, f"{HOTEL_DOC}.pdf")
        if os.path.exists(p):
            os.remove(p)
    return results


def main():
    print("=" * 70, "\nBANK CANARY (v4)\n", "=" * 70)
    bank = run_bank_canary()
    print("\n" + "=" * 70, "\nHOTEL CANARY (v4)\n", "=" * 70)
    hotel = run_hotel_canary()

    with open(os.path.join(OUT_DIR, "canary_results_v4.json"), "w") as f:
        json.dump(dict(bank=bank, hotel=hotel), f, indent=2, default=str)

    for d in (PDF_TMP_DIR,):
        if os.path.exists(d):
            for fn in os.listdir(d):
                os.remove(os.path.join(d, fn))
            try:
                os.rmdir(d)
            except OSError:
                pass

    print("\n\n=== CANARY VERDICTS (v4) ===")
    print("bank v4 regression vs v3:", bank["v4_proximity_reconnect"]["regression_vs_v3"])
    print("bank v4 regression vs v2:", bank["v4_proximity_reconnect"]["regression_vs_v2"])
    print("hotel v4 regression vs v3:", hotel["v4_proximity_reconnect"]["regression_vs_v3"])
    print("hotel v4 regression vs v2:", hotel["v4_proximity_reconnect"]["regression_vs_v2"])


if __name__ == "__main__":
    main()
