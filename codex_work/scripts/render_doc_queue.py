#!/usr/bin/env python3
"""Render a reviewed doc-id queue from R2 into Neon document/page rows."""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs"
STAGING_DIR = ROOT / "data" / "render_tmp"
PAGES_DIR = ROOT / "data" / "pages"
TEXT_DIR = ROOT / "data" / "pagetext"
LONG_EDGE = 1568


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key] = value
    env.update(os.environ)
    return env


def read_queue(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    seen = set()
    for row in rows:
        doc_id = int(row["doc_id"])
        if doc_id in seen:
            continue
        seen.add(doc_id)
        row["doc_id"] = doc_id
        out.append(row)
    return out


def r2_client(env: dict[str, str]):
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def fetch_r2(s3, bucket: str, doc_id: int) -> Path:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    path = STAGING_DIR / f"{doc_id}.pdf"
    with path.open("wb") as f:
        s3.download_fileobj(bucket, f"docs/{doc_id}.pdf", f)
    return path


def fetch_metadata(conn, doc_id: int) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.doc_id, d.permit_num, d.name
            FROM estimate.documents d
            WHERE d.doc_id = %s
            """,
            (doc_id,),
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"doc_id {doc_id} missing from estimate.documents")
    return {"doc_id": int(row[0]), "permit_num": row[1], "name": row[2]}


def upsert_document(conn, meta: dict[str, Any], pdf_path: Path, sha256: str, status: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO estimate.document
                (permit_num, onestop_doc_id, filename, sha256, bytes, storage_path, status, downloaded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (onestop_doc_id) DO UPDATE SET
                filename = EXCLUDED.filename,
                sha256 = EXCLUDED.sha256,
                bytes = EXCLUDED.bytes,
                storage_path = EXCLUDED.storage_path,
                status = EXCLUDED.status,
                downloaded_at = COALESCE(estimate.document.downloaded_at, EXCLUDED.downloaded_at)
            RETURNING id
            """,
            (
                meta["permit_num"],
                meta["doc_id"],
                meta["name"],
                sha256,
                pdf_path.stat().st_size,
                f"r2:docs/{meta['doc_id']}.pdf",
                status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return int(cur.fetchone()[0])


def render_one(conn, s3, bucket: str, doc_id: int, max_pages: int) -> tuple[str, int]:
    import fitz

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, status, page_count FROM estimate.document WHERE onestop_doc_id = %s",
            (doc_id,),
        )
        existing = cur.fetchone()
        if existing and existing[1] == "rendered" and existing[2]:
            return "already_rendered", int(existing[2])

    meta = fetch_metadata(conn, doc_id)
    pdf_path = fetch_r2(s3, bucket, doc_id)
    data = pdf_path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    document_id = upsert_document(conn, meta, pdf_path, sha256, "downloaded")
    conn.commit()

    try:
        pdf = fitz.open(pdf_path)
    except Exception as exc:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE estimate.document SET status = 'error', error = %s WHERE id = %s",
                (f"open_failed:{type(exc).__name__}", document_id),
            )
        conn.commit()
        return "open_failed", 0

    n_pages = min(len(pdf), max_pages)
    img_dir = PAGES_DIR / str(doc_id)
    txt_dir = TEXT_DIR / str(doc_id)
    img_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM estimate.page WHERE document_id = %s", (document_id,))
        for page_index in range(n_pages):
            page = pdf[page_index]
            zoom = LONG_EDGE / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            image_path = img_dir / f"page_{page_index:04d}.png"
            text_path = txt_dir / f"page_{page_index:04d}.txt"
            pix.save(str(image_path))
            text = page.get_text().strip()
            has_vector_text = bool(len(text) > 50)
            if has_vector_text:
                text_path.write_text(text[:20000], encoding="utf-8", errors="ignore")
            cur.execute(
                """
                INSERT INTO estimate.page
                    (document_id, page_index, image_path, width_px, height_px, has_vector_text, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'rendered')
                """,
                (
                    document_id,
                    page_index,
                    str(image_path.relative_to(ROOT)),
                    pix.width,
                    pix.height,
                    int(has_vector_text),
                ),
            )
        cur.execute(
            "UPDATE estimate.document SET page_count = %s, status = 'rendered', error = NULL WHERE id = %s",
            (n_pages, document_id),
        )
    conn.commit()
    pdf.close()
    pdf_path.unlink(missing_ok=True)
    return "rendered", n_pages


def append_log(path: Path, row: dict[str, Any]) -> None:
    fields = ["doc_id", "status", "pages"]
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    import psycopg2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--log", default=str(OUT_DIR / "targeted_render_run.csv"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-pages", type=int, default=200)
    args = parser.parse_args()

    env = load_env()
    queue = read_queue(Path(args.queue))
    if args.limit:
        queue = queue[: args.limit]

    s3 = r2_client(env)
    conn = psycopg2.connect(env["NEON_DATABASE_URL"])
    conn.autocommit = False
    counts: dict[str, int] = {}
    try:
        for index, row in enumerate(queue, 1):
            doc_id = int(row["doc_id"])
            try:
                status, pages = render_one(conn, s3, env["R2_BUCKET"], doc_id, args.max_pages)
            except Exception as exc:
                conn.rollback()
                status, pages = f"error:{type(exc).__name__}", 0
            counts[status] = counts.get(status, 0) + 1
            append_log(Path(args.log), {"doc_id": doc_id, "status": status, "pages": pages})
            print(f"{index}/{len(queue)} {doc_id} {status} pages={pages}", flush=True)
    finally:
        conn.close()
    print(f"DONE {counts}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
