#!/usr/bin/env python3
"""Probe 2 (Stage 4, Route A) — full SF-extraction pipeline on the 2 GOOD
pages identified by probe 1, per .claude/skills/sf-extraction/SKILL.md.

Pages:
  17-35590-RNVS doc=3523243 page_index=9   (Henriette Delille Hotel, 2nd floor)
  19-24353-RNVS doc=4492144 page_index=16  (705 Camp St, 2nd floor - PROPOSED)
    (page_index 29 in the original task is an ENLARGED-DETAIL sheet -- flagged,
     not used for room totals; page 16 substituted per skill failure-mode #4.)

Pipeline: get_drawings() from the ORIGINAL PDF -> dominant-angle histogram ->
wall-candidate filter (angle + stroke-width clusters, fill-rects included) ->
hatch suppression -> endpoint snapping / door-gap closing (using door-swing
arc chords where present) -> shapely polygonize -> connected-component
clustering (drop small/other-scale clusters, e.g. details on the same sheet)
-> per-room sqft -> scale parse + self-audit -> overlay PNG + JSON + grading
table (printed dimension strings vs polygon math).

Deletes fetched PDFs when done (disk is tight).
"""
import io
import json
import math
import os
import re
import sys
from collections import defaultdict

import boto3
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union, linemerge

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {}
with open(os.path.join(ROOT, ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            ENV[k] = v

OUT_DIR = os.path.join(ROOT, "data", "probe2")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)

PAGES = [
    dict(permit="17-35590-RNVS", doc_id=3523243, page_index=9,
         label="Henriette Delille Hotel - 2nd Floor Plan"),
    dict(permit="19-24353-RNVS", doc_id=4492144, page_index=16,
         label="705 Camp St - 2nd Floor Proposed (substituted for enlarged-detail p29)"),
]

SCALE_RE = re.compile(
    r"(\d+)\s*/\s*(\d+)\s*\"?\s*=\s*1\s*'\s*-?\s*0?\"?",
    re.IGNORECASE,
)

DIM_RE = re.compile(r"^\d+'-?\d*(?:\s?\d/\d)?\"?$")


# ---------------------------------------------------------------- R2 / PDF --

def r2_client():
    return boto3.client(
        "s3",
        endpoint_url=ENV["R2_ENDPOINT"],
        aws_access_key_id=ENV["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=ENV["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def download_pdf(s3, doc_id):
    dest = os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf")
    if os.path.exists(dest):
        return dest
    s3.download_file(ENV["R2_BUCKET"], f"docs/{doc_id}.pdf", dest)
    with open(dest, "rb") as f:
        head = f.read(5)
    assert head[:4] == b"%PDF", f"not a PDF: doc {doc_id}"
    return dest


# --------------------------------------------------------------- geometry --

def seg_len(p0, p1):
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def seg_angle_mod90(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    if dx == 0 and dy == 0:
        return None
    ang = math.degrees(math.atan2(dy, dx)) % 90.0
    return ang


def cluster_widths(widths, tol=0.15):
    clusters = []
    for w in sorted(widths):
        placed = False
        for c in clusters:
            center = c[0] / c[1]
            if abs(w - center) <= max(tol, center * 0.25):
                c[0] += w
                c[1] += 1
                placed = True
                break
        if not placed:
            clusters.append([w, 1])
    clusters.sort(key=lambda c: c[1], reverse=True)
    return [(round(c[0] / c[1], 4), c[1]) for c in clusters]


def dominant_angle(line_segments, pw):
    """Histogram of segment angles mod 90 (length-weighted, min length filter)
    to find the building's rotation off the page axes."""
    buckets = defaultdict(float)
    for p0, p1, w in line_segments:
        L = seg_len(p0, p1)
        if L < 0.01 * pw:
            continue
        a = seg_angle_mod90(p0, p1)
        if a is None:
            continue
        # fold near-0/near-90 together as "axis-aligned" bucket key 0
        key = round(a) % 90
        if key > 45:
            key = key  # keep raw; we bucket by rounding to nearest degree
        buckets[key] += L
    if not buckets:
        return 0.0
    best_key = max(buckets, key=buckets.get)
    # refine: weighted mean angle of segments within 3 deg of best_key (or its
    # complement, since a wall and its perpendicular both indicate the same
    # rotation mod 90)
    close = []
    for p0, p1, w in line_segments:
        a = seg_angle_mod90(p0, p1)
        if a is None:
            continue
        d = min(abs(a - best_key), abs(a - best_key - 90), abs(a - best_key + 90))
        if d <= 3:
            L = seg_len(p0, p1)
            # fold into [-45,45] relative representation for averaging
            rel = a - best_key
            if rel > 45:
                rel -= 90
            if rel < -45:
                rel += 90
            close.append((rel, L))
    if not close:
        return float(best_key % 90 if best_key <= 45 else best_key - 90)
    tot_l = sum(L for _, L in close)
    mean_rel = sum(r * L for r, L in close) / tot_l
    base = best_key if best_key <= 45 else best_key - 90
    return base + mean_rel


def extract_drawings(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    drawings = page.get_drawings()

    line_segments = []   # (p0, p1, width)
    fill_rect_edges = [] # (p0, p1, width) synthesized centerline of thin filled rects
    arcs = []             # (p_start, p_end) chord of curve-groups (door swings)
    all_widths = []

    for d in drawings:
        width = d.get("width") or 0.0
        is_fill = d.get("fill") is not None and d.get("type") in ("f", "fs")
        items = d.get("items", [])
        curve_pts = []
        for item in items:
            kind = item[0]
            if kind == "l":
                p0, p1 = (item[1].x, item[1].y), (item[2].x, item[2].y)
                line_segments.append((p0, p1, width))
                if width > 0:
                    all_widths.append(width)
            elif kind == "re":
                r = item[1]
                rw, rh = r.width, r.height
                short, long = min(rw, rh), max(rw, rh)
                if is_fill and long > 0:
                    width_frac = short / pw
                    len_frac = long / max(pw, ph)
                    if width_frac < 0.01 and len_frac > 0.015:
                        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
                        if rw >= rh:
                            p0, p1 = (r.x0, cy), (r.x1, cy)
                        else:
                            p0, p1 = (cx, r.y0), (cx, r.y1)
                        fill_rect_edges.append((p0, p1, short))
            elif kind == "c":
                p0 = (item[1].x, item[1].y)
                p3 = (item[4].x, item[4].y)
                curve_pts.append((p0, p3))
        # a "c" path with 1 curve of moderate radius = door swing arc; take
        # its endpoint chord as a closable-gap candidate
        for p0, p3 in curve_pts:
            L = seg_len(p0, p3)
            if 0.01 * pw < L < 0.06 * pw:
                arcs.append((p0, p3))

    doc.close()
    return dict(pw=pw, ph=ph, line_segments=line_segments,
                fill_rect_edges=fill_rect_edges, arcs=arcs,
                all_widths=all_widths)


def wall_candidates(extracted, angle_tol=2.0):
    pw = extracted["pw"]
    lines = extracted["line_segments"]
    width_clusters = cluster_widths([w for _, _, w in lines if w > 0])
    top5 = width_clusters[:5]
    # Use the top-2 MOST FREQUENT stroke-width clusters as wall linework --
    # architectural PDFs often draw walls with two nearby but distinct
    # widths (e.g. face line + outline). The single-max-value heuristic
    # picks up rare heavy accent strokes (few segments) instead. Hatch
    # suppression (regular-spacing detector) cleans out any fills/hatches
    # that share these widths.
    thick_set = {c for c, _ in top5[:2]}

    dom = dominant_angle(lines, pw)

    def aligned(p0, p1):
        a = seg_angle_mod90(p0, p1)
        if a is None:
            return False
        d = min(abs(a - dom % 90), abs(a - dom % 90 - 90), abs(a - dom % 90 + 90))
        return d <= angle_tol

    walls = []
    for p0, p1, w in lines:
        L = seg_len(p0, p1)
        if L < 0.015 * pw:
            continue
        if not aligned(p0, p1):
            continue
        # require a positive stroke width matching the wall-width clusters;
        # zero-width "l" items are typically glyph/icon fill outlines
        # (arrowheads, furniture icons), not walls.
        if w <= 0:
            continue
        if not any(abs(w - c) <= max(0.15, c * 0.3) for c in thick_set):
            continue
        walls.append((p0, p1, L, w))

    for p0, p1, w in extracted["fill_rect_edges"]:
        L = seg_len(p0, p1)
        if L < 0.015 * pw:
            continue
        if not aligned(p0, p1):
            continue
        walls.append((p0, p1, L, w))

    return walls, dom, thick_set


def suppress_hatches(walls, pw, spacing_tol_frac=0.006, min_group=4, locality_frac=0.035):
    """Drop groups of >=min_group near-identical-length, near-parallel
    segments at REGULAR, CLOSE spacing AND spatially local to each other --
    hatch fills / tick marks (e.g. stair treads, insulation hatch), not
    walls. Requires both perpendicular-offset regularity and 2D proximity
    (tangential closeness) so unrelated same-length walls scattered across
    the sheet are never merged into a false "run"."""
    tol = spacing_tol_frac * pw
    locality = locality_frac * pw
    # group by (orientation quadrant, rounded length) to find repeated hatch
    # ticks. NOTE: seg_angle_mod90() folds vertical and horizontal into the
    # SAME key (both -> 0), which is fine for wall alignment checks but
    # wrong here where we need a true, unambiguous direction per group; so
    # bucket separately by whether the segment is mostly horizontal or
    # mostly vertical.
    groups = defaultdict(list)
    for p0, p1, L, w in walls:
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        horiz = abs(dx) >= abs(dy)
        groups[(horiz, round(L / max(1.0, pw) * 200))].append((p0, p1, L, w))

    hatch_set = set()
    for key, segs in groups.items():
        if len(segs) < min_group:
            continue
        # basis from the group's actual (consistently-signed) direction,
        # not from a folded/rounded angle -- avoids horizontal/vertical
        # basis-vector mixups.
        p00, p10, _, _ = segs[0]
        dx0, dy0 = p10[0] - p00[0], p10[1] - p00[1]
        L0 = math.hypot(dx0, dy0) or 1.0
        tx, ty = dx0 / L0, dy0 / L0
        nx, ny = -ty, tx
        pts = []
        for p0, p1, L, w in segs:
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            pts.append((mx * nx + my * ny, mx * tx + my * ty, (p0, p1, L, w)))

        # spatial connected components on (perp, tangent) within `locality`
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
                if abs(pts[i][0] - pts[j][0]) <= tol and abs(pts[i][1] - pts[j][1]) <= locality:
                    union(i, j)

        comp = defaultdict(list)
        for i in range(n):
            comp[find(i)].append(i)

        for idxs in comp.values():
            if len(idxs) < min_group:
                continue
            offs = sorted(pts[i][0] for i in idxs)
            # Some hatch/wall conventions draw each tick/line as a close
            # DOUBLE stroke (~<1pt apart) -- merge those near-duplicates
            # into one representative "tick" position first, so pitch
            # regularity is judged on true tick spacing, not the doubled
            # sub-structure.
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
            # require genuinely regular spacing (low variance of gaps) --
            # true hatch ticks repeat at ~constant pitch
            gaps = [offs[k + 1] - offs[k] for k in range(len(offs) - 1)]
            if not gaps:
                continue
            mean_gap = sum(gaps) / len(gaps)
            if mean_gap <= 0:
                continue
            var = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
            if (var ** 0.5) > 0.5 * mean_gap:
                continue  # too irregular -- not a hatch pattern
            for i in idxs:
                _, _, seg = pts[i]
                hatch_set.add(id(seg[0]) ^ id(seg[1]) ^ hash(seg))

    kept = []
    dropped = 0
    for p0, p1, L, w in walls:
        h = id(p0) ^ id(p1) ^ hash((p0, p1, L, w))
        if h in hatch_set:
            dropped += 1
            continue
        kept.append((p0, p1, L, w))
    return kept, dropped


def snap_and_close(walls, arcs, pw, snap_tol_frac=0.0025, door_ft=4.5, feet_per_pt=None):
    """Round endpoints to a coordinate grid (snapping), then add short
    connector segments for gaps smaller than a door width (or arc chords,
    which ARE the closable gap per the skill)."""
    tol = snap_tol_frac * pw

    def snap_pt(p):
        return (round(p[0] / tol) * tol, round(p[1] / tol) * tol)

    lines = []
    endpoints = []
    for p0, p1, L, w in walls:
        sp0, sp1 = snap_pt(p0), snap_pt(p1)
        if sp0 == sp1:
            continue
        lines.append(LineString([sp0, sp1]))
        endpoints.extend([sp0, sp1])

    # door-swing arc chords: snap and add directly as wall segments (they
    # close the doorway opening at the correct location)
    added_from_arcs = 0
    for p0, p1 in arcs:
        sp0, sp1 = snap_pt(p0), snap_pt(p1)
        if sp0 != sp1:
            lines.append(LineString([sp0, sp1]))
            added_from_arcs += 1

    # generic small-gap closing: connect endpoints that are close (< door_ft)
    # but not already snapped together
    door_pt = (door_ft / feet_per_pt) if feet_per_pt else 0.0
    uniq_endpoints = list(set(endpoints))
    added_gap_closers = 0
    if door_pt > 0:
        # simple O(n^2) is fine at this scale (~thousands) -> bucket by grid cell
        cell = max(door_pt, tol)
        buckets = defaultdict(list)
        for p in uniq_endpoints:
            buckets[(int(p[0] // cell), int(p[1] // cell))].append(p)
        closed_pairs = set()
        for p in uniq_endpoints:
            cx, cy = int(p[0] // cell), int(p[1] // cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for q in buckets.get((cx + dx, cy + dy), []):
                        if q == p:
                            continue
                        key = tuple(sorted([p, q]))
                        if key in closed_pairs:
                            continue
                        d = seg_len(p, q)
                        if tol < d <= door_pt:
                            lines.append(LineString([p, q]))
                            closed_pairs.add(key)
                            added_gap_closers += 1

    return lines, dict(added_from_arcs=added_from_arcs, added_gap_closers=added_gap_closers)


def polygonize_rooms(lines, pw, ph, min_sqft, max_sqft, feet_per_pt):
    merged = unary_union(lines)
    polys = list(polygonize(merged))
    page_area_pts = pw * ph
    rooms = []
    for poly in polys:
        area_pts = poly.area
        sqft = area_pts * (feet_per_pt ** 2)
        if area_pts > 0.9 * page_area_pts:
            continue  # page border
        if sqft < min_sqft or sqft > max_sqft:
            continue
        rooms.append(poly)
    return rooms, len(polys)


def cluster_by_touching(rooms):
    """Connected-component grouping of room polygons that touch/overlap
    (i.e. belong to the same wall graph / drawing on the sheet)."""
    n = len(rooms)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if rooms[i].distance(rooms[j]) < 1e-6 or rooms[i].touches(rooms[j]):
                union(i, j)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


# ------------------------------------------------------------------ scale --

def find_scale(doc_id, page_index):
    path = os.path.join(ROOT, "data", "pagetext", str(doc_id), f"page_{page_index:04d}.txt")
    if not os.path.exists(path):
        return None, None
    with open(path, errors="ignore") as f:
        text = f.read()
    matches = SCALE_RE.findall(text)
    if not matches:
        return None, None
    # take the most frequent (num, den) pair -- the main plan's scale, not a
    # one-off detail-box scale elsewhere on the sheet
    counts = defaultdict(int)
    for num, den in matches:
        counts[(int(num), int(den))] += 1
    (num, den), _ = max(counts.items(), key=lambda kv: kv[1])
    feet_per_inch_on_paper = den / num  # e.g. 1/4" = 1'  -> 1 paper-inch = 4 ft
    feet_per_pt = feet_per_inch_on_paper / 72.0
    return feet_per_pt, f"{num}/{den}\" = 1'-0\""


# ------------------------------------------------------------------ words --

def extract_dim_words(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    words = page.get_text("words")
    doc.close()
    dims = []
    # group consecutive words on the same line (block,line) that together
    # form one dimension string, e.g. "26'-8" + "1/4\"" or "3'-0\"" alone
    by_line = defaultdict(list)
    for w in words:
        x0, y0, x1, y1, txt, block, line, wn = w
        by_line[(block, line)].append((wn, x0, y0, x1, y1, txt))
    for key, items in by_line.items():
        items.sort()
        i = 0
        while i < len(items):
            _, x0, y0, x1, y1, txt = items[i]
            if re.match(r"^\d+'-?\d*\"?$", txt):
                # try to merge a trailing fraction token like '1/4"'
                feet_in = txt
                bx0, by0, bx1, by1 = x0, y0, x1, y1
                j = i + 1
                if j < len(items):
                    _, jx0, jy0, jx1, jy1, jtxt = items[j]
                    if re.match(r"^\d/\d\"?$", jtxt) and (jx0 - x1) < (x1 - x0) * 1.5 + 20:
                        feet_in = feet_in + " " + jtxt
                        bx1, by1 = jx1, jy1
                        i = j
                dims.append(dict(text=feet_in, bbox=(bx0, by0, bx1, by1)))
            i += 1
    return dims


def parse_ft_in(s):
    """'26\'-8 1/4"' -> feet (float)."""
    s = s.replace('"', '').strip()
    m = re.match(r"(\d+)'-?(\d+)?(?:\s+(\d+)/(\d+))?", s)
    if not m:
        return None
    feet = int(m.group(1))
    inches = int(m.group(2)) if m.group(2) else 0
    frac = 0.0
    if m.group(3):
        frac = int(m.group(3)) / int(m.group(4))
    return feet + (inches + frac) / 12.0


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
        walls, dom_angle, thick_set = wall_candidates(extracted)
        result["n_wall_candidates_raw"] = len(walls)
        result["dominant_angle_deg"] = round(dom_angle, 3)
        result["stroke_width_clusters_used"] = sorted(thick_set)

        walls_clean, n_hatch_dropped = suppress_hatches(walls, extracted["pw"])
        result["n_hatch_segments_dropped"] = n_hatch_dropped
        result["n_wall_candidates_clean"] = len(walls_clean)

        lines, gap_info = snap_and_close(
            walls_clean, extracted["arcs"], extracted["pw"], feet_per_pt=feet_per_pt
        )
        result["gap_closing"] = gap_info

        min_sqft, max_sqft = 15, 5000
        rooms_all, n_faces = polygonize_rooms(
            lines, extracted["pw"], extracted["ph"], min_sqft, max_sqft, feet_per_pt
        )
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

        # self-audit
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

        rooms_json = []
        for i, poly in enumerate(sorted(main_rooms, key=lambda p: -p.area)):
            sqft = poly.area * feet_per_pt ** 2
            rooms_json.append(dict(
                room_idx=i,
                sqft=round(sqft, 1),
                polygon_pts=[[round(x, 1), round(y, 1)] for x, y in poly.exterior.coords],
                confidence="medium",
            ))
        result["rooms"] = rooms_json

        # dimension-string grading: associate printed dims near room edges
        dims = extract_dim_words(pdf_path, page_index)
        grading = grade_rooms(main_rooms, dims, feet_per_pt)
        result["grading_table"] = grading

        overlay_path = os.path.join(OUT_DIR, f"overlay_{tag}.png")
        render_overlay(pdf_path, page_index, main_rooms, other_clusters, rooms_all,
                        rooms_json, overlay_path)
        result["overlay_path"] = os.path.relpath(overlay_path, ROOT)
        result["verdict"] = "GOOD"
        print(json.dumps({k: v for k, v in result.items() if k not in ("rooms",)}, indent=2, default=str))
        return result
    finally:
        pass  # PDF removed centrally in main() after both pages if shared; see main


def nearest_dim_for_edge(p0, p1, dims, feet_per_pt, max_dist):
    """Find a printed dimension string whose bbox lies near the edge p0-p1
    and is roughly aligned with it (horizontal edge <-> horizontal-ish text
    position, vertical edge <-> vertical)."""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    edge_len_ft = seg_len(p0, p1) * feet_per_pt
    horizontal = abs(p1[0] - p0[0]) >= abs(p1[1] - p0[1])
    best = None
    best_d = max_dist
    for dm in dims:
        bx0, by0, bx1, by1 = dm["bbox"]
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        # project onto edge line, check perpendicular distance + within span
        if horizontal:
            if not (min(p0[0], p1[0]) - max_dist / 2 <= cx <= max(p0[0], p1[0]) + max_dist / 2):
                continue
            d = abs(cy - my)
        else:
            if not (min(p0[1], p1[1]) - max_dist / 2 <= cy <= max(p0[1], p1[1]) + max_dist / 2):
                continue
            d = abs(cx - mx)
        if d < best_d:
            val = parse_ft_in(dm["text"])
            if val is None:
                continue
            best_d = d
            best = (dm["text"], val)
    return best, edge_len_ft


def grade_rooms(main_rooms, dims, feet_per_pt, n_target=5):
    """For the largest N rooms, try to match width & length printed
    dimension strings to two roughly-perpendicular edges; report computed
    (polygon) sqft vs printed-dim-derived sqft and % error."""
    rows = []
    rooms_sorted = sorted(main_rooms, key=lambda p: -p.area)
    for poly in rooms_sorted:
        if len(rows) >= n_target:
            break
        coords = list(poly.exterior.coords)[:-1]
        if len(coords) < 4:
            continue
        # take min-rotated-rect-ish approach: use bbox edges as proxy width/len
        minx, miny, maxx, maxy = poly.bounds
        w_pt = maxx - minx
        h_pt = maxy - miny
        computed_sqft = poly.area * feet_per_pt ** 2
        max_dist = 0.02 * (w_pt + h_pt)  # search radius scaled to room size

        # search all 4 bbox edges for a matching horizontal / vertical dim
        top = ((minx, miny), (maxx, miny))
        bottom = ((minx, maxy), (maxx, maxy))
        left = ((minx, miny), (minx, maxy))
        right = ((maxx, miny), (maxx, maxy))

        h_match, h_edge_len_ft = None, None
        for edge in (top, bottom):
            m, edge_len_ft = nearest_dim_for_edge(*edge, dims, feet_per_pt, max_dist * 4)
            if m:
                h_match, h_edge_len_ft = m, edge_len_ft
                break
        v_match, v_edge_len_ft = None, None
        for edge in (left, right):
            m, edge_len_ft = nearest_dim_for_edge(*edge, dims, feet_per_pt, max_dist * 4)
            if m:
                v_match, v_edge_len_ft = m, edge_len_ft
                break

        row = dict(
            room_rank=len(rows) + 1,
            computed_sqft=round(computed_sqft, 1),
            bbox_w_ft=round(w_pt * feet_per_pt, 2),
            bbox_h_ft=round(h_pt * feet_per_pt, 2),
        )
        if h_match:
            row["printed_width_dim"] = h_match[0]
            row["printed_width_ft"] = round(h_match[1], 2)
            row["width_pct_error"] = round(100 * (row["bbox_w_ft"] - h_match[1]) / h_match[1], 1)
        if v_match:
            row["printed_height_dim"] = v_match[0]
            row["printed_height_ft"] = round(v_match[1], 2)
            row["height_pct_error"] = round(100 * (row["bbox_h_ft"] - v_match[1]) / v_match[1], 1)
        if h_match and v_match:
            printed_sqft = h_match[1] * v_match[1]
            row["printed_dim_sqft"] = round(printed_sqft, 1)
            row["sqft_pct_error"] = round(100 * (computed_sqft - printed_sqft) / printed_sqft, 1)
        rows.append(row)
    return rows


def render_overlay(pdf_path, page_index, main_rooms, other_clusters, rooms_all, rooms_json,
                    out_path, target_w=1800):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    zoom = target_w / page.rect.width
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    rooms_sorted = sorted(main_rooms, key=lambda p: -p.area)
    for rj, poly in zip(rooms_json, rooms_sorted):
        pts = [(x * zoom, y * zoom) for x, y in poly.exterior.coords]
        draw.polygon(pts, fill=(0, 160, 0, 90), outline=(0, 100, 0, 255))
        c = poly.centroid
        draw.text((c.x * zoom, c.y * zoom), f"{rj['sqft']:.0f} SF", fill=(0, 0, 0, 255), font=font)

    for idxs in other_clusters:
        for i in idxs:
            poly = rooms_all[i]
            pts = [(x * zoom, y * zoom) for x, y in poly.exterior.coords]
            draw.polygon(pts, fill=(200, 0, 0, 70), outline=(150, 0, 0, 255))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(out_path)
    doc.close()


def main():
    s3 = r2_client()
    results = []
    for page_def in PAGES:
        r = process_page(s3, page_def)
        results.append(r)

    with open(os.path.join(OUT_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    # clean up fetched PDFs -- disk is tight
    for f in os.listdir(PDF_TMP_DIR):
        os.remove(os.path.join(PDF_TMP_DIR, f))
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass

    print("\n=== DONE ===")
    for r in results:
        print(r["permit"], r.get("verdict"), r.get("total_sqft_main_cluster"))


if __name__ == "__main__":
    main()
