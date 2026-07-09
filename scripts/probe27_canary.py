#!/usr/bin/env python3
"""Probe 27 -- regression canary. 14-11290-NEWC bank branch (doc 1494156,
page 3) run through THREE variants of the two-tier engine:
  v1_arcs_only   -- probe26's actual current call (feet_per_pt=None into
                    snap_and_close -> generic closer fully disabled, arc
                    chords only). This is the safe baseline in production.
  v2_gated       -- geometry_v2's new density-gated 3.25ft generic closer.
  naive_ungated  -- the OLD, never-shipped naive closer this probe must NOT
                    resurrect: same 3.25ft gap, but with the density gate
                    forced off (pctile=100, i.e. never skip). Included only
                    to prove the gate is doing real work -- if v2_gated and
                    naive_ungated produce the same room count, the gate is
                    not gating anything on this page and the "regression
                    canary" check is meaningless.

Grades all three against the 18 known branch room anchors (probe4's ROOMS)
so the comparison is apples-to-apples with the prior probes on this page.
Deletes the fetched PDF after use.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from shapely.geometry import Point  # noqa: E402

import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, extract_drawings, find_scale,
    polygonize_rooms, cluster_by_touching,
)
from probe2b_sf import two_tier_wall_candidates, find_parallel_pairs, admit_minor  # noqa: E402
from geometry_v2 import snap_and_close_v2, filter_cavity_hatch  # noqa: E402
from probe4_room_sf import ROOMS  # noqa: E402

DOC, PAGE = 1494156, 3
OUT_DIR = os.path.join(ROOT, "data", "probe27")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR


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


def render_canary_overlay(pdf_path, page_index, rooms, anchors_by_poly, feet_per_pt, out_path):
    doc = fitz.open(pdf_path)
    pg = doc[page_index]
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
        sqft = poly.area * feet_per_pt ** 2
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


def grade(rooms, anchors, feet_per_pt):
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
    for rn in ROOMS:
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


def main():
    s3 = r2_client()
    pdf = download_pdf(s3, DOC)
    try:
        fpp, scale_text = find_scale(DOC, PAGE)
        extracted = extract_drawings(pdf, PAGE)
        pw, ph = extracted["pw"], extracted["ph"]

        doc = fitz.open(pdf)
        page = doc[PAGE]
        anchors = {}
        for w in page.get_text("words"):
            t = w[4].strip()
            if t.isdigit() and int(t) in ROOMS and int(t) not in anchors:
                anchors[int(t)] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        doc.close()

        walls_final, tiers = build_seed(extracted, fpp)
        print(f"scale={scale_text} n_major_clean={len(tiers['major'])} "
              f"n_minor_clean={len(tiers['minor'])} anchors={len(anchors)}/18\n")

        variants = [
            ("v1_arcs_only", dict(feet_per_pt=None)),
            ("v2_gated", dict(feet_per_pt=fpp, gap_ft=3.25, density_pctile=80)),
            ("naive_ungated_3.25ft", dict(feet_per_pt=fpp, gap_ft=3.25, density_pctile=100)),
            ("naive_ungated_4.5ft_OLD", dict(feet_per_pt=fpp, gap_ft=4.5, density_pctile=100)),
        ]

        results = {}
        for name, kwargs in variants:
            if kwargs.get("feet_per_pt") is None:
                # exact v1 path: import the real snap_and_close for a true baseline
                from probe2_sf import snap_and_close as v1_close
                lines_ls, gap_info = v1_close(walls_final, extracted["arcs"], pw, feet_per_pt=None)
            else:
                lines_ls, gap_info = snap_and_close_v2(walls_final, extracted["arcs"], pw, **kwargs)
            rooms_pre, n_faces = polygonize_rooms(lines_ls, pw, ph, 15, 8000, fpp)
            rooms_v2filtered, killed, _ = filter_cavity_hatch(rooms_pre, fpp) if fpp else (rooms_pre, [], [])
            c_pre, closed_pre = grade(rooms_pre, anchors, fpp)
            c_post, closed_post = grade(rooms_v2filtered, anchors, fpp)
            total_sf_pre = sum(p.area * fpp ** 2 for p in rooms_pre)
            print(f"--- {name} ---  gap_info={gap_info}")
            print(f"  n_polygon_faces={n_faces}  n_rooms(15-8000sf)={len(rooms_pre)}  "
                  f"total_sf(all)={total_sf_pre:.0f}")
            print(f"  PRE-cavity-filter : closed={c_pre['closed']:>2} frag={c_pre['fragment']:>2} "
                  f"merged={c_pre['merged']:>2} no_poly={c_pre['no_polygon']:>2}  {closed_pre}")
            print(f"  POST-cavity-filter: closed={c_post['closed']:>2} frag={c_post['fragment']:>2} "
                  f"merged={c_post['merged']:>2} no_poly={c_post['no_polygon']:>2}  "
                  f"(killed {len(killed)} polys / {sum(k['sqft'] for k in killed):.0f} sf)  {closed_post}")
            results[name] = dict(gap_info=gap_info, n_faces=n_faces, n_rooms=len(rooms_pre),
                                  total_sf=round(total_sf_pre, 1), pre=c_pre, post=c_post,
                                  n_killed=len(killed),
                                  killed_sf=round(sum(k["sqft"] for k in killed), 1),
                                  closed_rooms_post=closed_post)

            if name in ("v1_arcs_only", "v2_gated"):
                anchors_by_poly = defaultdict(list)
                for rn, (x, y) in anchors.items():
                    pt = Point(x, y)
                    for i, pg_ in enumerate(rooms_v2filtered):
                        if pg_.contains(pt):
                            anchors_by_poly[i].append(rn)
                            break
                render_canary_overlay(
                    pdf, PAGE, rooms_v2filtered, anchors_by_poly, fpp,
                    os.path.join(OUT_DIR, f"overlay_bank-canary_{DOC}_p{PAGE}_{name}.png"))

        with open(os.path.join(OUT_DIR, "canary_results.json"), "w") as f:
            json.dump(results, f, indent=2, default=str)
        print("\n=== VERDICT ===")
        v2 = results["v2_gated"]
        naive = results["naive_ungated_3.25ft"]
        v1 = results["v1_arcs_only"]
        print(f"v1 (current/shipped) closed={v1['pre']['closed']} n_rooms={v1['n_rooms']}")
        print(f"v2 gated             closed={v2['pre']['closed']} n_rooms={v2['n_rooms']} "
              f"skipped_dense={v2['gap_info']['skipped_dense']}")
        print(f"naive ungated same gap_ft  closed={naive['pre']['closed']} n_rooms={naive['n_rooms']} "
              f"skipped_dense={naive['gap_info']['skipped_dense']}")
        regressed = v2["n_rooms"] > 3 * max(v1["n_rooms"], 1) or v2["pre"]["closed"] < v1["pre"]["closed"] - 2
        print("REGRESSION DETECTED" if regressed else "NO REGRESSION vs v1 baseline")
    finally:
        for fn in os.listdir(PDF_TMP_DIR):
            os.remove(os.path.join(PDF_TMP_DIR, fn))
        try:
            os.rmdir(PDF_TMP_DIR)
        except OSError:
            pass


if __name__ == "__main__":
    main()
