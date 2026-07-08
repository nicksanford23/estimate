#!/usr/bin/env python3
"""Stage-0 FIT CHECK: for a permit, grade each architectural floor-plan sheet
on the 5 questions that decide whether automatic SF is even feasible:
  vector?  scale?  dimensions?  rooms-close?  footprint-vs-permit?
Prints a scorecard + a project verdict. Reuses probe2_sf geometry.
Usage: python3 sf_fit.py PERMIT_NUM
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, SCALE_RE, r2_client, download_pdf, extract_drawings, wall_candidates,
    suppress_hatches, snap_and_close, polygonize_rooms, extract_dim_words,
)

PERMIT = sys.argv[1] if len(sys.argv) > 1 else "14-11290-NEWC"


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            e[k] = v
    return e


def neon():
    import psycopg2
    import psycopg2.extras
    con = psycopg2.connect(env()["NEON_DATABASE_URL"])
    return con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def scale_of(pdf, page):
    doc = fitz.open(pdf)
    txt = doc[page].get_text()
    doc.close()
    ms = SCALE_RE.findall(txt)
    if not ms:
        return None, None
    num, den = int(ms[0][0]), int(ms[0][1])
    return (den / num) / 72.0, f'{num}/{den}" = 1\'-0"'


def assess(pdf, page, permit_sqft):
    ex = extract_drawings(pdf, page)
    n_seg = len(ex["line_segments"])
    is_vector = n_seg > 500
    fpp, scale_text = scale_of(pdf, page)
    dims = extract_dim_words(pdf, page)
    n_dims = len(dims)

    rooms = 0
    footprint = None
    if is_vector and fpp:
        walls, dom, thick = wall_candidates(ex)
        walls_clean, _ = suppress_hatches(walls, ex["pw"])
        lines, _ = snap_and_close(walls_clean, ex["arcs"], ex["pw"], feet_per_pt=fpp)
        rms, _ = polygonize_rooms(lines, ex["pw"], ex["ph"], 15, 20000, fpp)
        rooms = len(rms)
        if rms:
            footprint = max(r.area for r in rms) * (fpp ** 2)

    # verdict per sheet
    if not is_vector:
        verdict = "🔴 scanned / no vectors"
    elif not fpp:
        verdict = "🔴 no readable scale"
    elif rooms == 0:
        verdict = "🔴 nothing closed"
    else:
        # crude clean-vs-blob proxy: many small rooms good; 1-3 giant = merged
        verdict = "🟡 vector+scale OK, rooms likely merge (needs wall-classifier)"
    return dict(n_seg=n_seg, is_vector=is_vector, scale=scale_text, n_dims=n_dims,
                rooms=rooms, footprint=footprint, permit_sqft=permit_sqft, verdict=verdict)


def main():
    cur = neon()
    cur.execute("SELECT sqft, description FROM estimate.permits WHERE permit_num=%s", (PERMIT,))
    prow = cur.fetchone() or {}
    permit_sqft = prow.get("sqft")
    # architectural floor-plan sheets (A-*, overall) that are downloaded
    cur.execute("""SELECT doc_id::text did, name FROM estimate.documents
        WHERE permit_num=%s AND (name ILIKE 'A-%%floor plan%%' OR name ILIKE '%%overall plan%%'
             OR name ILIKE '%%branch floor plan%%' OR name ILIKE '%%retail floor plan%%')
        ORDER BY name""", (PERMIT,))
    cands = cur.fetchall()

    print(f"\n{'='*72}\nFIT CHECK — {PERMIT}")
    print(f"{prow.get('description','')[:66]}")
    print(f"permit recorded sq ft: {permit_sqft or 'n/a'}")
    print(f"candidate architectural floor-plan sheets: {len(cands)}\n{'='*72}")

    s3 = r2_client()
    for c in cands:
        pdf = download_pdf(s3, c["did"])
        try:
            r = assess(pdf, 0, permit_sqft)
        finally:
            try:
                os.remove(pdf)
            except OSError:
                pass
        fp = f"{r['footprint']:.0f}" if r['footprint'] else "—"
        print(f"\n• {c['name'][:52]}")
        print(f"    vector:      {'YES' if r['is_vector'] else 'NO'}  ({r['n_seg']:,} line segments)")
        print(f"    scale:       {r['scale'] or 'NOT FOUND'}")
        print(f"    dimensions:  {r['n_dims']} printed dimension strings")
        print(f"    geometry:    {r['rooms']} closed regions · footprint ~{fp} sqft"
              + (f" (permit says {permit_sqft})" if permit_sqft else ""))
        print(f"    → {r['verdict']}")
    print(f"\n{'='*72}")


if __name__ == "__main__":
    main()
