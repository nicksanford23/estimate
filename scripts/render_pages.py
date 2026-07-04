#!/usr/bin/env python3
"""Render a diverse subset of downloaded plan PDFs into page PNGs + text.

Selection: from download_run.csv ok rows, join Neon for permit metadata,
keep the largest doc per permit (plan sets are big), bytes 0.5-60MB,
interleave permit codes, take TARGET_DOCS. Fetch each from R2, render at
long-edge ~1568px, save per-page vector text, insert document+page rows,
delete the fetched PDF. Idempotent: skips onestop_doc_ids already in DB.
"""
import csv
import os
import subprocess
import sys

import fitz
import psycopg2
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {}
with open(os.path.join(ROOT, ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            ENV[k] = v

BUCKET_URL = f"{ENV['R2_ENDPOINT']}/{ENV['R2_BUCKET']}"
AWS_USER = f"{ENV['R2_ACCESS_KEY_ID']}:{ENV['R2_SECRET_ACCESS_KEY']}"
TARGET_DOCS = int(sys.argv[1]) if len(sys.argv) > 1 else 220
SHARD = int(sys.argv[2]) if len(sys.argv) > 2 else 0
NSHARDS = int(sys.argv[3]) if len(sys.argv) > 3 else 1
MAX_PAGES_PER_DOC = 150
LONG_EDGE = 1568


def pick_docs():
    ok = {}
    with open(os.path.join(ROOT, "data", "download_run.csv")) as f:
        for row in csv.reader(f):
            if len(row) >= 4 and row[1] == "ok":
                ok[row[0]] = (int(row[2]), row[3])
    conn = psycopg2.connect(ENV["NEON_DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("SELECT d.doc_id, d.permit_num, p.code FROM documents d "
                "JOIN permits p USING (permit_num) WHERE d.doc_id = ANY(%s)",
                ([int(i) for i in ok], ))
    rows = cur.fetchall()
    conn.close()

    best = {}  # permit -> (bytes, doc_id, name, code)
    for doc_id, permit, code in rows:
        size, name = ok[str(doc_id)]
        if not (500_000 <= size <= 60_000_000):
            continue
        if permit not in best or size > best[permit][0]:
            best[permit] = (size, str(doc_id), name, permit, code)
    by_code = {}
    for v in best.values():
        by_code.setdefault(v[4], []).append(v)
    for docs in by_code.values():
        docs.sort(key=lambda x: x[0], reverse=True)
    picked, i = [], 0
    while len(picked) < TARGET_DOCS and any(by_code.values()):
        for code in list(by_code):
            if by_code[code]:
                picked.append(by_code[code].pop(0))
                if len(picked) >= TARGET_DOCS:
                    break
        i += 1
    return picked  # (bytes, doc_id, name, permit, code)


def fetch_r2(doc_id, dest):
    r = subprocess.run(["curl", "-s", "-m", "1800", "-o", dest, "-w", "%{http_code}",
                        "--aws-sigv4", "aws:amz:auto:s3", "--user", AWS_USER,
                        f"{BUCKET_URL}/docs/{doc_id}.pdf"],
                       capture_output=True, timeout=1860)
    return r.stdout.decode().strip() == "200" and os.path.getsize(dest) > 1024


def render_doc(db, size, doc_id, name, permit, code):
    pdf_path = os.path.join(ROOT, "data", "render_tmp", f"{doc_id}.pdf")
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    if not fetch_r2(doc_id, pdf_path):
        return "fetch_failed"
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        os.remove(pdf_path)
        return "open_failed"
    n = min(len(doc), MAX_PAGES_PER_DOC)
    img_dir = os.path.join(ROOT, "data", "pages", doc_id)
    txt_dir = os.path.join(ROOT, "data", "pagetext", doc_id)
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(txt_dir, exist_ok=True)

    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO document (permit_num, onestop_doc_id, "
                "filename, bytes, storage_path, status) VALUES (?,?,?,?,?,?)",
                (permit, int(doc_id), name, size, f"r2:docs/{doc_id}.pdf", "downloaded"))
    db.commit()
    cur.execute("SELECT id FROM document WHERE onestop_doc_id=?", (int(doc_id),))
    dbid = cur.fetchone()[0]

    for i in range(n):
        page = doc[i]
        rect = page.rect
        zoom = LONG_EDGE / max(rect.width, rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_path = os.path.join(img_dir, f"page_{i:04d}.png")
        pix.save(img_path)
        text = page.get_text().strip()
        has_text = 1 if len(text) > 50 else 0
        if has_text:
            with open(os.path.join(txt_dir, f"page_{i:04d}.txt"), "w") as tf:
                tf.write(text[:20000])
        cur.execute("INSERT OR IGNORE INTO page (document_id, page_index, image_path, "
                    "width_px, height_px, has_vector_text, status) VALUES (?,?,?,?,?,?,?)",
                    (dbid, i, os.path.relpath(img_path, ROOT), pix.width, pix.height,
                     has_text, "rendered"))
    cur.execute("UPDATE document SET page_count=?, status='rendered' WHERE id=?",
                (n, dbid))
    db.commit()
    doc.close()
    os.remove(pdf_path)
    return f"ok:{n}"


def main():
    picked = [p for i, p in enumerate(pick_docs()) if i % NSHARDS == SHARD]
    db = sqlite3.connect(os.path.join(ROOT, "data", "estimate.db"), timeout=60)
    db.execute("PRAGMA busy_timeout=30000")
    have = {r[0] for r in db.execute("SELECT onestop_doc_id FROM document "
                                     "WHERE status IN ('rendered','error')")}
    todo = [p for p in picked if int(p[1]) not in have]
    print(f"selected {len(picked)} docs, {len(todo)} to render", flush=True)
    pages = 0
    for j, item in enumerate(todo, 1):
        res = render_doc(db, *item)
        if res.startswith("ok:"):
            pages += int(res.split(":")[1])
        print(f"{j}/{len(todo)} doc {item[1]} ({item[4]}) -> {res} [total pages {pages}]",
              flush=True)
    print(f"DONE: {pages} pages rendered", flush=True)


if __name__ == "__main__":
    main()
