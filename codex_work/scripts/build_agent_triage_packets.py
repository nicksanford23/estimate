#!/usr/bin/env python3
"""Build neutral permit/document packets for agent download triage.

This script intentionally does not decide what to download. It only gathers the
permit metadata, document names, and already-downloaded state needed by agents.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs"
BATCH_DIR = OUT_DIR / "agent_triage_batches"


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


def one_line(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text).strip()


def list_r2_doc_ids(env: dict[str, str]) -> set[int]:
    import boto3

    required = ["R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RuntimeError(f"missing R2 env keys: {', '.join(missing)}")

    client = boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    out: set[int] = set()
    token = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": env["R2_BUCKET"], "Prefix": "docs/"}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        for obj in response.get("Contents", []):
            key = obj.get("Key", "")
            match = re.fullmatch(r"docs/(\d+)\.pdf", key)
            if match:
                out.add(int(match.group(1)))
        if not response.get("IsTruncated"):
            return out
        token = response.get("NextContinuationToken")


def fetch_rows(database_url: str) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    import psycopg2

    docs_sql = """
        SELECT
            d.doc_id,
            d.permit_num,
            d.name,
            p.code,
            p.tier,
            p.description,
            p.cost,
            p.sqft,
            p.address,
            p.city,
            p.zip,
            p.permit_class,
            p.status,
            p.applied_date,
            p.issue_date,
            p.contractor,
            p.doc_count
        FROM estimate.documents d
        JOIN estimate.permits p USING (permit_num)
        ORDER BY d.permit_num, d.doc_id
    """
    working_sql = """
        SELECT onestop_doc_id, status, page_count, storage_path
        FROM estimate.document
    """
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(docs_sql)
        doc_cols = [desc[0] for desc in cur.description]
        docs = [dict(zip(doc_cols, row)) for row in cur.fetchall()]

        cur.execute(working_sql)
        working: dict[int, dict[str, Any]] = {}
        for doc_id, status, page_count, storage_path in cur.fetchall():
            working[int(doc_id)] = {
                "working_status": status or "",
                "page_count": page_count,
                "storage_path": storage_path or "",
            }
    finally:
        conn.close()
    return docs, working


def build_packets(
    rows: list[dict[str, Any]],
    working: dict[int, dict[str, Any]],
    r2_doc_ids: set[int],
    include_fully_downloaded: bool,
) -> list[dict[str, Any]]:
    by_permit: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_permit.setdefault(row["permit_num"], []).append(row)

    packets: list[dict[str, Any]] = []
    for permit_num, permit_rows in sorted(by_permit.items()):
        head = permit_rows[0]
        docs = []
        downloaded_count = 0
        pdf_count = 0
        for row in permit_rows:
            doc_id = int(row["doc_id"])
            in_r2 = doc_id in r2_doc_ids
            working_meta = working.get(doc_id, {})
            working_status = working_meta.get("working_status", "")
            already_downloaded = in_r2 or working_status in {"downloaded", "rendered"}
            if already_downloaded:
                downloaded_count += 1
            name = one_line(row["name"])
            is_pdf = bool(re.search(r"\.pdf(?:\s|$|\()", name, re.I))
            if is_pdf:
                pdf_count += 1
            docs.append(
                {
                    "doc_id": doc_id,
                    "name": name,
                    "is_pdf": is_pdf,
                    "already_downloaded": already_downloaded,
                    "in_r2": in_r2,
                    "working_status": working_status,
                    "working_page_count": working_meta.get("page_count"),
                }
            )

        if downloaded_count == len(docs) and not include_fully_downloaded:
            continue

        packets.append(
            {
                "permit_num": permit_num,
                "code": one_line(head.get("code")),
                "tier": one_line(head.get("tier")),
                "address": one_line(head.get("address")),
                "city": one_line(head.get("city")),
                "zip": one_line(head.get("zip")),
                "permit_class": one_line(head.get("permit_class")),
                "permit_status": one_line(head.get("status")),
                "applied_date": one_line(head.get("applied_date")),
                "issue_date": one_line(head.get("issue_date")),
                "cost": head.get("cost"),
                "sqft": head.get("sqft"),
                "contractor": one_line(head.get("contractor")),
                "description": one_line(head.get("description")),
                "declared_doc_count": head.get("doc_count"),
                "doc_count": len(docs),
                "pdf_count": pdf_count,
                "already_downloaded_count": downloaded_count,
                "undownloaded_count": len(docs) - downloaded_count,
                "documents": docs,
            }
        )
    return packets


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def write_batches(path: Path, packets: list[dict[str, Any]], batch_size: int) -> list[Path]:
    path.mkdir(parents=True, exist_ok=True)
    for old in path.glob("batch_*.jsonl"):
        old.unlink()
    out: list[Path] = []
    for index in range(0, len(packets), batch_size):
        batch = packets[index : index + batch_size]
        batch_path = path / f"batch_{len(out):03d}.jsonl"
        write_jsonl(batch_path, batch)
        out.append(batch_path)
    return out


def write_manifest(
    path: Path,
    packets: list[dict[str, Any]],
    batch_paths: list[Path],
    raw_doc_count: int,
    r2_count: int,
    working_count: int,
    batch_size: int,
) -> None:
    by_code = Counter(packet["code"] for packet in packets)
    status_counts = Counter()
    for packet in packets:
        if packet["already_downloaded_count"] == 0:
            status_counts["not_started"] += 1
        elif packet["already_downloaded_count"] == packet["doc_count"]:
            status_counts["fully_downloaded"] += 1
        else:
            status_counts["partially_downloaded"] += 1

    lines = [
        "# Agent Triage Packet Manifest",
        "",
        "Neutral export for agent document triage. No download decisions are made by the script.",
        "",
        "## Counts",
        "",
        f"- Raw Neon document rows: {raw_doc_count}",
        f"- Permit packets needing review: {len(packets)}",
        f"- R2 already-downloaded doc ids: {r2_count}",
        f"- Working pipeline downloaded/rendered doc ids: {working_count}",
        f"- Batch size: {batch_size}",
        f"- Batch files: {len(batch_paths)}",
        "",
        "## Permit Download Status",
        "",
        "| status | permits |",
        "|---|---:|",
    ]
    for status, count in status_counts.most_common():
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Permit Types", "", "| code | permits |", "|---|---:|"])
    for code, count in by_code.most_common():
        lines.append(f"| {code} | {count} |")
    lines.extend(["", "## Files", ""])
    lines.append("- `agent_triage_packets.jsonl`: all permit packets.")
    lines.append("- `agent_triage_batches/batch_*.jsonl`: same packets split for agents.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--skip-r2", action="store_true")
    parser.add_argument("--include-fully-downloaded", action="store_true")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args()

    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    env = load_env()
    database_url = args.database_url or env.get("NEON_DATABASE_URL")
    if not database_url:
        raise SystemExit("NEON_DATABASE_URL missing")

    docs, working = fetch_rows(database_url)
    working_ready = {
        doc_id
        for doc_id, meta in working.items()
        if meta.get("working_status") in {"downloaded", "rendered"}
    }
    r2_doc_ids = set() if args.skip_r2 else list_r2_doc_ids(env)
    packets = build_packets(
        docs,
        working,
        r2_doc_ids,
        include_fully_downloaded=args.include_fully_downloaded,
    )

    out_dir = Path(args.out_dir)
    batch_dir = out_dir / "agent_triage_batches"
    packet_path = out_dir / "agent_triage_packets.jsonl"
    manifest_path = out_dir / "agent_triage_manifest.md"

    write_jsonl(packet_path, packets)
    batch_paths = write_batches(batch_dir, packets, args.batch_size)
    write_manifest(
        manifest_path,
        packets,
        batch_paths,
        len(docs),
        len(r2_doc_ids),
        len(working_ready),
        args.batch_size,
    )

    print(f"packets={len(packets)}")
    print(f"batches={len(batch_paths)}")
    print(f"wrote={packet_path}")
    print(f"wrote={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
