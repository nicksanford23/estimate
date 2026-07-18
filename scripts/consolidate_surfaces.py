#!/usr/bin/env python3
"""S5.2 SURFACE CONSOLIDATION — 24-06748-RNVS.

Per FULL_PROCESS_LOCKED.md S5.2 + T-LOOP canonical unit: collapse room
IDENTITIES into physical_surface_regions before any measurement. Open-plan
duplication -> ONE surface with identity memberships; stairs/elevators ->
specialty/shaft (never room rectangles); everything else 1:1.

Two denominators recorded (data strategy §5): identity count and surface count.

Writes data/sam_smoke/24-06748-RNVS/surfaces.json
Usage: python scripts/consolidate_surfaces.py
"""
import json
import os

from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
PT_PER_FT = 18.0

STAIRS = {"105", "201", "301", "401"}
ELEVATORS = {"106", "202", "302", "402"}
OPEN_MERGE = ["305", "306", "307"]          # KITCHEN/DINING/LIVING one open field
DECK_MERGE = ["404", "405"]                 # COVERED + OUTDOOR one deck field


def load():
    tp = json.load(open(os.path.join(ROOT, "data", "sam_smoke", PERMIT,
                                     "bundle_g1b", "tasks.json")))
    tl = tp["tasks"] if isinstance(tp, dict) else tp
    tasks = {t["code"]: t for t in tl}
    ed = json.load(open(os.path.join(ROOT, "data", "sam_smoke", PERMIT,
                                     "results", "proposals_for_editor.json")))
    rep = json.load(open(os.path.join(ROOT, "data", "sam_smoke", PERMIT,
                                      "inspection", "repaired_proposals.json")))
    poly = {}
    for v in ed.values():
        poly[v["code"]] = v["polygon_pdf"]
    for v in rep.values():                  # repaired overrides
        poly[v["code"]] = v["polygon_pdf"]
    return tasks, poly


def area_sf(p):
    return round(Polygon(p).area / PT_PER_FT ** 2, 1)


def union_geom(codes, poly):
    polys = [Polygon(poly[c]) for c in codes if c in poly]
    u = unary_union(polys)
    if u.geom_type == "Polygon":
        ring = [[round(x, 2), round(y, 2)] for x, y in u.exterior.coords[:-1]]
        pieces = 1
    else:  # MultiPolygon: disjoint pieces, keep the convex hull as the merged extent
        ring = [[round(x, 2), round(y, 2)] for x, y in u.convex_hull.exterior.coords[:-1]]
        pieces = len(u.geoms)
    return ring, round(u.area / PT_PER_FT ** 2, 1), pieces


def main():
    tasks, poly = load()
    codes = list(tasks.keys())
    surfaces = []
    consumed = set()

    def rec(sid, kind, members, status, geom, gsource, note):
        names = [tasks[c].get("space_name") for c in members]
        pis = sorted({tasks[c]["page_index"] for c in members})
        sheets = sorted({tasks[c].get("sheet_number") for c in members})
        return {
            "surface_id": sid, "surface_kind": kind,
            "identity_memberships": members, "identity_names": names,
            "identity_count": len(members),
            "page_index": pis[0] if len(pis) == 1 else pis,
            "sheet": sheets[0] if len(sheets) == 1 else sheets,
            "status": status, "founder_disposition": "pending",
            "geometry_pdf": geom, "geometry_source": gsource,
            "area_sf_diagnostic": (area_sf(geom) if geom else None),
            "note": note,
        }

    # 1) open-plan merge 305/306/307
    g, a, pieces = union_geom(OPEN_MERGE, poly)
    surfaces.append(rec(
        "S-L3-GREATROOM", "open_plan_merge", OPEN_MERGE, "wrong_surface_model",
        g, "union(draft 305,306,307)",
        ("KITCHEN/DINING/LIVING are ONE continuous open field with no drawn wall "
         "between them (R5 open_split unresolved). The three draft rectangles are "
         "clipped, overlapping stand-ins. NEEDS STRUCTURAL REDRAW on the full-floor "
         f"context, not measurement. union area {a} sf (diagnostic; {pieces} draft "
         "piece(s)).")))
    consumed.update(OPEN_MERGE)

    # 2) deck merge 404/405
    g, a, pieces = union_geom(DECK_MERGE, poly)
    surfaces.append(rec(
        "S-L4-DECK", "deck_merge", DECK_MERGE, "wrong_surface_model",
        g, "union(draft 404,405)",
        ("COVERED DECK + OUTDOOR DECK are ONE continuous exterior deck field; the "
         "covered/outdoor split is scheduled-only with no drawn division line "
         "(invented split, 49.7 sf overlap in the drafts). NEEDS STRUCTURAL REDRAW "
         "with full-floor context + reviewer-established exterior edges, not "
         f"measurement. union area {a} sf (diagnostic; {pieces} draft piece(s)).")))
    consumed.update(DECK_MERGE)

    # 3) stairs -> specialty
    for c in [x for x in codes if x in STAIRS]:
        surfaces.append(rec(
            f"S-STAIR-{c}", "specialty_stair", [c], "needs_founder",
            None, "roster_identity",
            ("Stair: measured by specialty stair rules (tread/riser/landing run), "
             "NEVER as a room-floor rectangle. Founder judgment required. Draft "
             "polygon intentionally dropped as geometry.")))
        consumed.add(c)

    # 4) elevators -> shaft
    for c in [x for x in codes if x in ELEVATORS]:
        surfaces.append(rec(
            f"S-SHAFT-{c}", "shaft", [c], "needs_founder",
            None, "roster_identity",
            ("Elevator shaft: flooring-scope question (cab/pit typically out of "
             "flooring scope). Founder judgment required. Not a room-floor "
             "rectangle.")))
        consumed.add(c)

    # 5) everything else 1:1
    for c in codes:
        if c in consumed:
            continue
        p = poly.get(c)
        if p is None:
            surfaces.append(rec(
                f"S-{c}", "room", [c], "unresolved", None, "roster_identity_no_proposal",
                "No outline proposal produced for this identity (no polygon). "
                "Explicit unresolved state; carried in the identity denominator."))
        else:
            surfaces.append(rec(
                f"S-{c}", "room", [c], "ordinary_ready",
                [[round(x, 2), round(y, 2)] for x, y in p],
                "draft_proposal(1:1)",
                "1:1 room identity -> physical surface. Ready for reference-confirmed "
                "measurement (S5.5)."))

    ordinary = [s for s in surfaces if s["surface_kind"] == "room"
                and s["status"] == "ordinary_ready"]
    out = {
        "permit": PERMIT,
        "gate": "S5.2 surface-model consolidation",
        "canonical_unit": "physical_surface_region",
        "denominators": {
            "identity_count": sum(s["identity_count"] for s in surfaces),
            "surface_count": len(surfaces),
        },
        "surface_kind_counts": {
            k: sum(1 for s in surfaces if s["surface_kind"] == k)
            for k in sorted({s["surface_kind"] for s in surfaces})
        },
        "status_counts": {
            k: sum(1 for s in surfaces if s["status"] == k)
            for k in sorted({s["status"] for s in surfaces})
        },
        "ordinary_measurable_surface_ids": [s["surface_id"] for s in ordinary],
        "surfaces": surfaces,
    }
    p = os.path.join(ROOT, "data", "sam_smoke", PERMIT, "surfaces.json")
    json.dump(out, open(p, "w"), indent=1)
    print("identities:", out["denominators"]["identity_count"],
          "surfaces:", out["denominators"]["surface_count"])
    print("kinds:", out["surface_kind_counts"])
    print("status:", out["status_counts"])
    print("ordinary measurable:", len(ordinary))
    print("wrote", p)


if __name__ == "__main__":
    main()
