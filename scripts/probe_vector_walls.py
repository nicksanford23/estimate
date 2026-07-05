#!/usr/bin/env python3
"""Feasibility Probe 1 (Stage 4, Route A) — do wall lines exist as clean
vector segments in original PDFs, or are plan sets flattened to images?

Picks 6 floor_plan pages (has_vector_text=1) from 6 different permits,
mixed eras/project types. Downloads the ORIGINAL PDFs from R2 (never the
rendered PNG — geometry must come from the PDF), extracts drawings with
fitz page.get_drawings(), classifies "wall candidate" segments/rects,
overlays them in red on a render of the original page, and checks
pagetext for a scale notation. Deletes PDFs when done.

Outputs -> data/probe1/:
  overlay_<permit>_<doc>_<page>.png   red-annotated render
  results.json                        per-page metrics
"""
import io
import json
import math
import os
import re

import boto3
import fitz  # PyMuPDF
import psycopg2
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {}
with open(os.path.join(ROOT, ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            ENV[k] = v

OUT_DIR = os.path.join(ROOT, "data", "probe1")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)

# Curated for era + project-type spread (NEWC = new construction,
# RNVS/RNVN = renovation), 2013-2025, 6 distinct permits.
CANDIDATE_PERMITS = [
    "13-38849-NEWC",  # 2013 new construction
    "17-35590-RNVS",  # 2017 renovation
    "19-24353-RNVS",  # 2019 renovation
    "22-37867-NEWC",  # 2022 new construction
    "24-17262-NEWC",  # 2024 new construction
    "25-27326-RNVS",  # 2025 renovation
]

SCALE_RE = re.compile(
    r"(\d+/\d+\"?\s*=\s*1'-?0\"?"          # 1/8" = 1'-0"
    r"|\d+/\d+\"?\s*=\s*1'"                 # 1/4"=1'
    r"|\bscale\s*[:=]?\s*\d+/\d+"           # SCALE: 1/8
    r"|\b1\s*:\s*\d{2,4}\b"                 # 1:50, 1:100
    r"|3/32\"?\s*=\s*1'-?0\"?)",
    re.IGNORECASE,
)


def connect():
    conn = psycopg2.connect(ENV["NEON_DATABASE_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET search_path TO estimate, public")
    return conn, cur


def pick_pages(cur):
    """One floor_plan / has_vector_text=1 page per candidate permit, using
    the latest label per page. Picks a page roughly in the middle of that
    permit's floor_plan run (more likely a full plan, not a partial)."""
    cur.execute(
        """
        WITH latest AS (
            SELECT DISTINCT ON (page_id) page_id, category, created_at
            FROM page_label
            ORDER BY page_id, created_at DESC
        )
        SELECT d.permit_num, d.onestop_doc_id, p.page_index, p.image_path, p.id
        FROM latest l
        JOIN page p ON p.id = l.page_id
        JOIN document d ON d.id = p.document_id
        WHERE l.category = 'floor_plan' AND p.has_vector_text = 1
          AND d.permit_num = ANY(%s)
        ORDER BY d.permit_num, p.page_index
        """,
        (CANDIDATE_PERMITS,),
    )
    rows = cur.fetchall()
    by_permit = {}
    for permit, doc_id, page_index, image_path, page_id in rows:
        by_permit.setdefault(permit, []).append(
            (doc_id, page_index, image_path, page_id)
        )
    picks = []
    for permit in CANDIDATE_PERMITS:
        opts = by_permit.get(permit, [])
        if not opts:
            continue
        opts.sort(key=lambda r: r[1])
        doc_id, page_index, image_path, page_id = opts[len(opts) // 2]
        picks.append(
            dict(
                permit=permit,
                doc_id=doc_id,
                page_index=page_index,
                image_path=image_path,
                page_id=page_id,
            )
        )
    return picks


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
    s3.download_file(ENV["R2_BUCKET"], f"docs/{doc_id}.pdf", dest)
    with open(dest, "rb") as f:
        head = f.read(5)
    assert head[:4] == b"%PDF", f"downloaded file for {doc_id} is not a PDF (magic={head!r})"
    return dest


def seg_len(p0, p1):
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def seg_angle_from_axis(p0, p1):
    """Smallest angle (deg) from horizontal or vertical, 0 = perfectly axis-aligned."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ang = math.degrees(math.atan2(abs(dy), abs(dx))) if (dx or dy) else 0.0
    return min(ang, abs(90 - ang))


def cluster_widths(widths, tol=0.15):
    """Greedy 1D clustering of stroke widths; returns [(center, count), ...] sorted by count desc."""
    clusters = []  # list of [sum, count]
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


def analyze_page(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    drawings = page.get_drawings()

    total_paths = len(drawings)
    line_segments = []  # (p0, p1, width)
    fill_rects = []  # (rect, width_frac, len_frac)
    all_widths = []

    for d in drawings:
        width = d.get("width") or 0.0
        is_fill = d.get("fill") is not None and d.get("type") in ("f", "fs")
        for item in d.get("items", []):
            kind = item[0]
            if kind == "l":  # line: (kind, p0, p1)
                p0, p1 = item[1], item[2]
                line_segments.append((p0, p1, width))
                if width > 0:
                    all_widths.append(width)
            elif kind == "re":  # rect: (kind, rect)
                r = item[1]
                rw, rh = r.width, r.height
                short, long = min(rw, rh), max(rw, rh)
                if is_fill and long > 0:
                    width_frac = short / pw
                    len_frac = long / max(pw, ph)
                    if width_frac < 0.005 and len_frac > 0.02:
                        fill_rects.append((r, width_frac, len_frac))
            elif kind == "c":  # bezier curve — not a wall
                pass

    n_segments = len(line_segments)
    width_clusters = cluster_widths(all_widths) if all_widths else []
    top5 = width_clusters[:5]
    thick_centers = {c for c, _ in top5}
    # "thickest" = top clusters, but skip the single most-populous cluster if
    # it's clearly the thin annotation/hatch weight (< 0.3pt) with a thicker
    # runner-up available.
    thick_set = set()
    if top5:
        max_w = max(c for c, _ in top5)
        thick_set = {c for c, _ in top5 if c >= max_w * 0.6}

    wall_candidates = 0
    for p0, p1, width in line_segments:
        length = seg_len(p0, p1)
        if length < 0.02 * pw:
            continue
        if seg_angle_from_axis(p0, p1) > 2.0:
            continue
        if width > 0:
            matched = any(abs(width - c) <= max(0.15, c * 0.25) for c in thick_set)
            if not matched:
                continue
        wall_candidates += 1

    doc.close()
    return dict(
        page_w=pw,
        page_h=ph,
        total_paths=total_paths,
        n_segments=n_segments,
        width_clusters_top5=top5,
        wall_candidates=wall_candidates,
        fill_rect_walls=len(fill_rects),
        wall_segments=[
            (p0, p1)
            for p0, p1, width in line_segments
            if seg_len(p0, p1) >= 0.02 * pw
            and seg_angle_from_axis(p0, p1) <= 2.0
            and (width == 0 or any(abs(width - c) <= max(0.15, c * 0.25) for c in thick_set))
        ],
        fill_rect_geoms=[r for r, _, _ in fill_rects],
    )


def render_overlay(pdf_path, page_index, analysis, out_path, target_w=1600):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    zoom = target_w / page.rect.width
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(img)
    for p0, p1 in analysis["wall_segments"]:
        draw.line([(p0[0] * zoom, p0[1] * zoom), (p1[0] * zoom, p1[1] * zoom)],
                   fill=(255, 0, 0), width=3)
    for r in analysis["fill_rect_geoms"]:
        draw.rectangle(
            [r.x0 * zoom, r.y0 * zoom, r.x1 * zoom, r.y1 * zoom],
            outline=(255, 0, 0), width=3,
        )
    img.save(out_path)
    doc.close()


def find_scale(doc_id, page_index):
    path = os.path.join(ROOT, "data", "pagetext", str(doc_id), f"page_{page_index:04d}.txt")
    if not os.path.exists(path):
        return False, None
    with open(path, errors="ignore") as f:
        text = f.read()
    m = SCALE_RE.search(text)
    return bool(m), (m.group(0) if m else None)


def verdict(analysis):
    tp = analysis["total_paths"]
    wc = analysis["wall_candidates"] + analysis["fill_rect_walls"]
    if tp < 20:
        return "FLATTENED"
    if wc >= 15:
        return "GOOD"
    if wc >= 4:
        return "MESSY"
    return "FLATTENED"


def main():
    conn, cur = connect()
    picks = pick_pages(cur)
    conn.close()
    print(f"Picked {len(picks)} pages:")
    for p in picks:
        print(f"  {p['permit']}  doc={p['doc_id']}  page_index={p['page_index']}")

    s3 = r2_client()
    results = []
    for p in picks:
        print(f"\n=== {p['permit']} (doc {p['doc_id']}, page {p['page_index']}) ===")
        pdf_path = download_pdf(s3, p["doc_id"])
        try:
            analysis = analyze_page(pdf_path, p["page_index"])
            scale_found, scale_text = find_scale(p["doc_id"], p["page_index"])
            v = verdict(analysis)
            overlay_name = f"overlay_{p['permit']}_{p['doc_id']}_p{p['page_index']}.png"
            overlay_path = os.path.join(OUT_DIR, overlay_name)
            render_overlay(pdf_path, p["page_index"], analysis, overlay_path)

            row = dict(
                permit=p["permit"],
                doc_id=p["doc_id"],
                page_index=p["page_index"],
                page_id=p["page_id"],
                total_paths=analysis["total_paths"],
                n_segments=analysis["n_segments"],
                width_clusters_top5=analysis["width_clusters_top5"],
                wall_candidates=analysis["wall_candidates"],
                fill_rect_walls=analysis["fill_rect_walls"],
                scale_found=scale_found,
                scale_text=scale_text,
                verdict=v,
                overlay_path=os.path.relpath(overlay_path, ROOT),
            )
            results.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "overlay_path"}, indent=2))
        finally:
            os.remove(pdf_path)  # never keep original PDFs on disk

    with open(os.path.join(OUT_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)

    print("\n\n=== SUMMARY ===")
    from collections import Counter
    counts = Counter(r["verdict"] for r in results)
    print(dict(counts))
    print(f"Results written to {os.path.join(OUT_DIR, 'results.json')}")


if __name__ == "__main__":
    main()
