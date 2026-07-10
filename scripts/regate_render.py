#!/usr/bin/env python3
"""Batch-render regate candidates to data/triage/eyeball/{permit}-regate.jpg
(distinct filename from the original {permit}.jpg so we don't collide with /
skip-via-idempotence over the original false-pass overlay). Same subprocess-
isolation pattern as eyeball_batch_render.py (fitz crashes cost one row, not
the batch). CSV columns: permit,doc_id,page,fpp."""
import csv
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "data", "triage", "eyeball")
RENDER_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eyeball_render.py")
TIMEOUT = 240


def run_one(row):
    permit = row["permit"]
    out_jpg = os.path.join(OUTDIR, f"{permit}-regate.jpg")
    if os.path.exists(out_jpg):
        print(f"{permit} SKIP (exists)", flush=True)
        return
    cmd = [sys.executable, RENDER_PY, permit, row["doc_id"], row["page"], row["fpp"], out_jpg]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        if p.returncode != 0:
            print(f"{permit} CRASH rc={p.returncode} stderr_tail={p.stderr[-300:]!r}", flush=True)
        else:
            print(p.stdout.strip(), flush=True)
    except subprocess.TimeoutExpired:
        print(f"{permit} TIMEOUT after {TIMEOUT}s", flush=True)


def main(csv_path):
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(run_one, r) for r in rows]
        for fut in as_completed(futs):
            fut.result()
    print("BATCH DONE", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
