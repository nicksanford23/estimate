#!/usr/bin/env python3
"""export_demo_json.py -- turn a takeoff.py run into the v0.5 Review Screen
demo data (web/public/demo/<permit>.json + <permit>.png).

Why this exists: takeoff.py's run.json records room area_sf / product_action
/ material but NEVER persists the polygon vertex coordinates themselves --
they live only as in-memory shapely Polygons, baked into the overlay JPG as
pixels. The web review screen needs real clickable <polygon> shapes, so this
script re-derives them by calling takeoff.py's OWN functions (imported, not
copy-pasted: resolve_scale, route_and_extract, anchor_rooms, build_rooms,
load_truth) for the exact doc_id/page_index each permit's run.json already
used, then renders a plain (no-overlay) page PNG at a chosen zoom and
expresses every polygon in that same pixel space (pixel = page_point * zoom,
a fitz identity) -- so alignment is exact by construction, not by eyeball
fudging. `feet_per_pixel = feet_per_pt / zoom` follows from the same
identity and is recorded so the web app never re-derives scale.

Cross-checked against the existing run.json summary counts (n_auto/n_review/
n_open/total_sf) before writing output -- if the re-derivation doesn't match
the on-disk run.json byte-for-byte in the numbers that matter, something
about engine/inputs drifted and the script aborts rather than ship silently
wrong geometry.

Usage: python3 scripts/export_demo_json.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402

import takeoff as T  # noqa: E402

ROOT = T.ROOT
OUT_DIR = os.path.join(ROOT, "web", "public", "demo")
os.makedirs(OUT_DIR, exist_ok=True)

# Target render resolution: ~200dpi (fitz zoom = dpi/72), capped so giant
# sheets don't blow up file size absurdly.
TARGET_ZOOM = 200 / 72.0
MAX_PIXEL_WIDTH = 2600

STATUS_MAP = {
    "auto_quantity": "accepted",
    "geometry_review": "review",
    "open_zone_split": "open",
    "redraw": "draw_needed",
    "vision_correct_or_redraw": "draw_needed",
}

# Hand-curated material + name context already vetted for the takeoff guide
# pages (web/lib/guides.ts) -- reused here as the material JOIN for the two
# permits whose run.json leaves material=null (finish extraction not yet
# automated for these; the guide's per-room table was hand-read off the real
# finish schedule, so it's a legitimate source, not a fabrication).
sys.path.insert(0, os.path.join(ROOT, "web"))


def load_guides_rooms():
    """Parse web/lib/guides.ts's room tables into {permit: {room_num_str: {...}}}
    without a TS toolchain -- it's a static object literal; regex-extract the
    fields we need (num, name, material, code, action, sfNote)."""
    import re
    path = os.path.join(ROOT, "web", "lib", "guides.ts")
    with open(path) as f:
        src = f.read()
    out = {}
    cur_permit = None
    for m in re.finditer(
        r'"(?P<permit>[\w-]+)":\s*\{\s*permit:\s*"[\w-]+",\s*docId:\s*\d+,\s*rooms:\s*\[(?P<body>.*?)\],\n\s*planSet',
        src, re.S):
        permit = m.group("permit")
        body = m.group("body")
        rooms = {}
        for rm in re.finditer(
            r'\{\s*num:\s*(?P<num>\d+),\s*name:\s*"(?P<name>[^"]*)",\s*material:\s*"(?P<material>[^"]*)",'
            r'\s*code:\s*"(?P<code>[^"]*)"(?:,\s*action:\s*"(?P<action>[^"]*)")?'
            r'(?:,\s*sfNote:\s*"(?P<sfnote>[^"]*)")?\s*\}',
            body):
            rooms[rm.group("num")] = dict(
                name=rm.group("name"), material=rm.group("material"),
                code=rm.group("code"), action=rm.group("action"),
                sfnote=rm.group("sfnote"))
        out[permit] = rooms
    return out


GUIDES_ROOMS = load_guides_rooms()


def schedule_evidence_line(row):
    parts = [row.get("floor_finish") or row.get("floor_material_bucket")]
    if row.get("base"):
        parts.append(f"base {row['base']}")
    return f"Finish schedule: {row.get('name','')} -- " + ", ".join(p for p in parts if p)


def export_permit(permit, doc_id, page_index, project_name, address=None,
                   use_truth_gap_rooms=False):
    run_path = os.path.join(ROOT, "data", "takeoff", permit, "run.json")
    with open(run_path) as f:
        existing = json.load(f)
    existing_summary = existing["summary"]

    run_dir = os.path.join(ROOT, "data", "takeoff", permit)
    os.makedirs(run_dir, exist_ok=True)
    truth = T.load_truth(permit)

    s3 = T.r2_client()
    pdf = T.download_pdf(s3, doc_id)
    try:
        fpp, scale_text, scale_source, crop_path = T.resolve_scale(pdf, doc_id, page_index, run_dir)
        assert fpp is not None, f"{permit}: scale unresolved, cannot proceed"

        polys, meta, pw, ph = T.route_and_extract(pdf, page_index, fpp, engine="v4", truth=truth)

        doc = fitz.open(pdf)
        page = doc[page_index]
        poly_rooms, poly_artifact, anchors, anchor_flags, montage_path = T.anchor_rooms(
            page, polys, pdf, page_index, doc_id, run_dir, truth)
        rooms, open_groups, n_artifact = T.build_rooms(
            polys, poly_rooms, poly_artifact, fpp, truth, doc_id, page_index)

        # ---- cross-check vs the already-shipped run.json for this permit ----
        n_auto = sum(1 for r in rooms if r["product_action"] == "auto_quantity")
        n_review = sum(1 for r in rooms if r["product_action"] == "geometry_review")
        n_open = sum(1 for r in rooms if r["product_action"] == "open_zone_split")
        total_sf = round(sum(r["area_sf"] for r in rooms
                              if r["product_action"] == "auto_quantity" and r["area_sf"]), 1)
        mismatch = []
        if n_auto != existing_summary["n_auto"]:
            mismatch.append(f"n_auto {n_auto} != {existing_summary['n_auto']}")
        if n_review != existing_summary["n_review"]:
            mismatch.append(f"n_review {n_review} != {existing_summary['n_review']}")
        if n_open != existing_summary["n_open"]:
            mismatch.append(f"n_open {n_open} != {existing_summary['n_open']}")
        if abs(total_sf - existing_summary["total_sf"]) > 0.5:
            mismatch.append(f"total_sf {total_sf} != {existing_summary['total_sf']}")
        if mismatch:
            raise SystemExit(f"{permit}: re-derivation MISMATCH vs run.json: {'; '.join(mismatch)}")
        print(f"{permit}: re-derivation matches run.json "
              f"(auto={n_auto} review={n_review} open={n_open} total_sf={total_sf})")

        # ---- render the plain page PNG at our own (higher-res) zoom ----
        zoom = min(TARGET_ZOOM, MAX_PIXEL_WIDTH / pw)
        pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img_name = f"{permit}.png"
        pm.save(os.path.join(OUT_DIR, img_name))
        feet_per_pixel = fpp / zoom
        doc.close()

        # ---- build product-shaped rooms ----
        guide_rooms = GUIDES_ROOMS.get(permit, {})
        open_group_by_poly = {g["poly_index"]: g for g in open_groups}
        out_rooms = []
        for i, poly in enumerate(polys):
            r = next((rr for rr in rooms if rr["poly_index"] == i), None)
            if r is None:
                continue  # artifact polygon (notes/legend region)
            status = STATUS_MAP[r["product_action"]]
            room_num = r.get("room")
            gr = guide_rooms.get(str(room_num)) if room_num else None
            truth_row = truth["by_room"].get(str(room_num).upper()) if (truth and room_num) else None

            name = (r.get("name") or (gr["name"] if gr else None) or
                    (truth_row.get("name") if truth_row else None))
            if not name:
                og = open_group_by_poly.get(i)
                if og:
                    name = f"Open area (rooms {', '.join(og['members'])})"
                elif room_num:
                    name = f"Room {room_num}"
                else:
                    name = "Unlabeled area"

            material = (gr["material"] if gr and gr["material"] else None) or \
                       (truth_row.get("floor_finish") if truth_row else None) or \
                       r.get("material")
            if material in ("mixed/TBD", None):
                material = None

            evidence = {}
            if truth_row:
                evidence["schedule_row"] = schedule_evidence_line(truth_row)
            elif gr and gr["code"]:
                evidence["schedule_row"] = f"Finish schedule: {gr['material']} ({gr['code']})"
            if gr and gr.get("sfnote") and ("vs" in gr["sfnote"] or "review" in (gr.get("action") or "")):
                evidence["why_flagged"] = f"Dimension cross-check: {gr['sfnote']}."
            elif status == "review":
                evidence["why_flagged"] = ("Engine closed a room-sized shape here but could not "
                                            "confidently match a room number to it.")
            elif status == "open":
                members = open_group_by_poly.get(i, {}).get("members", [])
                evidence["why_flagged"] = (f"Open floor plate covering rooms {', '.join(members)} -- "
                                            "no drawn boundary between them yet.")

            pts = list(poly.exterior.coords)[:-1]  # drop shapely's repeated closing vertex
            polygon_px = [[round(x * zoom, 1), round(y * zoom, 1)] for x, y in pts]

            out_rooms.append(dict(
                id=f"{permit}-poly{i}",
                name=name,
                polygon=polygon_px,
                sf=r["area_sf"],
                status=status,
                material=material,
                evidence=evidence,
            ))

        # ---- rooms the geometry engine never produced a polygon for at all,
        #      known only from the finish schedule (24-06748's honest gap) ----
        if use_truth_gap_rooms and truth:
            matched_room_nums = {str(r.get("room")).upper() for r in rooms if r.get("room")}
            for room_num, row in truth["by_room"].items():
                if room_num in matched_room_nums:
                    continue
                sf = row.get("area_sf")
                out_rooms.append(dict(
                    id=f"{permit}-schedule-{room_num}",
                    name=f"{row.get('name', room_num)} ({room_num})",
                    polygon=None,
                    sf=sf,
                    status="draw_needed",
                    material=row.get("floor_finish"),
                    evidence=dict(
                        schedule_row=schedule_evidence_line(row),
                        why_flagged=("No plan geometry on this permit's takeoff pass covers this "
                                      "room -- area is from the finish schedule only, not measured. "
                                      "Needs a boundary drawn."),
                    ),
                    sf_source="schedule",
                ))

        demo = dict(
            project=dict(id=permit, name=project_name, address=address),
            pages=[dict(
                id=f"{doc_id}_p{page_index}",
                image=f"/demo/{img_name}",
                feet_per_pixel=round(feet_per_pixel, 5),
                rooms=out_rooms,
            )],
        )
        out_path = os.path.join(OUT_DIR, f"{permit}.json")
        with open(out_path, "w") as f:
            json.dump(demo, f, indent=2)
        print(f"  -> {os.path.relpath(out_path, ROOT)}  ({len(out_rooms)} rooms, "
              f"image {pm.width}x{pm.height}px, feet_per_pixel={feet_per_pixel:.5f})")
    finally:
        os.remove(pdf)


if __name__ == "__main__":
    export_permit("14-11290-NEWC", 1494156, 3, "First Bank Branch — 14-11290-NEWC")
    export_permit("26-10321-RNVN", 9058456, 18, "Office Renovation, Floor 9 — 26-10321-RNVN")
    export_permit("24-06748-RNVS", 7372349, 6, "Residential Renovation, 2nd Floor — 24-06748-RNVS",
                  use_truth_gap_rooms=True)
