#!/usr/bin/env python3
"""Probe 27 -- geometry engine v2. Two targeted fixes on TOP of the
probe2b_sf/probe26 two-tier engine (imported, unchanged):

  1. BOUNDED, DENSITY-GATED generic gap closer. probe2b/probe26 disabled the
     generic "close any two endpoints within door_ft" step entirely (passed
     feet_per_pt=None into snap_and_close) because at the two-tier engine's
     candidate density (minor tier ~4x's segment count) it produced
     thousands of spurious connectors and collapsed/fragmented the room
     graph (see probe2b_sf.py docstring point 4; STATE.md 07-08 sprint).
     Here we reinstate it, but (a) TIGHTER -- 3.0-3.5ft instead of 4.5ft,
     and (b) DENSITY-GATED -- a candidate connector is only added if the
     local wall-candidate density around its midpoint is below a threshold
     derived from THAT PAGE's own density distribution (a page-relative
     percentile, not a hardcoded cross-project constant -- floor-plan
     complexity varies too much per project for one global number to be
     meaningful; see calibration note below). In practice this closes
     normal door gaps in the ordinary-density ~80% of a sheet while leaving
     the genuinely cluttered/hatched top slice (service cores, plumbing
     chases) untouched, where only the arc-chord closer (unconditional,
     unchanged) still applies.
  2. CAVITY/HATCH POLYGON FILTER. Kill closed polygons that are structurally
     wall cavities or hatch-strip artifacts rather than rooms: elongated,
     wall-thickness-width, roughly-constant-width shapes (a), or repeating
     parallel-strip families at regular spacing (b). (c) "enclosed within a
     double-line wall band" reduces to the same elongated-constant-width
     test geometrically, so (a)/(c) share one test.

Both fixes are additive: importing probe2_sf/probe2b_sf UNCHANGED, calling
run_geometry_engine_v2() in place of probe26_truth_grading's
run_geometry_engine(). The confident-wrong guard and merge-scoring fix
(probe27 fixes 3/4) live in the GRADER (scripts/probe27_regrade.py), not
here -- they are scoring-time decisions, not geometry.

Calibration, cavity/hatch filter (probe27, see experiments/probe27_closure_fix.md
for the full isolated sweep): tested directly against probe26's exact 100
"unlabeled polygon" / 7,608 SF population (the probe's own named target), at
max_width_ft/min_aspect grid points. Zero-false-positive operating point
(no MATCHED/MERGED truth-room polygon ever killed) tops out at
max_width_ft=6.0, min_aspect=3.0 -> kills 28.3% of that SF (2,151 of 7,608),
NOT the >80% aspiration -- loosening further (max_width_ft up to 8, min_aspect
down to 2.5) plateaus around 31% and starts costing false positives (2 real
room polygons killed). DIAGNOSIS: roughly 70% of that flagged SF is not
elongated/hatch-shaped at all -- it is large, blob-shaped, multi-room-scale
polygons from a DIFFERENT cause (same-sheet other-building/other-plan
clusters -- e.g. a roof plan or an adjacent unit's whole footprint on the
same sheet closing as one big polygon that just contains no ADDRESSABLE
room-code token from this permit's target list; visually confirmed in
overlay_24-06748-RNVS_7372349_p7_v2.png). That is a real, separate failure
mode this filter's shape test cannot and should not try to catch (it is not
a cavity or a hatch -- it is a real closed room-sized space, just for a
different unit/building than the one being graded). Reported honestly in
probe27, not forced.

Calibration, gap closer: radius-based
wall-candidate density (segments within 5ft of a point) was sampled across
all 7 probe26 target pages + the bank canary (14-11290 doc 1494156 p3).
Every page's own p50-p90 density band overlaps every other page's -- there
is no single absolute count that means "dense" on one page but "normal" on
another (a busy 25-room townhouse page and the bank's known-good branch
page have near-identical raw density distributions). A PAGE-RELATIVE gate
(skip closing in a page's own top density_pctile) is therefore the only
form of this idea that doesn't require re-tuning per project. Default
density_pctile=80 chosen because it reliably isolates the densest, most
repetitive regions (hatch/cavity clusters, plumbing chases) on every
tested page while leaving >=80% of each page's area eligible for normal
door-gap closing.
"""
import math
import os
import sys
from collections import defaultdict

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union, polygonize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import seg_len  # noqa: E402
from probe2b_sf import two_tier_wall_candidates, find_parallel_pairs, admit_minor  # noqa: E402

# --------------------------------------------------------------- constants --
GAP_FT = 3.25                # tighter than the old disabled 4.5ft closer
DENSITY_RADIUS_FT = 5.0      # neighborhood radius for the density gate
DENSITY_PCTILE = 80          # page-relative: gate is this page's own Nth pct


# ------------------------------------------------------------ density gate --

def build_density_index(walls, feet_per_pt, radius_ft=DENSITY_RADIUS_FT):
    """Grid-bucket wall-candidate segment MIDPOINTS so density-at-point
    queries are O(1) amortized. Returns (buckets, cell_pt, radius_pt)."""
    radius_pt = radius_ft / feet_per_pt
    cell = radius_pt
    buckets = defaultdict(list)
    mids = []
    for p0, p1, L, w in walls:
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        buckets[(int(mx // cell), int(my // cell))].append((mx, my))
        mids.append((mx, my))
    return buckets, cell, radius_pt, mids


def density_at(buckets, cell, radius_pt, x, y):
    cx, cy = int(x // cell), int(y // cell)
    c = 0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for (qx, qy) in buckets.get((cx + dx, cy + dy), []):
                if math.hypot(qx - x, qy - y) <= radius_pt:
                    c += 1
    return c


def page_density_threshold(walls, feet_per_pt, buckets, cell, radius_pt,
                            pctile=DENSITY_PCTILE):
    """This page's own density distribution -> the Nth percentile value,
    used as the gate cutoff (page-relative, not a global constant)."""
    if not walls:
        return 0
    vals = sorted(density_at(buckets, cell, radius_pt, mx, my)
                   for p0, p1, L, w in walls
                   for mx, my in [((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)])
    idx = min(len(vals) - 1, int(pctile / 100.0 * len(vals)))
    return vals[idx]


def snap_and_close_v2(walls, arcs, pw, feet_per_pt, gap_ft=GAP_FT,
                       density_radius_ft=DENSITY_RADIUS_FT,
                       density_pctile=DENSITY_PCTILE,
                       snap_tol_frac=0.0025):
    """probe2_sf.snap_and_close, with the generic gap closer reinstated at a
    tighter gap_ft AND gated by local, page-relative wall-candidate density.
    Arc-chord closing (door swings) is unconditional, exactly as upstream --
    it is the ALREADY-PROVEN-SAFE mechanism (skill step 5); only the
    generic closer is new/gated here."""
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

    added_from_arcs = 0
    for p0, p1 in arcs:
        sp0, sp1 = snap_pt(p0), snap_pt(p1)
        if sp0 != sp1:
            lines.append(LineString([sp0, sp1]))
            added_from_arcs += 1

    added_gap_closers = 0
    skipped_dense = 0
    gap_pt = (gap_ft / feet_per_pt) if feet_per_pt else 0.0
    if gap_pt > 0 and walls:
        buckets_d, cell_d, radius_pt_d, _ = build_density_index(
            walls, feet_per_pt, density_radius_ft)
        gate = page_density_threshold(walls, feet_per_pt, buckets_d, cell_d,
                                       radius_pt_d, density_pctile)

        uniq_endpoints = list(set(endpoints))
        cell = max(gap_pt, tol)
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
                        if not (tol < d <= gap_pt):
                            continue
                        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
                        dens = density_at(buckets_d, cell_d, radius_pt_d, mx, my)
                        if dens > gate:
                            skipped_dense += 1
                            closed_pairs.add(key)
                            continue
                        lines.append(LineString([p, q]))
                        closed_pairs.add(key)
                        added_gap_closers += 1

    return lines, dict(added_from_arcs=added_from_arcs,
                        added_gap_closers=added_gap_closers,
                        skipped_dense=skipped_dense)


# ------------------------------------------------------- cavity/hatch kill --

def _min_rot_rect_dims(poly):
    mrr = poly.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)
    if len(coords) < 4:
        return None, None
    d1 = seg_len(coords[0], coords[1])
    d2 = seg_len(coords[1], coords[2])
    return (min(d1, d2), max(d1, d2))  # (short, long) in page-pt units


def is_elongated_constant_width(poly, feet_per_pt, max_width_ft=6.0,
                                 min_aspect=3.0):
    """(a)+(c): wall cavities and double-line-wall-band enclosures are both,
    geometrically, thin elongated rectangles at wall-thickness widths --
    short side of the min-rotated-rect < max_width_ft AND long/short
    aspect >= min_aspect. This does NOT require parallel-pair evidence
    explicitly; it is the shape signature both failure modes share."""
    short_pt, long_pt = _min_rot_rect_dims(poly)
    if short_pt is None or short_pt <= 0:
        return False
    short_ft = short_pt * feet_per_pt
    aspect = long_pt / short_pt
    return short_ft <= max_width_ft and aspect >= min_aspect


def find_hatch_polygon_family(candidates, feet_per_pt, spacing_tol_ft=1.5,
                               min_group=3):
    """(b): repeating parallel strip family. Group small candidate polygons
    by (orientation bucket, rounded short-width), then check for >=min_group
    members at roughly regular perpendicular spacing along their shared
    long axis -- the same "regular pitch" signature as segment-level hatch
    suppression, applied to polygons instead of raw segments."""
    groups = defaultdict(list)
    info = {}
    for i, poly in enumerate(candidates):
        mrr = poly.minimum_rotated_rectangle
        coords = list(mrr.exterior.coords)[:-1]
        if len(coords) != 4:
            continue
        d01 = seg_len(coords[0], coords[1])
        d12 = seg_len(coords[1], coords[2])
        if d01 >= d12:
            long_edge = (coords[0], coords[1])
            short_pt = d12
        else:
            long_edge = (coords[1], coords[2])
            short_pt = d01
        dx, dy = long_edge[1][0] - long_edge[0][0], long_edge[1][1] - long_edge[0][1]
        Lm = math.hypot(dx, dy) or 1.0
        tx, ty = dx / Lm, dy / Lm
        nx, ny = -ty, tx
        cen = poly.centroid
        perp = cen.x * nx + cen.y * ny
        along = cen.x * tx + cen.y * ty
        orient_key = round(math.degrees(math.atan2(ty, tx)) % 180 / 5.0)
        width_key = round(short_pt * feet_per_pt / 0.25)  # quarter-ft bins
        key = (orient_key, width_key)
        groups[key].append(i)
        info[i] = (perp, along)

    hatch_idxs = set()
    for key, idxs in groups.items():
        if len(idxs) < min_group:
            continue
        # sub-cluster by tangential (along-axis) proximity into RUNS, then
        # check perpendicular-offset regularity within a run (a true hatch
        # family repeats at constant perpendicular pitch along one run)
        idxs_sorted = sorted(idxs, key=lambda i: info[i][1])
        run = [idxs_sorted[0]]
        runs = []
        for i in idxs_sorted[1:]:
            if abs(info[i][1] - info[run[-1]][1]) <= (spacing_tol_ft / feet_per_pt) * 6:
                run.append(i)
            else:
                runs.append(run)
                run = [i]
        runs.append(run)
        for r in runs:
            if len(r) < min_group:
                continue
            offs = sorted(info[i][0] for i in r)
            gaps = [offs[k + 1] - offs[k] for k in range(len(offs) - 1)]
            if not gaps:
                continue
            mean_gap = sum(gaps) / len(gaps)
            if mean_gap <= 0:
                continue
            var = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
            if (var ** 0.5) <= 0.5 * mean_gap:
                hatch_idxs.update(r)
    return hatch_idxs


def filter_cavity_hatch(rooms_all, feet_per_pt):
    """Kill (a)/(c) elongated-constant-width polygons and (b) hatch-strip
    families. Returns (kept_rooms, killed) where killed is a list of dicts
    {poly, sqft, reason} for reporting/verification."""
    killed = []
    kept_idx = []
    elongated_flags = []
    for i, poly in enumerate(rooms_all):
        el = is_elongated_constant_width(poly, feet_per_pt)
        elongated_flags.append(el)
        if el:
            sqft = poly.area * feet_per_pt ** 2
            killed.append(dict(idx=i, sqft=round(sqft, 1),
                                reason="elongated_constant_width"))
        else:
            kept_idx.append(i)

    # hatch family check runs over the FULL candidate set (not just already-
    # elongated ones) since hatch strips can be squarer sub-blocks that only
    # reveal themselves as a repeating family once grouped
    remaining = [rooms_all[i] for i in kept_idx]
    hatch_local = find_hatch_polygon_family(remaining, feet_per_pt)
    hatch_global = {kept_idx[j] for j in hatch_local}
    final_kept = [i for i in kept_idx if i not in hatch_global]
    for i in sorted(hatch_global):
        sqft = rooms_all[i].area * feet_per_pt ** 2
        killed.append(dict(idx=i, sqft=round(sqft, 1), reason="hatch_family"))

    kept_rooms = [rooms_all[i] for i in final_kept]
    return kept_rooms, killed, final_kept


# ------------------------------------------------------------- full engine --

def run_geometry_engine_v2(extracted, feet_per_pt, min_sqft=15, max_sqft=5000):
    """Same shape as probe26_truth_grading.run_geometry_engine but calling
    the v2 gap closer + the cavity/hatch filter. Returns (out_dict, diag)
    like the v1 engine, plus diag fields for the new steps."""
    from probe2_sf import polygonize_rooms  # local import, unchanged fn

    pw, ph = extracted["pw"], extracted["ph"]
    diag = {}
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

    # FIX 1: density-gated generic closer + unconditional arc-chord closer
    lines_ls, gap_info = snap_and_close_v2(
        walls_final, extracted["arcs"], pw, feet_per_pt=feet_per_pt)
    diag["gap_closing_v2"] = gap_info

    rooms_pre_filter, n_faces = polygonize_rooms(
        lines_ls, pw, ph, min_sqft, max_sqft, feet_per_pt)

    # FIX 2: cavity/hatch polygon filter
    rooms_all, killed, kept_idx = filter_cavity_hatch(rooms_pre_filter, feet_per_pt)
    diag["n_cavity_hatch_killed"] = len(killed)
    diag["cavity_hatch_killed_sf"] = round(sum(k["sqft"] for k in killed), 1)
    diag["cavity_hatch_killed_detail"] = killed

    diag.update(
        n_major_clean=len(major_clean), n_minor_clean=len(minor_clean),
        n_parallel_pairs=len(pairs), n_minor_admitted=n_added,
        n_polygon_faces_total=n_faces,
        n_rooms_pre_cavity_filter=len(rooms_pre_filter),
        n_rooms_all=len(rooms_all),
        dominant_angle_deg=round(tiers["dom"], 3),
    )
    if not rooms_all:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = "no room-sized polygons closed at all (v2)"
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
                lines_ls=lines_ls, walls_final=walls_final,
                rooms_pre_filter=rooms_pre_filter), diag
