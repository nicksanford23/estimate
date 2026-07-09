#!/usr/bin/env python3
"""Probe 28 -- regression canaries for the v3 engine (anchor-cluster
membership filter), extending probe27_canary.py's bank-page methodology and
ADDING the hotel page canary that probe27_closure_fix.md only ran ad hoc
(inline numbers in the markdown, no saved script/data).

BANK canary (14-11290-NEWC, doc 1494156, page 3): same 18-room truth anchor
list as probes 4/6/27. Adds a v3 variant (v2_gated geometry + the new
anchor-cluster filter) to the existing v1/v2/naive-ungated comparison.

HOTEL canary (17-35590-RNVS, doc 3523243, page 9): this page has NEVER had a
per-room truth schedule (probe2b/probe27 used it purely as a DENSITY STRESS
TEST -- minor-tier segment count ~1500-2000, the page where an ungated
closer was first found to explode). No formal anchors exist. To test the
anchor-cluster filter honestly on THIS specific page (the one the task
statement names for false-positive risk), we derive real anchors from the
page's own printed finish-schedule keynote tags ("201.1", "201.2", "201.3"
-> room 201; a genuine printed label, just decimal-suffixed, not invented)
via a regex, giving 15 real room-number anchors (201-215, 2nd floor). This
is NOT a truth-area SF grading exercise (no truth `area_sf` exists) -- it
is a structural regression + false-positive check, reported as such.

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
from probe4_room_sf import ROOMS as BANK_ROOMS  # noqa: E402

OUT_DIR = os.path.join(ROOT, "data", "probe28")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR

BANK_DOC, BANK_PAGE = 1494156, 3
HOTEL_DOC, HOTEL_PAGE = 3523243, 9


def build_seed(extracted, feet_per_pt):
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
    walls_final, n_added, n_left = admit_minor(seed, minor_unpaired, extracted["pw"])
    return walls_final, tiers


def grade_bank(rooms, anchors, feet_per_pt):
    room_poly, poly_rooms = {}, defaultdict(list)
    for rn, (x, y) in anchors.items():
        pt = Point(x, y)
        for i, pg in enumerate(rooms):
            if pg.contains(pt):
                room_poly[rn] = i
                poly_rooms[i].append(rn)
                break
    c = dict(closed=0, fragment=0, merged=0, no_polygon=0)
    closed_rooms = []
    for rn in BANK_ROOMS:
        if rn not in anchors:
            continue
        pi = room_poly.get(rn)
        if pi is None:
            c["no_polygon"] += 1
        elif len(poly_rooms[pi]) > 1:
            c["merged"] += 1
        else:
            area = rooms[pi].area * feet_per_pt ** 2
            if area < 25:
                c["fragment"] += 1
            else:
                c["closed"] += 1
                closed_rooms.append(rn)
    return c, sorted(closed_rooms)


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

        variants = [
            ("v1_arcs_only", dict(feet_per_pt=None)),
            ("v2_gated", dict(feet_per_pt=fpp, gap_ft=3.25, density_pctile=80)),
            ("naive_ungated_3.25ft", dict(feet_per_pt=fpp, gap_ft=3.25, density_pctile=100)),
        ]

        for name, kwargs in variants:
            if kwargs.get("feet_per_pt") is None:
                from probe2_sf import snap_and_close as v1_close
                lines_ls, gap_info = v1_close(walls_final, extracted["arcs"], pw, feet_per_pt=None)
            else:
                lines_ls, gap_info = snap_and_close_v2(walls_final, extracted["arcs"], pw, **kwargs)
            rooms_pre, n_faces = polygonize_rooms(lines_ls, pw, ph, 15, 8000, fpp)
            rooms_v2filtered, killed, _ = filter_cavity_hatch(rooms_pre, fpp) if fpp else (rooms_pre, [], [])
            c_pre, closed_pre = grade_bank(rooms_pre, anchors, fpp)
            c_post, closed_post = grade_bank(rooms_v2filtered, anchors, fpp)
            total_sf_pre = sum(p.area * fpp ** 2 for p in rooms_pre)
            print(f"--- [bank] {name} ---  gap_info={gap_info}")
            print(f"  n_polygon_faces={n_faces}  n_rooms(15-8000sf)={len(rooms_pre)}  total_sf(all)={total_sf_pre:.0f}")
            print(f"  PRE-cavity : closed={c_pre['closed']:>2} frag={c_pre['fragment']:>2} merged={c_pre['merged']:>2} no_poly={c_pre['no_polygon']:>2}")
            print(f"  POST-cavity: closed={c_post['closed']:>2} frag={c_post['fragment']:>2} merged={c_post['merged']:>2} no_poly={c_post['no_polygon']:>2}  (killed {len(killed)}/{sum(k['sqft'] for k in killed):.0f}sf)")

            results[name] = dict(gap_info=gap_info, n_faces=n_faces, n_rooms=len(rooms_pre),
                                  total_sf=round(total_sf_pre, 1), pre=c_pre, post=c_post,
                                  n_killed=len(killed), killed_sf=round(sum(k["sqft"] for k in killed), 1),
                                  closed_rooms_post=closed_post)

        # v3: v2_gated geometry + anchor-cluster filter
        lines_ls, gap_info = snap_and_close_v2(walls_final, extracted["arcs"], pw,
                                                feet_per_pt=fpp, gap_ft=3.25, density_pctile=80)
        rooms_pre, n_faces = polygonize_rooms(lines_ls, pw, ph, 15, 8000, fpp)
        rooms_v2filtered, killed, _ = filter_cavity_hatch(rooms_pre, fpp)
        ac = filter_anchor_clusters(rooms_v2filtered, anchor_points, fpp)
        rooms_v3 = [rooms_v2filtered[i] for i in ac["kept_idx"]]
        c_pre, closed_pre = grade_bank(rooms_v2filtered, anchors, fpp)
        c_post, closed_post = grade_bank(rooms_v3, anchors, fpp)
        anchor_killed_sf = sum(rooms_v2filtered[i].area * fpp ** 2 for i in ac["killed_idx"])
        print(f"--- [bank] v3 (v2_gated + anchor-cluster filter) ---")
        print(f"  anchor_cluster: {len(ac['clusters'])} clusters, "
              f"{sum(1 for h in ac['cluster_has_anchor'] if not h)} killed, "
              f"{len(ac['killed_idx'])} polys / {anchor_killed_sf:.0f}sf, "
              f"false_positive_suspects={len(ac['false_positive_suspects'])}")
        print(f"  v2 (pre-anchor-filter): closed={c_pre['closed']} no_poly={c_pre['no_polygon']}")
        print(f"  v3 (post-anchor-filter): closed={c_post['closed']} no_poly={c_post['no_polygon']}")
        results["v3_anchor_filtered"] = dict(
            n_clusters_total=len(ac["clusters"]),
            n_clusters_killed=sum(1 for h in ac["cluster_has_anchor"] if not h),
            n_polys_killed=len(ac["killed_idx"]), sf_killed=round(anchor_killed_sf, 1),
            false_positive_suspects=ac["false_positive_suspects"],
            pre=c_pre, post=c_post, closed_rooms_post=closed_post,
            regression_vs_v2=(c_post["closed"] < c_pre["closed"]))

        # overlays: v1, v2_gated (already saved names from probe27), plus v3
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
            for i, pg_ in enumerate(rooms_v3):
                if pg_.contains(pt):
                    anchors_by_poly[i].append(rn)
                    break
        render(rooms_v3, anchors_by_poly, os.path.join(OUT_DIR, f"overlay_bank-canary_{BANK_DOC}_p{BANK_PAGE}_v3_anchor_filtered.png"))

    finally:
        p = os.path.join(PDF_TMP_DIR, f"{BANK_DOC}.pdf")
        if os.path.exists(p):
            os.remove(p)
    return results


KEYNOTE_RE = re.compile(r"^(\d{3})\.\d+$")


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
              f"decimal finish-keynote tags (e.g. '201.1'->'201'): {sorted(anchors)}\n")

        walls_final, tiers = build_seed(extracted, fpp)
        print(f"[hotel] n_major_clean={len(tiers['major'])} n_minor_clean={len(tiers['minor'])}\n")

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

        variants = [
            ("v1_arcs_only", dict(feet_per_pt=None)),
            ("v2_gated", dict(feet_per_pt=fpp, gap_ft=3.25, density_pctile=80)),
        ]
        rooms_by_variant = {}
        for name, kwargs in variants:
            if kwargs.get("feet_per_pt") is None:
                from probe2_sf import snap_and_close as v1_close
                lines_ls, gap_info = v1_close(walls_final, extracted["arcs"], pw, feet_per_pt=None)
            else:
                lines_ls, gap_info = snap_and_close_v2(walls_final, extracted["arcs"], pw, **kwargs)
            rooms_pre, n_faces = polygonize_rooms(lines_ls, pw, ph, 15, 5000, fpp)
            rooms_post, killed, _ = filter_cavity_hatch(rooms_pre, fpp) if fpp else (rooms_pre, [], [])
            total_pre = sum(p.area * fpp ** 2 for p in rooms_pre)
            total_post = sum(p.area * fpp ** 2 for p in rooms_post)
            hit = anchors_hit(rooms_post)
            n_anchored_polys = len(hit)
            n_anchors_matched = len(set().union(*hit.values())) if hit else 0
            print(f"--- [hotel] {name} --- gap_info={gap_info}")
            print(f"  n_faces={n_faces} n_rooms(15-5000sf)={len(rooms_pre)}/{len(rooms_post)} pre/post-cavity "
                  f"total_sf={total_pre:.0f}/{total_post:.0f}  anchored_polys={n_anchored_polys} "
                  f"anchors_matched={n_anchors_matched}/{len(anchors)}")
            results[name] = dict(gap_info=gap_info, n_faces=n_faces,
                                  n_rooms_pre=len(rooms_pre), n_rooms_post=len(rooms_post),
                                  total_sf_pre=round(total_pre, 1), total_sf_post=round(total_post, 1),
                                  n_anchored_polys=n_anchored_polys, n_anchors_matched=n_anchors_matched)
            rooms_by_variant[name] = rooms_post

        # v3: v2_gated + anchor-cluster filter
        rooms_v2 = rooms_by_variant["v2_gated"]
        ac = filter_anchor_clusters(rooms_v2, anchor_points, fpp)
        rooms_v3 = [rooms_v2[i] for i in ac["kept_idx"]]
        killed_sf = sum(rooms_v2[i].area * fpp ** 2 for i in ac["killed_idx"])
        hit_v3 = anchors_hit(rooms_v3)
        n_anchors_matched_v3 = len(set().union(*hit_v3.values())) if hit_v3 else 0
        total_v3 = sum(p.area * fpp ** 2 for p in rooms_v3)
        print(f"--- [hotel] v3 (v2_gated + anchor-cluster filter) ---")
        print(f"  anchor_cluster: {len(ac['clusters'])} clusters, "
              f"{sum(1 for h in ac['cluster_has_anchor'] if not h)} killed, "
              f"{len(ac['killed_idx'])} polys / {killed_sf:.0f}sf killed, "
              f"false_positive_suspects={len(ac['false_positive_suspects'])}")
        print(f"  n_rooms(post)={len(rooms_v3)} total_sf={total_v3:.0f} anchors_matched={n_anchors_matched_v3}/{len(anchors)}")
        results["v3_anchor_filtered"] = dict(
            n_clusters_total=len(ac["clusters"]),
            n_clusters_killed=sum(1 for h in ac["cluster_has_anchor"] if not h),
            n_polys_killed=len(ac["killed_idx"]), sf_killed=round(killed_sf, 1),
            n_rooms_post=len(rooms_v3), total_sf_post=round(total_v3, 1),
            n_anchors_matched=n_anchors_matched_v3,
            false_positive_suspects=ac["false_positive_suspects"],
            regression_vs_v2=(n_anchors_matched_v3 < results["v2_gated"]["n_anchors_matched"]))

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

        render(rooms_v2, anchors_hit(rooms_v2),
                os.path.join(OUT_DIR, f"overlay_hotel-canary_{HOTEL_DOC}_p{HOTEL_PAGE}_v2_gated.png"))
        render(rooms_v3, hit_v3,
                os.path.join(OUT_DIR, f"overlay_hotel-canary_{HOTEL_DOC}_p{HOTEL_PAGE}_v3_anchor_filtered.png"))

    finally:
        p = os.path.join(PDF_TMP_DIR, f"{HOTEL_DOC}.pdf")
        if os.path.exists(p):
            os.remove(p)
    return results


def main():
    print("=" * 70, "\nBANK CANARY\n", "=" * 70)
    bank = run_bank_canary()
    print("\n" + "=" * 70, "\nHOTEL CANARY\n", "=" * 70)
    hotel = run_hotel_canary()

    with open(os.path.join(OUT_DIR, "canary_results_v3.json"), "w") as f:
        json.dump(dict(bank=bank, hotel=hotel), f, indent=2, default=str)

    for d in (PDF_TMP_DIR,):
        for fn in os.listdir(d):
            os.remove(os.path.join(d, fn))
        try:
            os.rmdir(d)
        except OSError:
            pass

    print("\n\n=== CANARY VERDICTS ===")
    print("bank v3 regression:", bank["v3_anchor_filtered"]["regression_vs_v2"])
    print("hotel v3 regression:", hotel["v3_anchor_filtered"]["regression_vs_v2"])


if __name__ == "__main__":
    main()
