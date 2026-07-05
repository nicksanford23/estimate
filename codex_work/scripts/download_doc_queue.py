#!/usr/bin/env python3
"""Download a reviewed doc-id queue from One Stop into R2.

Input CSV must include a `doc_id` column. This script is intentionally targeted:
it only downloads the reviewed queue and writes an append-only run log.
"""
from __future__ import annotations

import argparse
import csv
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs"
LOCAL_DIR = ROOT / "data" / "pdfs_r2"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


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


def head_r2(s3, bucket: str, doc_id: int) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=f"docs/{doc_id}.pdf")
        return True
    except Exception:
        return False


def put_r2(s3, bucket: str, doc_id: int, path: Path) -> None:
    with path.open("rb") as f:
        s3.put_object(Bucket=bucket, Key=f"docs/{doc_id}.pdf", Body=f, ContentType="application/pdf")


def fetch_doc(doc_id: int, dest: Path, retries: int, sleep: float) -> tuple[str, int]:
    url = f"https://onestopapp.nola.gov/GetDocument.aspx?DocID={doc_id}"
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                data = response.read()
            if not data.startswith(b"%PDF"):
                return "not_pdf", len(data)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return "ok", len(data)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt >= retries:
                return f"fetch_error_{type(exc).__name__}", 0
            time.sleep(sleep * (attempt + 1))
    return "fetch_error_unknown", 0


def append_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["doc_id", "status", "bytes", "permit_num", "name"]
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--log", default=str(OUT_DIR / "targeted_download_run.csv"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep", type=float, default=1.5)
    args = parser.parse_args()

    env = load_env()
    s3 = r2_client(env)
    bucket = env["R2_BUCKET"]
    queue = read_queue(Path(args.queue))
    if args.limit:
        queue = queue[: args.limit]

    counts: dict[str, int] = {}
    for index, item in enumerate(queue, 1):
        doc_id = int(item["doc_id"])
        name = item.get("name", "")
        dest = LOCAL_DIR / f"{doc_id}.pdf"
        if head_r2(s3, bucket, doc_id):
            status, size = "already_in_r2", 0
        else:
            status, size = fetch_doc(doc_id, dest, args.retries, args.sleep)
            if status == "ok":
                put_r2(s3, bucket, doc_id, dest)
        counts[status] = counts.get(status, 0) + 1
        append_log(
            Path(args.log),
            {
                "doc_id": doc_id,
                "status": status,
                "bytes": size,
                "permit_num": item.get("permit_num", ""),
                "name": name,
            },
        )
        print(f"{index}/{len(queue)} {doc_id} {status} {size} {name[:80]}", flush=True)

    print(f"DONE {counts}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
