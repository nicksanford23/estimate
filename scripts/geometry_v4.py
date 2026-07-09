#!/usr/bin/env python3
"""Probe 29 (Task A) -- geometry engine v4. Fixes probe28's confirmed
false-positive mechanism (same-building wall-graph fragmentation) with a
PROXIMITY-based reconnection step in front of the anchor-cluster membership
filter, plus a REVIEW_KILLED bucket for whatever still can't be reconnected.

  THE FIX, AS ACTUALLY SHIPPED (revised once during this probe -- see
  "chaining" note below): v3's `filter_anchor_clusters` (geometry_v3.py)
  grouped surviving room-sized polygons by STRICT wall-graph connectivity
  (`probe2_sf.cluster_by_touching` -- shares an edge or distance < 1e-6).
  Probe28 confirmed this is unsafe: the TARGET building's own wall graph
  commonly fragments into disconnected islands (imperfect closure is this
  pipeline's NORMAL failure mode) -- e.g. 24-06233 p10 Building B's own
  upper-floor rooms (B201/B203/B204 + an unlabeled corridor/attic blob)
  form a wall-graph "island" separate from the matched B202 polygon purely
  because one partition failed to close, not because they belong to a
  different building. Measured: that island sits 1.44ft from the ANCHORED
  island containing B202 -- well within the density-gated closer's own
  door-gap scale (`geometry_v2.GAP_FT` = 3.25ft) -- confirming this really
  is the same drawing, just a closure gap, not a different building.

  FIRST ATTEMPT (rejected after measurement, kept here as an honest record
  -- see probe29_continuity_fix.md for the full numbers): grouping ALL
  polygons pairwise by `distance <= gap_pt`, transitively (plain
  union-find over every pair), rescues the confirmed case correctly BUT
  also CHAINS in unrelated, genuinely-distant clusters through the
  rescued blob as an intermediate stepping-stone: three more anchor-less
  islands on the SAME page sit 9.4-11.7ft from the anchored island itself
  (i.e. really are too far to reconnect directly) but only 0.7-1.4ft from
  the rescued 1,177sf blob -- so plain transitive union-find pulls them
  all into one group anyway. Measured cost: fabricated/unlabeled SF nearly
  DOUBLED across the 4-permit regrade (4,004 -> 7,665 SF, +91%), giving
  back a large chunk of probe28's headline win -- failing this probe's own
  success bar ("...WITHOUT giving back a material chunk of the
  fabricated-SF win").

  THE FIX THAT SHIPS: a DIRECTIONAL, single-hop reconnection instead of
  blanket transitive proximity clustering.
    1. Build islands by STRICT touching, exactly as v3 (`cluster_by_touching`,
       unchanged, imported from probe2_sf).
    2. Classify each island anchored/unanchored exactly as v3 (does any
       member polygon contain an addressable anchor point).
    3. For each UNANCHORED island, measure its distance to EVERY anchored
       island's own polygon set (the ORIGINAL anchored footprint, never a
       previously-reconnected one -- this is what prevents chaining: an
       anchor-less island can only reconnect directly to genuine anchored
       ground truth, never piggyback through another anchor-less island).
       If it is within `gap_ft` of EXACTLY ONE distinct anchored island,
       reconnect (kept, inherits that island's anchor). If it is within
       tolerance of >=2 different anchored islands (ambiguous -- could be
       either building) or of none, it is NOT reconnected -- falls through
       to the same false-positive-suspect check v3 used, now split into
       REVIEW_KILLED vs ARTIFACT (see below) instead of one kill bucket.
  This reuses the exact same gap-tolerance scale the task asked for, but
  applies it as a targeted "did this island fail to close onto genuine
  anchored ground truth" test instead of a blanket pairwise union that
  chains through whatever else happens to be nearby.

  SAFETY NET (still needed): an island that remains unreconnected is split:
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
from probe2_sf import cluster_by_touching  # noqa: E402 -- islands, unchanged (v3's own test)
from geometry_v2 import run_geometry_engine_v2, GAP_FT  # noqa: E402
from geometry_v3 import (  # noqa: E402
    ROOM_BAND_MIN_SF, ROOM_BAND_MAX_SF, PRINCIPAL_REGION_OVERLAP_FRAC,
    build_arcs_only_rooms,  # re-exported, unchanged -- fix 2's oracle is geometry-agnostic
)

# Reuse the density-gated closer's own door-gap scale as the proximity
# reconnection tolerance -- not a new constant invented for this purpose.
PROXIMITY_GAP_FT = GAP_FT


# Kept for reference / possible future use elsewhere, but NOT used by
# filter_anchor_clusters_v4 below -- see the module docstring's "first
# attempt (rejected)" note. A blanket pairwise union-find chains distant,
# genuinely-unrelated clusters together through whatever intermediate
# polygon happens to be close to both; the directional reconnection below
# is the fix that actually shipped.
def cluster_by_proximity(rooms, gap_pt):
    """Union-find over ALL pairs within `gap_pt` (plus touching). Chains
    transitively -- rejected as the anchor-cluster grouping mechanism
    (see module docstring), kept only as a documented negative result /
    building block someone might reuse more carefully elsewhere."""
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


def _island_has_anchor(grp, rooms_all, anchor_pts):
    for i in grp:
        poly = rooms_all[i]
        for p in anchor_pts:
            if poly.contains(p):
                return True
    return False


def filter_anchor_clusters_v4(rooms_all, anchor_points, feet_per_pt,
                               gap_ft=PROXIMITY_GAP_FT):
    """v3's filter_anchor_clusters, with a DIRECTIONAL proximity
    reconnection step (anchor-less island -> nearest anchored island,
    single hop, never anchor-less-to-anchor-less) run BEFORE the final
    kill decision, and killed islands split into REVIEW_KILLED (suspect)
    vs ARTIFACT (not suspect) instead of one undifferentiated kill bucket.
    See module docstring for why this replaced the simpler blanket
    pairwise-proximity union-find (chaining)."""
    gap_pt = gap_ft / feet_per_pt if feet_per_pt else 0.0
    islands = cluster_by_touching(rooms_all)
    anchor_pts = [Point(x, y) for x, y in anchor_points]

    island_has_anchor = [_island_has_anchor(grp, rooms_all, anchor_pts) for grp in islands]
    anchored_islands = [grp for grp, has in zip(islands, island_has_anchor) if has]
    unanchored_islands = [grp for grp, has in zip(islands, island_has_anchor) if not has]

    # cache each ANCHORED island's own (original, never-grown) union geometry
    # -- this is what a candidate reconnects to; using the original geometry
    # (not a running/growing one) is what prevents transitive chaining.
    anchored_polys = [unary_union([rooms_all[i] for i in grp]) for grp in anchored_islands]

    reconnected_pairs = []   # (unanchored_grp, anchored_island_index)
    still_unanchored = []
    reconnect_diag = []
    for u_grp in unanchored_islands:
        u_poly = unary_union([rooms_all[i] for i in u_grp])
        within = [ai for ai, a_poly in enumerate(anchored_polys)
                  if u_poly.distance(a_poly) <= gap_pt]
        if len(within) == 1:
            reconnected_pairs.append((u_grp, within[0]))
            reconnect_diag.append(dict(idxs=u_grp, reconnected_to_anchored_island=within[0],
                                        sf=round(sum(rooms_all[i].area * feet_per_pt ** 2 for i in u_grp), 1)))
        else:
            still_unanchored.append(u_grp)
            if len(within) > 1:
                reconnect_diag.append(dict(idxs=u_grp, ambiguous_anchored_islands=within,
                                            sf=round(sum(rooms_all[i].area * feet_per_pt ** 2 for i in u_grp), 1)))

    kept_idx = sorted(i for grp in anchored_islands for i in grp)
    kept_idx += sorted(i for grp, _ in reconnected_pairs for i in grp)
    kept_idx = sorted(set(kept_idx))

    # principal drawing region: convex hull of every kept (anchored OR
    # reconnected) polygon, buffered outward a bit (same as v3)
    principal_region = None
    if kept_idx:
        hull = unary_union([rooms_all[i] for i in kept_idx]).convex_hull
        buf_pt = 0.10 * math.sqrt(hull.area) if hull.area > 0 else 0
        principal_region = hull.buffer(buf_pt)

    review_killed_idx, artifact_idx = [], []
    false_positive_suspects = []
    killed_idx = sorted(i for grp in still_unanchored for i in grp)
    for grp in still_unanchored:
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

    # clusters, for reporting/overlay purposes: anchored islands (unchanged),
    # reconnected islands (now folded into their target's group for the
    # cluster count), and still-unanchored islands
    clusters = list(anchored_islands) + [grp for grp, _ in reconnected_pairs] + list(still_unanchored)
    cluster_has_anchor = ([True] * len(anchored_islands) + [True] * len(reconnected_pairs) +
                           [False] * len(still_unanchored))

    return dict(kept_idx=kept_idx, killed_idx=killed_idx, clusters=clusters,
                cluster_has_anchor=cluster_has_anchor,
                principal_region=principal_region,
                false_positive_suspects=false_positive_suspects,
                review_killed_idx=review_killed_idx, artifact_idx=artifact_idx,
                reconnected_diag=reconnect_diag, gap_ft=gap_ft,
                n_islands_total=len(islands), n_anchored_islands=len(anchored_islands),
                n_reconnected_islands=len(reconnected_pairs),
                n_still_unanchored_islands=len(still_unanchored))


def run_geometry_engine_v4(extracted, feet_per_pt, anchor_points,
                            min_sqft=15, max_sqft=5000,
                            enable_anchor_filter=True, gap_ft=PROXIMITY_GAP_FT):
    """v2 engine, then the DIRECTIONAL PROXIMITY-RECONNECTING anchor-cluster
    membership filter (probe29's fix on top of probe28's v3). `anchor_points`
    must be computed by the caller BEFORE this call (plain PDF text lookup,
    independent of geometry) -- see probe29_regrade.py.

    Kept `rooms_all` = polygons in an anchored island, OR in an unanchored
    island that reconnected (single hop, unambiguous) to exactly one
    anchored island within `gap_ft`. Anything else is split into
    REVIEW_KILLED (flagged false_positive_suspect, excluded from sums but
    surfaced) or ARTIFACT (discarded silently, as v3)."""
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
    diag["anchor_cluster_n_islands_total"] = ac["n_islands_total"]
    diag["anchor_cluster_n_anchored_islands"] = ac["n_anchored_islands"]
    diag["anchor_cluster_n_reconnected_islands"] = ac["n_reconnected_islands"]
    diag["anchor_cluster_n_still_unanchored_islands"] = ac["n_still_unanchored_islands"]
    diag["anchor_cluster_reconnected_diag"] = ac["reconnected_diag"]
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
