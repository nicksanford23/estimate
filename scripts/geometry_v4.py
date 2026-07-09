#!/usr/bin/env python3
"""Probe 29 (Task A) -- geometry engine v4. Fixes probe28's confirmed
false-positive mechanism (same-building wall-graph fragmentation) with a
PROXIMITY-based cluster grouping in front of the anchor-cluster membership
filter, plus a REVIEW_KILLED bucket for whatever still can't be reconnected.

  FIX (this module): PROXIMITY-BASED CLUSTER GROUPING. v3's
  `filter_anchor_clusters` (geometry_v3.py) grouped surviving room-sized
  polygons by STRICT wall-graph connectivity (`probe2_sf.cluster_by_touching`
  -- shares an edge or distance < 1e-6). Probe28 confirmed this is unsafe:
  the TARGET building's own wall graph commonly fragments into multiple
  disconnected islands (imperfect closure is this whole pipeline's NORMAL
  failure mode, not a rare edge case) -- e.g. 24-06233 p10 Building B's own
  upper-floor rooms (B201/B203/B204 + an unlabeled corridor/attic blob) form
  a wall-graph "island" separate from the matched B202 polygon purely
  because one partition failed to close, not because they belong to a
  different building.

  `cluster_by_proximity` reuses the EXACT gap-tolerance scale already
  established for wall-closing (`geometry_v2.GAP_FT` = 3.25ft, the
  density-gated door-gap-closing radius) as the union threshold BEFORE
  judging "zero anchors = off-scope": two polygons are grouped together if
  they are within `gap_ft` of one another (not only if they literally
  touch). This lets a same-building island inherit an anchor from a nearby
  cluster across the same small gap that failed to close as a WALL,
  without touching the different-building/other-plan-blob mechanism the
  original filter targeted (those blobs sit measurably farther apart than
  one door-gap width -- see probe29_continuity_fix.md for the measured
  gap-distance distribution that justifies reusing this scale rather than
  inventing a new one).

  SAFETY NET (still needed, per the task): a cluster that remains
  anchor-less even after proximity grouping is still demoted -- but no
  longer silently discarded like v3 did. It is split into two buckets:
    - REVIEW_KILLED: flagged `false_positive_suspect` (v3's own heuristic,
      reused unchanged -- room-sized polygon + material overlap with the
      principal drawing region). Excluded from auto-quantity/fabricated-SF
      sums (same practical effect as ARTIFACT on that number), but
      surfaced with the suspect flag and tracked by the grader as its own
      bucket instead of vanishing.
    - ARTIFACT: not suspect -- discarded exactly as v3 did (preserves v3's
      fabricated-SF win on the confirmed different-building/hatch cases
      the suspect heuristic correctly leaves alone).

  v3 (geometry_v3.py) is UNCHANGED and still directly importable/callable
  for comparison -- this module imports it, never modifies it.
"""
import math
import os
import sys

from shapely.geometry import Point
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry_v2 import run_geometry_engine_v2, GAP_FT  # noqa: E402
from geometry_v3 import (  # noqa: E402
    ROOM_BAND_MIN_SF, ROOM_BAND_MAX_SF, PRINCIPAL_REGION_OVERLAP_FRAC,
    build_arcs_only_rooms,  # re-exported, unchanged -- fix 2's oracle is geometry-agnostic
)

# Reuse the density-gated closer's own door-gap scale as the proximity
# grouping tolerance -- not a new constant invented for this purpose.
PROXIMITY_GAP_FT = GAP_FT


# ---------------------------------------------------- proximity clustering --

def cluster_by_proximity(rooms, gap_pt):
    """Same union-find shape as probe2_sf.cluster_by_touching, generalized:
    two polygons are grouped if they touch/overlap (distance < 1e-6, the
    original test) OR their distance is <= gap_pt -- the same physical
    tolerance already trusted to close a real door gap as a WALL, reused
    one step earlier in the pipeline (grouping) rather than a new
    threshold invented for this purpose. O(n^2) distance checks, same cost
    profile as cluster_by_touching (fine at room-polygon-per-page counts:
    tens, not thousands)."""
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
            if rooms[i].distance(rooms[j]) <= gap_pt:
                union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def filter_anchor_clusters_v4(rooms_all, anchor_points, feet_per_pt,
                               gap_ft=PROXIMITY_GAP_FT):
    """v3's filter_anchor_clusters, with PROXIMITY-based grouping in place
    of strict touching, and killed clusters split into REVIEW_KILLED
    (suspect) vs ARTIFACT (not suspect) instead of one undifferentiated
    kill bucket."""
    gap_pt = gap_ft / feet_per_pt if feet_per_pt else 0.0
    clusters = cluster_by_proximity(rooms_all, gap_pt)
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
    # polygons, buffered outward a bit (same as v3)
    principal_region = None
    if kept_idx:
        kept_polys = [rooms_all[i] for i in kept_idx]
        hull = unary_union(kept_polys).convex_hull
        buf_pt = 0.10 * math.sqrt(hull.area) if hull.area > 0 else 0
        principal_region = hull.buffer(buf_pt)

    review_killed_idx, artifact_idx = [], []
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
        is_suspect = in_room_band and overlap_frac >= PRINCIPAL_REGION_OVERLAP_FRAC
        if is_suspect:
            review_killed_idx.extend(grp)
            false_positive_suspects.append(dict(
                idxs=grp, n_polys=len(grp), total_sf=round(sum(sizes), 1),
                max_poly_sf=round(max(sizes), 1), overlap_frac=round(overlap_frac, 2)))
        else:
            artifact_idx.extend(grp)
    review_killed_idx.sort()
    artifact_idx.sort()

    return dict(kept_idx=kept_idx, killed_idx=killed_idx, clusters=clusters,
                cluster_has_anchor=cluster_has_anchor,
                principal_region=principal_region,
                false_positive_suspects=false_positive_suspects,
                review_killed_idx=review_killed_idx, artifact_idx=artifact_idx,
                gap_ft=gap_ft)


def run_geometry_engine_v4(extracted, feet_per_pt, anchor_points,
                            min_sqft=15, max_sqft=5000,
                            enable_anchor_filter=True, gap_ft=PROXIMITY_GAP_FT):
    """v2 engine, then the PROXIMITY-gated anchor-cluster membership filter
    (probe29's fix on top of probe28's v3). `anchor_points` must be
    computed by the caller BEFORE this call (plain PDF text lookup,
    independent of geometry) -- see probe29_regrade.py.

    Kept `rooms_all` = polygons whose PROXIMITY cluster contains >=1
    addressable anchor. Anything else is split into REVIEW_KILLED (flagged
    false_positive_suspect, excluded from sums but surfaced) or ARTIFACT
    (discarded silently, as v3)."""
    out2, diag = run_geometry_engine_v2(extracted, feet_per_pt, min_sqft, max_sqft)
    diag["engine_version"] = "v4"
    if out2 is None:
        return None, diag

    rooms_all = out2["rooms_all"]
    if not enable_anchor_filter:
        diag["anchor_cluster_filter_applied"] = False
        return out2, diag

    ac = filter_anchor_clusters_v4(rooms_all, anchor_points, feet_per_pt, gap_ft)
    review_polys = [rooms_all[i] for i in ac["review_killed_idx"]]
    artifact_polys = [rooms_all[i] for i in ac["artifact_idx"]]
    review_sf = sum(p.area * feet_per_pt ** 2 for p in review_polys)
    artifact_sf = sum(p.area * feet_per_pt ** 2 for p in artifact_polys)

    diag["anchor_cluster_filter_applied"] = True
    diag["anchor_cluster_gap_ft"] = gap_ft
    diag["anchor_cluster_n_clusters_total"] = len(ac["clusters"])
    diag["anchor_cluster_n_clusters_killed"] = sum(1 for h in ac["cluster_has_anchor"] if not h)
    diag["anchor_cluster_n_polys_killed"] = len(ac["killed_idx"])
    diag["anchor_cluster_sf_killed"] = round(review_sf + artifact_sf, 1)
    diag["anchor_cluster_n_polys_review_killed"] = len(ac["review_killed_idx"])
    diag["anchor_cluster_sf_review_killed"] = round(review_sf, 1)
    diag["anchor_cluster_n_polys_artifact"] = len(ac["artifact_idx"])
    diag["anchor_cluster_sf_artifact"] = round(artifact_sf, 1)
    diag["anchor_cluster_false_positive_suspects"] = ac["false_positive_suspects"]

    rooms_all_new = [rooms_all[i] for i in ac["kept_idx"]]
    out2["rooms_all_pre_anchor_filter"] = rooms_all
    out2["rooms_all"] = rooms_all_new
    out2["rooms_review_killed"] = review_polys
    out2["rooms_artifact_killed"] = artifact_polys
    out2["anchor_cluster_diag"] = ac
    return out2, diag
