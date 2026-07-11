#!/usr/bin/env python3
"""Single-doc on-demand fetch, invoked from the Ops Documents tab's
"Download" button (web/app/api/ops/fetch-doc/route.ts shells out to this).

Reuses scripts/download_batch.py's proven fetch/validate/upload functions
(HEAD-skip already-in-R2, GET from NOLA One Stop, %PDF magic-byte check,
PUT to R2, never overwrite) instead of duplicating that logic in TS. Logs
to the same standing append-only CSV as the batch downloader so this path
shows up in the existing audit trail.

Usage: python3 scripts/fetch_one_doc.py <doc_id> <permit_num>
Prints one JSON line to stdout: {"doc_id","permit","status","bytes","note"}
status one of: ok, already_in_r2, not_pdf, fetch_error_*, r2_put_failed.
"""
from __future__ import annotations

import json
import sys

from download_batch import (
    append_log_row,
    fetch_to_temp,
    head_r2,
    load_env,
    put_r2,
    r2_client,
)


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: fetch_one_doc.py <doc_id> <permit_num>"}))
        return 2
    doc_id, permit = sys.argv[1], sys.argv[2]

    env = load_env()
    s3 = r2_client(env)
    bucket = env["R2_BUCKET"]

    if head_r2(s3, bucket, doc_id):
        res = {"doc_id": doc_id, "permit": permit, "status": "already_in_r2", "bytes": 0, "note": ""}
        append_log_row(res)
        print(json.dumps(res))
        return 0

    status, path, size = fetch_to_temp(doc_id)
    if status != "ok" or path is None:
        res = {"doc_id": doc_id, "permit": permit, "status": status, "bytes": size, "note": "fetch_one_doc"}
        append_log_row(res)
        print(json.dumps(res))
        return 0 if status == "not_pdf" else 1

    ok = put_r2(s3, bucket, doc_id, path)
    path.unlink(missing_ok=True)
    if not ok:
        res = {"doc_id": doc_id, "permit": permit, "status": "r2_put_failed", "bytes": size, "note": "fetch_one_doc"}
        append_log_row(res)
        print(json.dumps(res))
        return 1

    res = {"doc_id": doc_id, "permit": permit, "status": "ok", "bytes": size, "note": "fetch_one_doc"}
    append_log_row(res)
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
