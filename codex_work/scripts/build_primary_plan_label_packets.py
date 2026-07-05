#!/usr/bin/env python3
"""Build Claude-friendly primary plan labeling packets for rendered pages.

This is a Codex-only export helper. It reads the reviewed primary-plan queue,
the render run log, and Neon document/page rows. It does not render, download,
or write labels.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs"
DEFAULT_QUEUE = OUT_DIR / "download_queue_primary_plan_full.csv"
DEFAULT_RENDER_LOG = OUT_DIR / "targeted_render_run.csv"
DEFAULT_OUT_DIR = OUT_DIR / "primary_plan_labeling"

PACKET_NAME = "primary_plan_label_packets.jsonl"
MANIFEST_NAME = "primary_plan_labeling_manifest.md"
DOCS_NAME = "primary_plan_docs.csv"

BLANK_LABEL_FIELDS = [
    "category",
    "keep",
    "sheet_title",
    "scale_visible",
    "usable_scale",
    "finish_codes_visible",
    "table_present",
    "room_labels_visible",
    "dimensions_visible",
    "floor_finish_group_id",
    "applies_to_area",
    "review_status",
    "confidence",
    "notes",
]


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
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        rows = list(csv.DictReader(f))

    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        raw_doc_id = (row.get("doc_id") or "").strip()
        if not raw_doc_id:
            continue
        doc_id = int(raw_doc_id)
        if doc_id in seen:
            continue
        seen.add(doc_id)
        out.append(
            {
                "doc_id": doc_id,
                "permit_num": row.get("permit_num", ""),
                "filename": row.get("name", ""),
            }
        )
    return out


def read_render_log(path: Path) -> dict[int, dict[str, Any]]:
    if not path.exists():
        return {}

    latest: dict[int, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            raw_doc_id = (row.get("doc_id") or "").strip()
            if not raw_doc_id:
                continue
            doc_id = int(raw_doc_id)
            raw_pages = (row.get("pages") or "").strip()
            latest[doc_id] = {
                "render_status": row.get("status", ""),
                "render_log_pages": int(raw_pages) if raw_pages.isdigit() else None,
            }
    return latest


def fetch_page_rows(database_url: str, doc_ids: list[int]) -> list[dict[str, Any]]:
    if not doc_ids:
        return []

    import psycopg2

    sql = """
    SELECT
      d.permit_num,
      d.onestop_doc_id AS doc_id,
      d.id AS document_id,
      d.filename,
      d.page_count AS document_page_count,
      d.status AS document_status,
      p.id AS page_id,
      p.page_index,
      p.image_path,
      p.has_vector_text,
      p.status AS page_status
    FROM estimate.document d
    JOIN estimate.page p ON p.document_id = d.id
    WHERE d.onestop_doc_id = ANY(%s)
      AND p.status = 'rendered'
    ORDER BY d.permit_num, d.onestop_doc_id, p.page_index
    """
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(sql, (doc_ids,))
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

    for row in rows:
        row["doc_id"] = int(row["doc_id"])
        row["document_id"] = int(row["document_id"])
        row["page_id"] = int(row["page_id"])
        row["page_index"] = int(row["page_index"])
        row["has_vector_text"] = bool(row["has_vector_text"])
    return rows


def fetch_doc_rows(database_url: str, doc_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not doc_ids:
        return {}

    import psycopg2

    sql = """
    SELECT
      permit_num,
      onestop_doc_id AS doc_id,
      id AS document_id,
      filename,
      page_count AS document_page_count,
      status AS document_status
    FROM estimate.document
    WHERE onestop_doc_id = ANY(%s)
    ORDER BY permit_num, onestop_doc_id
    """
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(sql, (doc_ids,))
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        doc_id = int(row["doc_id"])
        row["doc_id"] = doc_id
        row["document_id"] = int(row["document_id"])
        out[doc_id] = row
    return out


def text_path_for(doc_id: int, page_index: int) -> str:
    return f"data/pagetext/{doc_id}/page_{page_index:04d}.txt"


def image_path_for(row: dict[str, Any]) -> str:
    image_path = row.get("image_path") or ""
    if image_path:
        return image_path
    return f"data/pages/{row['doc_id']}/page_{row['page_index']:04d}.png"


def build_packets(page_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for row in page_rows:
        packet = {
            "permit_num": row["permit_num"],
            "doc_id": row["doc_id"],
            "document_id": row["document_id"],
            "page_id": row["page_id"],
            "page_index": row["page_index"],
            "image_path": image_path_for(row),
            "text_path": text_path_for(row["doc_id"], row["page_index"]),
            "filename": row.get("filename") or "",
        }
        packet.update({field: None for field in BLANK_LABEL_FIELDS})
        packets.append(packet)
    return packets


def summarize_docs(
    queue_rows: list[dict[str, Any]],
    render_log: dict[int, dict[str, Any]],
    doc_rows: dict[int, dict[str, Any]],
    page_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pages_by_doc: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in page_rows:
        pages_by_doc[row["doc_id"]].append(row)

    out: list[dict[str, Any]] = []
    for item in queue_rows:
        doc_id = item["doc_id"]
        doc = doc_rows.get(doc_id, {})
        pages = pages_by_doc.get(doc_id, [])
        log = render_log.get(doc_id, {})
        permit_num = doc.get("permit_num") or item.get("permit_num") or ""
        filename = doc.get("filename") or item.get("filename") or ""
        out.append(
            {
                "permit_num": permit_num,
                "doc_id": doc_id,
                "document_id": doc.get("document_id", ""),
                "filename": filename,
                "render_status": log.get("render_status", ""),
                "render_log_pages": log.get("render_log_pages", ""),
                "document_status": doc.get("document_status", ""),
                "document_page_count": doc.get("document_page_count", ""),
                "packet_page_count": len(pages),
                "vector_text_count": sum(1 for page in pages if page["has_vector_text"]),
            }
        )
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def write_docs_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "permit_num",
        "doc_id",
        "document_id",
        "filename",
        "render_status",
        "render_log_pages",
        "document_status",
        "document_page_count",
        "packet_page_count",
        "vector_text_count",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_manifest(
    path: Path,
    packets: list[dict[str, Any]],
    doc_summaries: list[dict[str, Any]],
    queue_path: Path,
    render_log_path: Path,
) -> None:
    permit_counts: dict[str, dict[str, int]] = {}
    for row in doc_summaries:
        permit_num = row["permit_num"]
        counts = permit_counts.setdefault(
            permit_num,
            {"docs": 0, "docs_with_pages": 0, "pages": 0, "vector_text": 0},
        )
        counts["docs"] += 1
        page_count = int(row["packet_page_count"] or 0)
        vector_count = int(row["vector_text_count"] or 0)
        counts["pages"] += page_count
        counts["vector_text"] += vector_count
        if page_count:
            counts["docs_with_pages"] += 1

    total_pages = len(packets)
    total_vector = sum(int(row["vector_text_count"] or 0) for row in doc_summaries)
    docs_with_pages = sum(1 for row in doc_summaries if int(row["packet_page_count"] or 0) > 0)

    lines = [
        "# Primary Plan Labeling Manifest",
        "",
        "Codex-only export for Claude labeling. This packet is read-only source material; do not write labels from this script.",
        "",
        "## Inputs",
        "",
        f"- Queue CSV: `{queue_path.relative_to(ROOT)}`",
        f"- Render log: `{render_log_path.relative_to(ROOT)}`",
        "",
        "## Outputs",
        "",
        f"- Packet JSONL: `{PACKET_NAME}`",
        f"- Document CSV: `{DOCS_NAME}`",
        "",
        "## Totals",
        "",
        f"- Queue documents: {len(doc_summaries)}",
        f"- Documents with rendered packet pages: {docs_with_pages}",
        f"- Total packet pages: {total_pages}",
        f"- Pages with vector text: {total_vector}",
        "",
        "## Counts By Permit",
        "",
        "| permit_num | docs | docs_with_pages | pages | vector_text_pages |",
        "|---|---:|---:|---:|---:|",
    ]
    for permit_num, counts in sorted(permit_counts.items()):
        lines.append(
            f"| {permit_num} | {counts['docs']} | {counts['docs_with_pages']} | "
            f"{counts['pages']} | {counts['vector_text']} |"
        )

    lines.extend(
        [
            "",
            "## Counts By Document",
            "",
            "| permit_num | doc_id | document_id | pages | vector_text_pages | render_status | filename |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in doc_summaries:
        filename = str(row["filename"]).replace("|", "\\|")
        lines.append(
            f"| {row['permit_num']} | {row['doc_id']} | {row['document_id']} | "
            f"{row['packet_page_count']} | {row['vector_text_count']} | "
            f"{row['render_status']} | {filename} |"
        )

    lines.extend(
        [
            "",
            "## Output Instructions",
            "",
            "- Each JSONL row is one rendered page from `estimate.page` for a queued primary-plan document.",
            "- Fill only the blank labeling fields: `category`, `keep`, `sheet_title`, `scale_visible`, `usable_scale`, `finish_codes_visible`, `table_present`, `room_labels_visible`, `dimensions_visible`, `floor_finish_group_id`, `applies_to_area`, `review_status`, `confidence`, and `notes`.",
            "- Do not edit ID, path, permit, document, page, or filename fields.",
            "- Use `image_path` as the visual source. Use `text_path` when present for searchable vector text context.",
            "- Leave uncertain values blank or explain the uncertainty in `notes`; this packet is not an import file.",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE), help="Primary plan queue CSV.")
    parser.add_argument("--render-log", default=str(DEFAULT_RENDER_LOG), help="Render run CSV.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory.")
    parser.add_argument("--database-url", default=None, help="Override NEON_DATABASE_URL.")
    args = parser.parse_args()

    env = load_env()
    database_url = args.database_url or env.get("NEON_DATABASE_URL")
    if not database_url:
        raise SystemExit("NEON_DATABASE_URL missing from .env/env; pass --database-url")

    queue_path = Path(args.queue)
    render_log_path = Path(args.render_log)
    out_dir = Path(args.out_dir)

    queue_rows = read_queue(queue_path)
    render_log = read_render_log(render_log_path)
    doc_ids = [row["doc_id"] for row in queue_rows]

    doc_rows = fetch_doc_rows(database_url, doc_ids)
    page_rows = fetch_page_rows(database_url, doc_ids)
    packets = build_packets(page_rows)
    doc_summaries = summarize_docs(queue_rows, render_log, doc_rows, page_rows)

    jsonl_path = out_dir / PACKET_NAME
    manifest_path = out_dir / MANIFEST_NAME
    docs_path = out_dir / DOCS_NAME

    write_jsonl(jsonl_path, packets)
    write_docs_csv(docs_path, doc_summaries)
    write_manifest(manifest_path, packets, doc_summaries, queue_path, render_log_path)

    vector_text_count = sum(1 for row in page_rows if row["has_vector_text"])
    print(f"queue_docs={len(queue_rows)} packet_pages={len(packets)} vector_text_pages={vector_text_count}")
    print(f"wrote {jsonl_path}")
    print(f"wrote {manifest_path}")
    print(f"wrote {docs_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
