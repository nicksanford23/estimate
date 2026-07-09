#!/usr/bin/env python3
"""Probe 28 -- geometry engine v3. Adds the ANCHOR-CLUSTER MEMBERSHIP FILTER
(probe27's recommended lever #2) on TOP of the v2 engine (geometry_v2.py,
imported unchanged -- v2 is still callable standalone for comparison).

  FIX 1 (this module): ANCHOR-CLUSTER MEMBERSHIP FILTER. After v2's
  polygonize + cavity/hatch kill, group the surviving room-sized polygons by
  connected wall-graph component (reusing probe2_sf.cluster_by_touching --
  polygons that share an edge/touch belong to the same closed wall graph).
  Any component that contains ZERO of the page's addressable room-code
  anchors (anywhere in the component, not just the polygon being judged) is
  demoted to ARTIFACT: removed before grading, never summed as "unlabeled/
  fabricated" SF, never a matching candidate. This targets probe27's named
  next lever directly -- same-sheet other-building/other-plan blobs that
  have no reason to be part of THIS permit's takeoff.

  Failure mode this can cause (watched explicitly, see probe28_regrade.py's
  false-positive report): a legitimate room cluster whose labels are
  VECTORIZED (drawn as filled glyphs / stroke text, not real PDF text) would
  produce zero `words`-based anchors and get wrongly killed. Operational
  proxy for "is this actually part of the same drawing, not a false kill":
  cluster contains >=1 polygon in the room-size band (30-2000 sf) AND its
  footprint materially overlaps the page's "principal drawing region" (the
  convex hull of every ANCHORED cluster, lightly buffered). Reported as
  `anchor_cluster_false_positive_suspects` for a human to check the overlay.

  FIX 2 (unit/corridor merge guard) is grading-time logic that also needs
  truth-schedule unit/building groupings -- it lives in probe28_regrade.py
  (grader-side), same architectural split as probe27's fixes 3/4. This
  module only exposes the reusable geometry primitive it needs:
  `build_arcs_only_rooms()` -- the page's room polygons if the generic
  (non-arc) gap closer were disabled, used as the "local re-split" oracle.
"""
import math
import os
import sys

from shapely.geometry import Point
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import snap_and_close, polygonize_rooms, cluster_by_touching  # noqa: E402
from geometry_v2 import run_geometry_engine_v2  # noqa: E402

ROOM_BAND_MIN_SF = 30
ROOM_BAND_MAX_SF = 2000
PRINCIPAL_REGION_OVERLAP_FRAC = 0.3  # fraction of a killed cluster's own
                                     # area that must fall inside the
                                     # principal drawing region to flag it
                                     # as a possible false-kill suspect


# ------------------------------------------------------- anchor clustering --

def filter_anchor_clusters(rooms_all, anchor_points, feet_per_pt):
    """rooms_all: list of shapely Polygons (already cavity/hatch filtered).
    anchor_points: flat list of (x, y) page-pt tuples -- every addressable
    room-code anchor found on this page (any token, not per-polygon).

    Returns dict(kept_idx, killed_idx, clusters, cluster_has_anchor,
    principal_region, false_positive_suspects) -- all indices are positions
    in the INPUT rooms_all list.
    """
    clusters = cluster_by_touching(rooms_all)
    anchor_pts = [Point(x, y) for x, y in anchor_points]

    cluster_has_anchor = []
    for grp in clusters:
        has = False
        for i in grp:
            poly = rooms_all[i]
            for p in anchor_pts:
                if poly.contains(p):
                    has = True
                    break
            if has:
                break
        cluster_has_anchor.append(has)

    kept_idx, killed_idx = [], []
    for grp, has in zip(clusters, cluster_has_anchor):
        (kept_idx if has else killed_idx).extend(grp)
    kept_idx.sort()
    killed_idx.sort()

    # principal drawing region: convex hull of every ANCHORED cluster's
    # polygons, buffered outward a bit (drawings extend past labeled rooms:
    # corridors, unlabeled closets, exterior walls)
    principal_region = None
    if kept_idx:
        kept_polys = [rooms_all[i] for i in kept_idx]
        hull = unary_union(kept_polys).convex_hull
        buf_pt = 0.10 * math.sqrt(hull.area) if hull.area > 0 else 0
        principal_region = hull.buffer(buf_pt)

    false_positive_suspects = []
    for grp, has in zip(clusters, cluster_has_anchor):
        if has:
            continue
        polys = [rooms_all[i] for i in grp]
        sizes = [p.area * feet_per_pt ** 2 for p in polys]
        in_room_band = any(ROOM_BAND_MIN_SF <= s <= ROOM_BAND_MAX_SF for s in sizes)
        overlap_frac = 0.0
        if principal_region is not None:
            u = unary_union(polys)
            if u.area > 0:
                overlap_frac = u.intersection(principal_region).area / u.area
        if in_room_band and overlap_frac >= PRINCIPAL_REGION_OVERLAP_FRAC:
            false_positive_suspects.append(dict(
                idxs=grp, n_polys=len(grp),
                total_sf=round(sum(sizes), 1),
                max_poly_sf=round(max(sizes), 1),
                overlap_frac=round(overlap_frac, 2)))

    return dict(kept_idx=kept_idx, killed_idx=killed_idx, clusters=clusters,
                 cluster_has_anchor=cluster_has_anchor,
                 principal_region=principal_region,
                 false_positive_suspects=false_positive_suspects)


def run_geometry_engine_v3(extracted, feet_per_pt, anchor_points,
                            min_sqft=15, max_sqft=5000,
                            enable_anchor_filter=True):
    """v2 engine, then the anchor-cluster membership filter. `anchor_points`
    must be computed by the caller BEFORE this call (plain PDF text lookup,
    independent of geometry) -- see probe28_regrade.py."""
    out2, diag = run_geometry_engine_v2(extracted, feet_per_pt, min_sqft, max_sqft)
    diag["engine_version"] = "v3"
    if out2 is None:
        return None, diag

    rooms_all = out2["rooms_all"]
    if not enable_anchor_filter:
        diag["anchor_cluster_filter_applied"] = False
        return out2, diag

    ac = filter_anchor_clusters(rooms_all, anchor_points, feet_per_pt)
    killed_polys = [rooms_all[i] for i in ac["killed_idx"]]
    killed_sf = sum(p.area * feet_per_pt ** 2 for p in killed_polys)

    diag["anchor_cluster_filter_applied"] = True
    diag["anchor_cluster_n_clusters_total"] = len(ac["clusters"])
    diag["anchor_cluster_n_clusters_killed"] = sum(1 for h in ac["cluster_has_anchor"] if not h)
    diag["anchor_cluster_n_polys_killed"] = len(ac["killed_idx"])
    diag["anchor_cluster_sf_killed"] = round(killed_sf, 1)
    diag["anchor_cluster_false_positive_suspects"] = ac["false_positive_suspects"]

    rooms_all_new = [rooms_all[i] for i in ac["kept_idx"]]
    out2["rooms_all_pre_anchor_filter"] = rooms_all
    out2["rooms_all"] = rooms_all_new
    out2["anchor_cluster_diag"] = ac
    return out2, diag


# --------------------------------------------------- arcs-only resplit oracle

def build_arcs_only_rooms(walls_final, arcs, pw, ph, feet_per_pt,
                           min_sqft=15, max_sqft=5000):
    """The page's room polygons if the v2 generic gap closer had never run
    (arc-chord door closing only -- the always-safe mechanism). Used by the
    grader as the "local re-split" oracle for merge candidates: a candidate
    connector that over-bridged two rooms in v2 simply won't exist here, so
    if this arcs-only graph closes a sub-polygon per anchor inside a v2
    merge blob's footprint, the merge can be safely un-done."""
    lines_ls, _ = snap_and_close(walls_final, arcs, pw, feet_per_pt=None)
    rooms, n_faces = polygonize_rooms(lines_ls, pw, ph, min_sqft, max_sqft, feet_per_pt)
    return rooms
