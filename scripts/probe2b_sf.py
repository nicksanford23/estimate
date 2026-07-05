#!/usr/bin/env python3
"""Probe 2b -- fix room segmentation on the Henriette Delille Hotel page
(17-35590-RNVS, doc 3523243, page_index 9) per the orchestrator's diagnosis:
probe 2's single-tier wall filter (thick-stroke clusters only) kept the
exterior envelope but dropped interior partitions, merging guest suites
into ~3500 SF blobs instead of individual rooms.

Fix, layered on top of probe2_sf.py's pipeline (imported, not copy-pasted):
  1. TWO-TIER wall candidates: MAJOR tier = thick strokes (width >= 0.45pt,
     same idea as probe 2). MINOR tier = thinner strokes (0.10-0.45pt),
     admitted only if they (a) survive hatch suppression, (b) are >=3ft
     long at scale, (c) connect to the wall graph -- built iteratively:
     start from major-tier nodes, repeatedly admit minor segments that
     touch the growing graph, until no more are added.
  2. PARALLEL-PAIR detection: any two aligned segments running parallel,
     overlapping tangentially by >=60%, separated by 0.2-0.85 ft (typical
     interior partition thickness at this scale) are treated as one
     high-confidence wall regardless of tier -- their centerline is
     synthesized and seeded into the graph directly (no length/hatch
     ambiguity: a matched PAIR is strong structural evidence).
  3. Hatch suppression is used with a WIDENED perpendicular-union radius
     (probe 2's version used the tight "spacing regularity" tolerance as
     the union radius too, which under-unions runs whose pitch -- e.g.
     stair-tread risers at ~11in centers -- exceeds that tolerance,
     letting long tick-mark runs slip through as "walls"; widening the
     union radius while keeping the regularity check catches those runs).
  4. Door/opening closing uses ONLY door-swing arc chords (no generic
     "any two endpoints within 4.5ft" closer) -- that generic closer,
     fine at probe 2's sparse ~330-segment candidate list, produces
     thousands of spurious short connectors once the minor tier roughly
     4x's candidate density, fragmenting/collapsing the room graph.

Deletes fetched PDFs when done (disk is tight). See
.claude/skills/sf-extraction/SKILL.md for the pipeline/verification
standard this must satisfy.
"""
import json
import math
import os
import sys
from collections import defaultdict

from shapely.geometry import LineString

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, seg_len, seg_angle_mod90, dominant_angle,
    extract_drawings, snap_and_close, polygonize_rooms, cluster_by_touching,
    find_scale, extract_dim_words, parse_ft_in, render_overlay,
)

OUT_DIR = os.path.join(ROOT, "data", "probe2b")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)

PAGE = dict(permit="17-35590-RNVS", doc_id=3523243, page_index=9,
            label="Henriette Delille Hotel - 2nd Floor Plan")

MAJOR_MIN_W = 0.45      # pt stroke width: thick clusters (exterior/major walls)
MINOR_MIN_W = 0.10      # pt stroke width: thin partition-wall candidates
MINOR_MIN_LEN_FT = 3.0  # shortest plausible real partition run


# ------------------------------------------------------------ hatch v2 ----

def suppress_hatches_v2(walls, pw, spacing_tol_frac=0.006, min_group=4,
                         locality_frac=0.10, union_perp_frac=0.02):
    """probe2's suppress_hatches, but the perpendicular UNION radius used to
    group candidate ticks into one hatch-run is widened to union_perp_frac*pw
    (probe2 reused the tight spacing_tol_frac as the union radius, which
    under-unions runs with pitch larger than that tolerance -- e.g. stair
    tread risers at ~11-17pt centers on this page -- leaving each tick as
    its own <min_group singleton that survives filtering). The final
    regularity-of-spacing check (on the union result) is unchanged."""
    tol = spacing_tol_frac * pw
    union_perp = union_perp_frac * pw
    locality = locality_frac * pw
    groups = defaultdict(list)
    for p0, p1, L, w in walls:
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        horiz = abs(dx) >= abs(dy)
        groups[(horiz, round(L / max(1.0, pw) * 200))].append((p0, p1, L, w))

    hatch_set = set()
    for key, segs in groups.items():
        if len(segs) < min_group:
            continue
        p00, p10, _, _ = segs[0]
        dx0, dy0 = p10[0] - p00[0], p10[1] - p00[1]
        L0 = math.hypot(dx0, dy0) or 1.0
        tx, ty = dx0 / L0, dy0 / L0
        nx, ny = -ty, tx
        pts = []
        for p0, p1, L, w in segs:
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            pts.append((mx * nx + my * ny, mx * tx + my * ty, (p0, p1, L, w)))

        n = len(pts)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a_, b_):
            ra, rb = find(a_), find(b_)
            if ra != rb:
                parent[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                if abs(pts[i][0] - pts[j][0]) <= union_perp and abs(pts[i][1] - pts[j][1]) <= locality:
                    union(i, j)

        comp = defaultdict(list)
        for i in range(n):
            comp[find(i)].append(i)

        for idxs in comp.values():
            if len(idxs) < min_group:
                continue
            offs = sorted(pts[i][0] for i in idxs)
            merge_tol = max(1.0, 0.08 * tol)
            merged = [offs[0]]
            for v in offs[1:]:
                if v - merged[-1] <= merge_tol:
                    merged[-1] = (merged[-1] + v) / 2
                else:
                    merged.append(v)
            offs = merged
            if len(offs) < min_group:
                continue
            gaps = [offs[k + 1] - offs[k] for k in range(len(offs) - 1)]
            if not gaps:
                continue
            mean_gap = sum(gaps) / len(gaps)
            if mean_gap <= 0:
                continue
            var = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
            if (var ** 0.5) > 0.5 * mean_gap:
                continue
            for i in idxs:
                _, _, seg = pts[i]
                hatch_set.add(id(seg[0]) ^ id(seg[1]) ^ hash(seg))

    kept, dropped = [], 0
    for p0, p1, L, w in walls:
        h = id(p0) ^ id(p1) ^ hash((p0, p1, L, w))
        if h in hatch_set:
            dropped += 1
            continue
        kept.append((p0, p1, L, w))
    return kept, dropped


# ---------------------------------------------------------- two-tier walls

def two_tier_wall_candidates(extracted, feet_per_pt):
    pw = extracted["pw"]
    lines = extracted["line_segments"]
    dom = dominant_angle(lines, pw)

    def aligned(p0, p1, tol=2.0):
        a = seg_angle_mod90(p0, p1)
        if a is None:
            return False
        d = min(abs(a - dom % 90), abs(a - dom % 90 - 90), abs(a - dom % 90 + 90))
        return d <= tol

    major_raw, minor_raw = [], []
    for p0, p1, w in lines:
        if w <= 0 or not aligned(p0, p1):
            continue
        L = seg_len(p0, p1)
        if w >= MAJOR_MIN_W:
            if L < 0.015 * pw:
                continue
            major_raw.append((p0, p1, L, w))
        elif w >= MINOR_MIN_W:
            if L * feet_per_pt < MINOR_MIN_LEN_FT:
                continue
            minor_raw.append((p0, p1, L, w))

    for p0, p1, w in extracted["fill_rect_edges"]:
        L = seg_len(p0, p1)
        if L < 0.015 * pw or not aligned(p0, p1):
            continue
        major_raw.append((p0, p1, L, w))

    combined = major_raw + minor_raw
    combined_clean, n_hatch = suppress_hatches_v2(combined, pw)
    major_vals, minor_vals = set(major_raw), set(minor_raw)
    major_clean = [s for s in combined_clean if s in major_vals]
    minor_clean = [s for s in combined_clean if s in minor_vals]
    return dict(major=major_clean, minor=minor_clean, dom=dom, n_hatch=n_hatch,
                n_major_raw=len(major_raw), n_minor_raw=len(minor_raw))


def find_parallel_pairs(all_clean, feet_per_pt, min_len_ft=3.0,
                         gap_ft_range=(0.2, 0.85), overlap_frac=0.6, bucket_pt=40):
    """Two aligned segments running parallel, overlapping tangentially by
    >=overlap_frac of the shorter one's span, separated by a perpendicular
    gap in the typical interior-partition-thickness range -- near-certain
    wall evidence regardless of stroke width."""
    segs = []
    for p0, p1, L, w in all_clean:
        if L * feet_per_pt < min_len_ft:
            continue
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        horiz = abs(dx) >= abs(dy)
        segs.append((p0, p1, L, w, horiz))

    buckets = defaultdict(list)
    for s in segs:
        p0, p1, L, w, horiz = s
        key = ("h", round((p0[1] + p1[1]) / 2 / bucket_pt)) if horiz \
            else ("v", round((p0[0] + p1[0]) / 2 / bucket_pt))
        buckets[key].append(s)

    pairs_found = []
    for key, group in buckets.items():
        horiz = key[0] == "h"
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                s1, s2 = group[i], group[j]
                p0a, p1a, La, wa, _ = s1
                p0b, p1b, Lb, wb, _ = s2
                if horiz:
                    ca, cb = (p0a[1] + p1a[1]) / 2, (p0b[1] + p1b[1]) / 2
                    lo_a, hi_a = min(p0a[0], p1a[0]), max(p0a[0], p1a[0])
                    lo_b, hi_b = min(p0b[0], p1b[0]), max(p0b[0], p1b[0])
                else:
                    ca, cb = (p0a[0] + p1a[0]) / 2, (p0b[0] + p1b[0]) / 2
                    lo_a, hi_a = min(p0a[1], p1a[1]), max(p0a[1], p1a[1])
                    lo_b, hi_b = min(p0b[1], p1b[1]), max(p0b[1], p1b[1])
                gap_ft = abs(ca - cb) * feet_per_pt
                if not (gap_ft_range[0] <= gap_ft <= gap_ft_range[1]):
                    continue
                ov = min(hi_a, hi_b) - max(lo_a, lo_b)
                if ov <= 0:
                    continue
                shorter = min(hi_a - lo_a, hi_b - lo_b)
                if shorter <= 0 or ov / shorter < overlap_frac:
                    continue
                pairs_found.append((s1[:4], s2[:4], horiz, max(lo_a, lo_b),
                                     min(hi_a, hi_b), (ca + cb) / 2))
    return pairs_found


def snap_pt(p, tol):
    return (round(p[0] / tol) * tol, round(p[1] / tol) * tol)


def admit_minor(seed_segs, minor_segs, pw, snap_tol_frac=0.003):
    """Iteratively admit minor-tier segments whose (snapped) endpoint
    touches the growing wall-graph node set, seeded from major-tier +
    parallel-pair-centerline segments. Repeat to a fixed point."""
    tol = snap_tol_frac * pw
    nodes = set()
    walls = list(seed_segs)
    for p0, p1, L, w in seed_segs:
        nodes.add(snap_pt(p0, tol))
        nodes.add(snap_pt(p1, tol))
    remaining = list(minor_segs)
    added_total = 0
    changed = True
    while changed:
        changed = False
        still = []
        for s in remaining:
            p0, p1, L, w = s
            sp0, sp1 = snap_pt(p0, tol), snap_pt(p1, tol)
            if sp0 in nodes or sp1 in nodes:
                walls.append(s)
                nodes.add(sp0)
                nodes.add(sp1)
                added_total += 1
                changed = True
            else:
                still.append(s)
        remaining = still
    return walls, added_total, len(remaining)


# ------------------------------------------------------------------ main --

def process_page(s3, page_def):
    permit, doc_id, page_index = page_def["permit"], page_def["doc_id"], page_def["page_index"]
    tag = f"{permit}_{doc_id}_p{page_index}"
    print(f"\n=== {tag}: {page_def['label']} ===")
    result = dict(permit=permit, doc_id=doc_id, page_index=page_index, label=page_def["label"])

    pdf_path = download_pdf(s3, doc_id)
    try:
        feet_per_pt, scale_text = find_scale(doc_id, page_index)
        result["scale_text"] = scale_text
        result["feet_per_pt"] = feet_per_pt
        if feet_per_pt is None:
            result["verdict"] = "scale_unverified"
            result["reason"] = "no scale note found in page text"
            print(json.dumps(result, indent=2))
            return result

        extracted = extract_drawings(pdf_path, page_index)
        pw, ph = extracted["pw"], extracted["ph"]

        tiers = two_tier_wall_candidates(extracted, feet_per_pt)
        major_clean, minor_clean = tiers["major"], tiers["minor"]
        result["n_major_raw"] = tiers["n_major_raw"]
        result["n_minor_raw"] = tiers["n_minor_raw"]
        result["n_hatch_dropped"] = tiers["n_hatch"]
        result["n_major_clean"] = len(major_clean)
        result["n_minor_clean_candidates"] = len(minor_clean)
        result["dominant_angle_deg"] = round(tiers["dom"], 3)

        combined_clean = major_clean + minor_clean
        pairs = find_parallel_pairs(combined_clean, feet_per_pt)
        pair_member_segs = set()
        for a, b, *_ in pairs:
            pair_member_segs.add(a)
            pair_member_segs.add(b)
        result["n_parallel_pairs"] = len(pairs)
        result["n_segs_in_pairs"] = len(pair_member_segs)

        centerlines, seen_keys = [], set()
        for a, b, horiz, lo, hi, c in pairs:
            p0, p1 = ((lo, c), (hi, c)) if horiz else ((c, lo), (c, hi))
            key = (horiz, round(c / 2.0), round(lo / 3.0), round(hi / 3.0))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            centerlines.append((p0, p1, hi - lo, 0.3))
        result["n_pair_centerlines"] = len(centerlines)

        minor_unpaired = [s for s in minor_clean if s not in pair_member_segs]
        seed = major_clean + centerlines
        walls_final, n_added, n_left = admit_minor(seed, minor_unpaired, pw)
        result["n_minor_admitted_iteratively"] = n_added
        result["n_minor_left_out"] = n_left
        result["n_walls_final"] = len(walls_final)

        # door closing: arc chords ONLY (generic small-gap closer disabled --
        # see module docstring point 4)
        lines_ls, gap_info = snap_and_close(walls_final, extracted["arcs"], pw, feet_per_pt=None)
        result["gap_closing"] = gap_info

        min_sqft, max_sqft = 15, 5000
        rooms_all, n_faces = polygonize_rooms(lines_ls, pw, ph, min_sqft, max_sqft, feet_per_pt)
        result["n_polygon_faces_total"] = n_faces
        result["n_rooms_before_clustering"] = len(rooms_all)

        if not rooms_all:
            result["verdict"] = "scale_unverified"
            result["reason"] = "no room-sized polygons closed"
            print(json.dumps(result, indent=2))
            return result

        clusters = cluster_by_touching(rooms_all)
        clusters.sort(key=lambda idxs: -sum(rooms_all[i].area for i in idxs))
        main_cluster = clusters[0]
        other_clusters = clusters[1:]
        main_rooms = [rooms_all[i] for i in main_cluster]
        main_total_sqft = sum(p.area * feet_per_pt ** 2 for p in main_rooms)
        result["n_rooms_main_cluster"] = len(main_rooms)
        result["n_other_clusters_excluded"] = len(other_clusters)
        result["other_clusters_excluded_areas_sqft"] = [
            round(sum(rooms_all[i].area for i in idxs) * feet_per_pt ** 2, 1)
            for idxs in other_clusters
        ]

        largest_room_sqft = max(p.area * feet_per_pt ** 2 for p in main_rooms)
        audit_ok = 30 <= largest_room_sqft <= 10000 and 30 <= main_total_sqft <= 200000
        result["largest_room_sqft"] = round(largest_room_sqft, 1)
        result["total_sqft_main_cluster"] = round(main_total_sqft, 1)
        result["audit_ok"] = audit_ok

        if not audit_ok:
            result["verdict"] = "scale_unverified"
            result["reason"] = f"self-audit failed: largest_room={largest_room_sqft:.0f}sqft total={main_total_sqft:.0f}sqft"
            print(json.dumps(result, indent=2))
            return result

        rooms_sorted = sorted(main_rooms, key=lambda p: -p.area)
        rooms_json = []
        for i, poly in enumerate(rooms_sorted):
            sqft = poly.area * feet_per_pt ** 2
            minx, miny, maxx, maxy = poly.bounds
            rooms_json.append(dict(
                room_idx=i,
                sqft=round(sqft, 1),
                bbox_w_ft=round((maxx - minx) * feet_per_pt, 2),
                bbox_h_ft=round((maxy - miny) * feet_per_pt, 2),
                polygon_pts=[[round(x, 1), round(y, 1)] for x, y in poly.exterior.coords],
                confidence="low" if sqft > 900 else "medium",
                note="likely still merges multiple named rooms (partitions not fully recovered)" if sqft > 900 else "",
            ))
        result["rooms"] = rooms_json

        # dimension-string grading: manual, honest -- only rooms we can
        # actually pin against a printed dimension pair are graded; the
        # remaining large multi-room blobs are called out, not force-graded.
        dims = extract_dim_words(pdf_path, page_index)
        dim_texts = sorted({d["text"] for d in dims})
        result["dim_strings_found"] = dim_texts
        all_rooms_sorted = sorted(rooms_all, key=lambda p: -p.area)
        grading = build_grading_table(all_rooms_sorted, feet_per_pt, dim_texts)
        result["grading_table"] = grading

        overlay_path = os.path.join(OUT_DIR, f"overlay_{tag}.png")
        render_overlay(pdf_path, page_index, main_rooms, other_clusters, rooms_all,
                        rooms_json, overlay_path)
        result["overlay_path"] = os.path.relpath(overlay_path, ROOT)
        result["verdict"] = "PARTIAL"
        result["verdict_reason"] = (
            f"{len(main_rooms)} polygons in main cluster (vs 4 in probe 2), "
            "but the three guest-suite blocks (left/middle/right) are each "
            "still ONE merged polygon internally -- individual bedrooms/"
            "bathrooms/halls did not separate. Only small appendage rooms "
            "(closets, mechanical bays, canopy sections) resolved cleanly."
        )
        print(json.dumps({k: v for k, v in result.items() if k not in ("rooms",)}, indent=2, default=str))
        return result
    finally:
        pass


def build_grading_table(rooms_sorted, feet_per_pt, dim_texts):
    """Verification standard (skill step 7/mandatory audit): match polygon
    bounding-box edges against printed dimension strings directly, rather
    than asserting a hand-picked room identity. This is done for EVERY
    room-sized polygon (both main-cluster and excluded small clusters),
    keeping only matches within 6% on at least one axis -- and, where BOTH
    axes of a polygon match independent printed dimensions, reporting a
    full expected-area vs computed-area % error (the strongest form of
    check, since two independent printed numbers agree with the polygon
    math). This intentionally does NOT force-grade the three big merged
    blocks (they are not single rooms -- see verdict_reason); it grades
    whatever DID resolve as a clean, closed, room-sized polygon."""
    dim_vals = sorted({v for v in (parse_ft_in(t) for t in dim_texts) if v and v > 2})
    rows = []
    seen_areas = set()
    for poly in rooms_sorted:
        minx, miny, maxx, maxy = poly.bounds
        w_ft = (maxx - minx) * feet_per_pt
        h_ft = (maxy - miny) * feet_per_pt
        sqft = poly.area * feet_per_pt ** 2
        if round(sqft, 1) in seen_areas:
            continue
        w_match = min(dim_vals, key=lambda d: abs(d - w_ft) / d, default=None)
        h_match = min(dim_vals, key=lambda d: abs(d - h_ft) / d, default=None)
        w_ok = w_match is not None and abs(w_match - w_ft) / w_match <= 0.06
        h_ok = h_match is not None and abs(h_match - h_ft) / h_match <= 0.06
        if not (w_ok and h_ok):
            continue
        seen_areas.add(round(sqft, 1))
        expected_sqft = w_match * h_match
        pct_err = round(100 * (sqft - expected_sqft) / expected_sqft, 1)
        rows.append(dict(
            element_bbox_ft=f"{w_ft:.2f} x {h_ft:.2f}",
            computed_sqft=round(sqft, 1),
            matched_width_dim_ft=round(w_match, 2),
            matched_height_dim_ft=round(h_match, 2),
            expected_sqft=round(expected_sqft, 1),
            pct_error=pct_err,
            note="both bbox edges independently match printed dimension "
                 "strings within 6% -- confirms SCALE; this is a small "
                 "sub-element (canopy/closet-scale), NOT a named bedroom/"
                 "bathroom -- those partitions are still merged (see "
                 "verdict_reason)",
        ))
        if len(rows) >= 6:
            break
    return rows


def main():
    s3 = r2_client()
    result = process_page(s3, PAGE)

    with open(os.path.join(OUT_DIR, "results.json"), "w") as f:
        json.dump([result], f, indent=2, default=str)

    for f in os.listdir(PDF_TMP_DIR):
        os.remove(os.path.join(PDF_TMP_DIR, f))
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass

    print("\n=== DONE ===")
    print(PAGE["permit"], result.get("verdict"), result.get("total_sqft_main_cluster"),
          "n_rooms_main_cluster=", result.get("n_rooms_main_cluster"))


if __name__ == "__main__":
    main()
