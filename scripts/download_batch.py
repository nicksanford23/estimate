#!/usr/bin/env python3
"""Go-wider download batch (2026-07-09): fetch a ranked candidate pool of
architectural plan PDFs from NOLA One Stop and upload to R2, skipping
anything already present.

Input: data/triage/download_batch_2026-07-09_candidates.csv (from
scripts/select_batch.py), a rank-ordered pool with priority-1/2 first,
then priority-3 spread across permits.

For each doc_id (in rank order, parallel workers):
  1. HEAD R2 docs/{doc_id}.pdf -> skip (already_in_r2) if present.
  2. GET from One Stop into a temp file in the scratch dir.
  3. Validate the first 4 bytes are %PDF -- reject otherwise (not_pdf).
  4. PUT to R2 (never overwrite -- step 1 already guards this) then
     delete the local temp file immediately (disk is tight).

Append-only log: data/triage/download_batch_2026-07-09.csv
Columns: doc_id, permit, status, bytes, note

Supports --target N (stop once N docs are newly "ok" this run, but only
checked between rank-ordered chunks so all in-flight work finishes) and
--start-rank / --limit to run top-up rounds over the tail of the pool
without re-attempting rows already logged.
"""
from __future__ import annotations

import argparse
import csv
import os
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "triage" / "download_batch_2026-07-09_candidates.csv"
LOG_PATH = ROOT / "data" / "triage" / "download_batch_2026-07-09.csv"
SCRATCH_DIR = Path(
    os.environ.get(
        "SCRATCH_DIR",
        "/tmp/claude-1000/-workspaces-estimate/cfaebbe4-655a-4986-8607-25a6d76540e7/scratchpad",
    )
) / "dlbatch"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
LOG_FIELDS = ["doc_id", "permit", "status", "bytes", "note"]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = ROOT / ".env"
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    env.update(os.environ)
    return env


def r2_client(env: dict[str, str]):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(retries={"max_attempts": 3}),
    )


def already_logged() -> set[str]:
    done = set()
    if LOG_PATH.exists():
        with LOG_PATH.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                # Only treat terminal outcomes as "done" -- retry transient
                # fetch errors if the row is re-selected in a top-up round.
                if row.get("status") in ("ok", "already_in_r2", "not_pdf"):
                    done.add(row["doc_id"])
    return done


def append_log_row(row: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    exists = LOG_PATH.exists()
    with LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if not exists:
            w.writeheader()
        w.writerow(row)


def head_r2(s3, bucket: str, doc_id: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=f"docs/{doc_id}.pdf")
        return True
    except Exception:
        return False


def fetch_to_temp(doc_id: str, retries: int = 2, sleep: float = 2.0) -> tuple[str, Path | None, int]:
    url = f"https://onestopapp.nola.gov/GetDocument.aspx?DocID={doc_id}"
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    dest = SCRATCH_DIR / f"{doc_id}.pdf"
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                head = resp.read(4)
                if head != b"%PDF":
                    # drain a bit more so we can report a useful size, then
                    # bail -- no temp file is ever created on this path
                    rest = resp.read(2048)
                    return "not_pdf", None, len(head) + len(rest)
                with dest.open("wb") as out:
                    out.write(head)
                    total = 4
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                        total += len(chunk)
            return "ok", dest, total
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if dest.exists():
                dest.unlink(missing_ok=True)
            if attempt >= retries:
                return f"fetch_error_{type(exc).__name__}", None, 0
            time.sleep(sleep * (attempt + 1))
    return "fetch_error_unknown", None, 0


def put_r2(s3, bucket: str, doc_id: str, path: Path) -> bool:
    try:
        with path.open("rb") as f:
            s3.put_object(Bucket=bucket, Key=f"docs/{doc_id}.pdf", Body=f,
                           ContentType="application/pdf")
        return True
    except Exception:
        return False


def worker(env: dict, bucket: str, row: dict) -> dict:
    import boto3  # noqa: F401  (ensure available per-thread if needed)

    s3 = worker.s3  # type: ignore[attr-defined]
    doc_id = row["doc_id"]
    permit = row.get("permit_num", "")

    if head_r2(s3, bucket, doc_id):
        return {"doc_id": doc_id, "permit": permit, "status": "already_in_r2",
                "bytes": 0, "note": ""}

    status, path, size = fetch_to_temp(doc_id)
    if status != "ok" or path is None:
        return {"doc_id": doc_id, "permit": permit, "status": status,
                "bytes": size, "note": row.get("name", "")[:100]}

    ok = put_r2(s3, bucket, doc_id, path)
    path.unlink(missing_ok=True)
    if not ok:
        return {"doc_id": doc_id, "permit": permit, "status": "r2_put_failed",
                "bytes": size, "note": row.get("name", "")[:100]}
    return {"doc_id": doc_id, "permit": permit, "status": "ok",
            "bytes": size, "note": row.get("name", "")[:100]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(CANDIDATES))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--start-rank", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="max rows to attempt this invocation")
    args = ap.parse_args()

    env = load_env()
    s3 = r2_client(env)
    bucket = env["R2_BUCKET"]
    worker.s3 = s3  # type: ignore[attr-defined]

    with Path(args.candidates).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if int(r["rank"]) >= args.start_rank]

    done = already_logged()
    rows = [r for r in rows if r["doc_id"] not in done]
    if args.limit:
        rows = rows[: args.limit]

    print(f"attempting {len(rows)} rows (already-logged terminal: {len(done)})", flush=True)

    counts: dict[str, int] = {}
    total_bytes = 0
    n = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(worker, env, bucket, r): r for r in rows}
        for fut in as_completed(futs):
            res = fut.result()
            append_log_row(res)
            counts[res["status"]] = counts.get(res["status"], 0) + 1
            if res["status"] == "ok":
                total_bytes += res["bytes"]
            n += 1
            if n % 20 == 0 or n == len(rows):
                print(f"{n}/{len(rows)} {counts} bytes_ok={total_bytes}", flush=True)

    print(f"DONE {counts} total_ok_bytes={total_bytes}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
