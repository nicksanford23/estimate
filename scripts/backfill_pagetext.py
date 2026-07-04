#!/usr/bin/env python3
"""Rung-2b, Task 1: backfill missing page text (no re-render, no DB writes).

Rung-2 diagnosis (STATE.md, 2026-07-05): text_only TF-IDF is the winning
signal (finish_recall@0.5 = 0.974) but only 54% of LABELED pages have any
extracted text, because a chunk of the corpus was rendered before
render_pages.py started saving page text. This script closes that gap.

For every document that has at least one page missing its text file, fetch
the source PDF -- a pre-existing local copy under data/pdfs/ if present
(the 11 oldest docs, rendered before a render_tmp-and-delete pipeline
existed), else R2 key docs/<onestop_doc_id>.pdf via boto3 (S3 API,
endpoint R2_ENDPOINT) -- and extract text per page with fitz
(page.get_text()), saving the first 20000 chars whenever len > 50, exactly
like render_pages.py. Images are NOT re-rendered and the DB is NOT touched.
PDFs this script itself fetches are deleted right after extraction; a
pre-existing data/pdfs/ copy is left in place (it wasn't "fetched" here).

Path derivation for "does this page already have text" and "where do I
write it" reuses train_sweep_rung2.text_path_for (imported, not modified,
not copied) so the coverage number this script prints is guaranteed to
match what the training scripts see. That function derives the pagetext
path from each page's own image_path (data/pages/<X>/... ->
data/pagetext/<X>/...), which is important: the 11 oldest docs use the
*internal* document id as <X> (e.g. data/pages/1/...), not the
onestop_doc_id, because they predate render_pages.py's onestop_doc_id-keyed
directory convention. Deriving from image_path (rather than hardcoding
onestop_doc_id) handles both conventions correctly.

Usage
    python3 scripts/backfill_pagetext.py                # full run
    python3 scripts/backfill_pagetext.py --dry-run       # report only
    python3 scripts/backfill_pagetext.py --docs 332,354  # subset (testing)
"""
import argparse
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_sweep_rung2 as ts2  # noqa: E402 (reuse text_path_for, not modified)

STAGING_DIR = os.path.join(ROOT, "data", "render_tmp")
MAX_PDF_BYTES = 500_000_000  # safety guard against a runaway/corrupt object


def load_env():
    env = {}
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def get_pages(db_url):
    """All page rows joined to their document, across the whole corpus (not
    just labeled pages) -- the backfill closes the gap for everyone; the
    coverage report at the end restricts to labeled pages only."""
    import psycopg2
    conn = psycopg2.connect(db_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(
            """
            SELECT p.id, p.image_path, p.page_index, p.document_id,
                   d.onestop_doc_id, d.storage_path
            FROM page p JOIN document d ON d.id = p.document_id
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def get_labeled_page_ids(db_url):
    import psycopg2
    conn = psycopg2.connect(db_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute("SELECT DISTINCT page_id FROM page_label")
        return {int(r[0]) for r in cur.fetchall()}
    finally:
        conn.close()


def coverage(rows, labeled_ids):
    """(n_nonempty, n_total) over LABELED pages, by current on-disk state."""
    total, nonempty = 0, 0
    for pid, image_path, *_rest in rows:
        if pid not in labeled_ids:
            continue
        total += 1
        tp = ts2.text_path_for(image_path)
        if os.path.exists(tp):
            with open(tp, encoding="utf-8", errors="ignore") as f:
                if f.read().strip():
                    nonempty += 1
    return nonempty, total


def s3_client(env):
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def fetch_pdf(s3, env, onestop_doc_id, storage_path):
    """Return (local_path, was_fetched). was_fetched=True means the caller
    must delete it after use. Prefers a pre-existing local data/pdfs/ copy."""
    if storage_path and storage_path.startswith("data/pdfs/"):
        local = os.path.join(ROOT, storage_path)
        if os.path.exists(local):
            return local, False
    os.makedirs(STAGING_DIR, exist_ok=True)
    dest = os.path.join(STAGING_DIR, f"{onestop_doc_id}.pdf")
    key = f"docs/{onestop_doc_id}.pdf"
    head = s3.head_object(Bucket=env["R2_BUCKET"], Key=key)
    if head["ContentLength"] > MAX_PDF_BYTES:
        raise RuntimeError(f"{key}: {head['ContentLength']} bytes exceeds safety cap")
    s3.download_file(env["R2_BUCKET"], key, dest)
    return dest, True


def extract_doc_text(pdf_path, pages):
    """pages: list of (page_id, image_path, page_index). Writes text files
    with the same threshold/truncation as render_pages.py. Returns
    (n_written, n_short_or_blank, n_out_of_range)."""
    import fitz
    doc = fitz.open(pdf_path)
    n_written = n_short = n_oor = 0
    try:
        for _page_id, image_path, page_index in pages:
            if page_index >= len(doc):
                n_oor += 1
                continue
            text = doc[page_index].get_text().strip()
            if len(text) > 50:
                tp = ts2.text_path_for(image_path)
                os.makedirs(os.path.dirname(tp), exist_ok=True)
                with open(tp, "w", encoding="utf-8") as f:
                    f.write(text[:20000])
                n_written += 1
            else:
                n_short += 1
    finally:
        doc.close()
    return n_written, n_short, n_oor


def main(argv=None):
    p = argparse.ArgumentParser(description="Backfill missing page text (rung-2b Task 1).")
    p.add_argument("--dry-run", action="store_true", help="report only, fetch/extract nothing")
    p.add_argument("--docs", default=None,
                   help="comma-separated internal document_id subset, for testing")
    args = p.parse_args(argv)

    env = load_env()
    if "NEON_DATABASE_URL" not in env:
        print("ERROR: NEON_DATABASE_URL not found in .env", file=sys.stderr)
        return 2
    db_url = env["NEON_DATABASE_URL"]

    print("querying Neon for all pages + documents...", flush=True)
    rows = get_pages(db_url)
    labeled_ids = get_labeled_page_ids(db_url)
    print(f"{len(rows)} page rows across the corpus; {len(labeled_ids)} distinct labeled pages",
          flush=True)

    before_nonempty, before_total = coverage(rows, labeled_ids)
    pct = 100 * before_nonempty / before_total if before_total else 0.0
    print(f"BEFORE: labeled pages with non-empty text: {before_nonempty}/{before_total} "
          f"({pct:.1f}%)", flush=True)

    by_doc = defaultdict(list)  # document_id -> [(page_id, image_path, page_index, onestop_id, storage_path)]
    for pid, image_path, page_index, document_id, onestop_id, storage_path in rows:
        by_doc[document_id].append((pid, image_path, page_index, onestop_id, storage_path))

    todo_docs = {}
    for document_id, plist in by_doc.items():
        missing = [t for t in plist if not os.path.exists(ts2.text_path_for(t[1]))]
        if missing:
            onestop_id, storage_path = plist[0][3], plist[0][4]
            todo_docs[document_id] = (onestop_id, storage_path, plist, len(missing))

    if args.docs:
        wanted = {int(x) for x in args.docs.split(",")}
        todo_docs = {k: v for k, v in todo_docs.items() if k in wanted}

    total_missing_pages = sum(v[3] for v in todo_docs.values())
    print(f"\n{len(todo_docs)} documents need backfill "
          f"({total_missing_pages} pages currently missing text, corpus-wide, "
          f"not just labeled)", flush=True)

    ordered = sorted(todo_docs.items(), key=lambda kv: -kv[1][3])
    if args.dry_run:
        for document_id, (onestop_id, storage_path, plist, n_missing) in ordered:
            print(f"  doc_id={document_id} onestop={onestop_id} "
                  f"missing={n_missing}/{len(plist)} src={storage_path}")
        print("\n[dry-run] no fetch/extract performed.")
        return 0

    s3 = s3_client(env)
    n_ok = n_fail = 0
    total_written = total_short = total_oor = 0
    for i, (document_id, (onestop_id, storage_path, plist, n_missing)) in enumerate(ordered, 1):
        pages = [(pid, ip, pidx) for pid, ip, pidx, _, _ in plist]
        try:
            pdf_path, fetched = fetch_pdf(s3, env, onestop_id, storage_path)
        except Exception as e:  # noqa: BLE001 - log and continue the run
            print(f"[{i}/{len(ordered)}] doc_id={document_id} onestop={onestop_id} "
                  f"FETCH FAILED: {type(e).__name__}: {e}", flush=True)
            n_fail += 1
            continue
        try:
            n_written, n_short, n_oor = extract_doc_text(pdf_path, pages)
            total_written += n_written
            total_short += n_short
            total_oor += n_oor
            n_ok += 1
            print(f"[{i}/{len(ordered)}] doc_id={document_id} onestop={onestop_id} "
                  f"pages={len(pages)} written={n_written} short/blank={n_short} "
                  f"oor={n_oor} (missing_before={n_missing})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(ordered)}] doc_id={document_id} onestop={onestop_id} "
                  f"EXTRACT FAILED: {type(e).__name__}: {e}", flush=True)
            n_fail += 1
        finally:
            if fetched and os.path.exists(pdf_path):
                os.remove(pdf_path)

    print(f"\nDONE: {n_ok} docs ok, {n_fail} failed, {total_written} text files written, "
          f"{total_short} pages confirmed short/blank (<=50 chars, no file written), "
          f"{total_oor} pages out of PDF page-count range", flush=True)

    after_nonempty, after_total = coverage(rows, labeled_ids)
    apct = 100 * after_nonempty / after_total if after_total else 0.0
    print(f"\nAFTER: labeled pages with non-empty text: {after_nonempty}/{after_total} "
          f"({apct:.1f}%)", flush=True)
    print(f"COVERAGE DELTA: {before_nonempty}/{before_total} ({pct:.1f}%) -> "
          f"{after_nonempty}/{after_total} ({apct:.1f}%)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
