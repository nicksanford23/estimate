#!/usr/bin/env python3
"""Import offline takeoff/project runs into v2 so the
Geometry Review tab actually renders them.

This is the missing standing step: takeoff.py produces run.json on disk, and
this carries it into v2 (region + geometry_run + polygon_prediction) which the
web Geometry tab reads. Run it after the pipeline for any building.

  scripts/import_takeoff_to_v2.py --permit 24-06748-RNVS
  scripts/import_takeoff_to_v2.py --permit 24-06748-RNVS --project-run-name viewport_v4
  scripts/import_takeoff_to_v2.py --permit 24-06748-RNVS --run-path data/project_runs/viewport_v4/24-06748-RNVS/run.json
  scripts/import_takeoff_to_v2.py --all        # every data/takeoff/*/run.json

Idempotent by source run path. Multiple engines/runs may coexist on the same
viewport with increasing run_no. Machine predictions only — never human truth,
decisions, source links, or eligibility approvals.
"""
import os, sys, json, glob, argparse
import psycopg2

ROOT = "/workspaces/estimate"


def get_conn():
    env = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    conn = psycopg2.connect(env["NEON_DATABASE_URL"])
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SET search_path TO v2, public")
    cur.close()
    return conn


def import_run(conn, permit, run_path):
    run = json.load(open(run_path))
    generated_at = run.get("generated_at")
    source_run_path = os.path.relpath(os.path.abspath(run_path), ROOT)
    imported = skipped = 0
    for pg in run.get("pages", []):
        onestop = str(pg.get("doc_id"))
        pidx = pg.get("page_index")
        cur = conn.cursor()
        cur.execute(
            """SELECT pg.id FROM v2.page pg JOIN v2.document d ON d.id=pg.document_id
               JOIN v2.permit p ON p.id=d.permit_id
               WHERE p.permit_num=%s AND d.onestop_doc_id::text=%s AND pg.pdf_page_index=%s""",
            (permit, onestop, pidx),
        )
        row = cur.fetchone()
        if not row:
            print(f"  [skip] no v2.page for {permit} doc {onestop} p{pidx}")
            cur.close()
            continue
        page_id = row[0]
        cur.execute(
            """SELECT gr.id FROM v2.geometry_run gr
               JOIN v2.region r ON r.id=gr.region_id
               WHERE r.page_id=%s AND gr.manifest_json->>'source_run_path'=%s""",
            (page_id, source_run_path),
        )
        if cur.fetchone():
            print(f"  [skip] source run already imported for {permit} p{pidx} (page {page_id})")
            skipped += 1
            cur.close()
            continue

        rooms = pg.get("rooms", [])
        n_auto = sum(1 for r in rooms if r.get("product_action") == "auto_quantity")
        n_review = sum(1 for r in rooms if r.get("product_action") == "geometry_review")
        n_open = len(pg.get("open_groups", []) or [])
        total_sf = round(sum(float(r.get("area_sf") or 0) for r in rooms), 1)
        manifest = {
            "legacy": False,
            "permit": permit,
            "summary": {
                "n_auto": n_auto, "n_review": n_review, "n_open": n_open,
                "n_artifact": pg.get("n_artifact", 0), "total_sf": total_sf,
                "flags": pg.get("flags", []),
            },
            "scale_text": pg.get("scale_text"),
            "sheet_title": pg.get("sheet_title"),
            "generated_at": generated_at,
            "overlay_path": pg.get("overlay_path"),
            "routing_meta": pg.get("routing_meta", {}),
            "geometry_path": pg.get("geometry_path"),
            "onestop_doc_id": onestop,
            "pdf_page_index": pidx,
            "rules_engine": run.get("rules_engine"),
            "source_run_path": source_run_path,
        }
        cur.execute(
            "SELECT id FROM v2.region WHERE page_id=%s AND kind='plan_viewport' ORDER BY id LIMIT 1",
            (page_id,),
        )
        region = cur.fetchone()
        if region:
            region_id = region[0]
        else:
            cur.execute("INSERT INTO v2.region (page_id, kind) VALUES (%s,'plan_viewport') RETURNING id", (page_id,))
            region_id = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(MAX(run_no),0)+1 FROM v2.geometry_run WHERE region_id=%s", (region_id,))
        run_no = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO v2.geometry_run (region_id, run_no, status, manifest_json) VALUES (%s,%s,'active',%s::jsonb) RETURNING id",
            (region_id, run_no, json.dumps(manifest)),
        )
        run_id = cur.fetchone()[0]
        for r in rooms:
            geom = {
                "poly_index": r.get("poly_index"),
                "bbox_pdf": r.get("bbox_pdf"),
                "centroid_pdf": r.get("centroid_pdf"),
                "note": "full vector ring is not retained; overlay image is the canvas",
            }
            flags = {"flags": r.get("flags", []), "material": r.get("material"), "confidence": r.get("confidence")}
            cur.execute(
                """INSERT INTO v2.polygon_prediction (run_id, geom_json, label_match, area_sf, product_action, flags)
                   VALUES (%s,%s::jsonb,%s,%s,%s,%s::jsonb)""",
                (run_id, json.dumps(geom), r.get("room"), r.get("area_sf"), r.get("product_action"), json.dumps(flags)),
            )
        conn.commit()
        print(f"  [import] {permit} p{pidx}: region {region_id}, run {run_id}, {len(rooms)} polygons ({n_auto} auto / {n_review} review)")
        imported += 1
        cur.close()
    return imported, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--permit")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--project-run-name")
    ap.add_argument("--run-path")
    a = ap.parse_args()

    if a.all:
        paths = sorted(glob.glob(os.path.join(ROOT, "data/takeoff/*/run.json")))
    elif a.permit and a.run_path:
        paths = [a.run_path if os.path.isabs(a.run_path) else os.path.join(ROOT, a.run_path)]
    elif a.permit and a.project_run_name:
        paths = [os.path.join(ROOT, f"data/project_runs/{a.project_run_name}/{a.permit}/run.json")]
    elif a.permit:
        paths = [os.path.join(ROOT, f"data/takeoff/{a.permit}/run.json")]
    else:
        print("usage: --permit <num> [--project-run-name NAME | --run-path PATH] | --all")
        sys.exit(1)

    conn = get_conn()
    ti = ts = 0
    for pth in paths:
        if not os.path.exists(pth):
            print(f"[missing] {pth}")
            continue
        permit = a.permit or os.path.basename(os.path.dirname(pth))
        print(f"== {permit} ==")
        i, s = import_run(conn, permit, pth)
        ti += i
        ts += s
    conn.close()
    print(f"\nDONE: imported {ti} page-runs, skipped {ts} already-present.")


if __name__ == "__main__":
    main()
