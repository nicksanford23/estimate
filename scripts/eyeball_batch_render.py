#!/usr/bin/env python3
"""Batch driver for eyeball_render.py over a slice CSV (permit,doc_id,page,fpp).
Idempotent (skips existing jpgs). Deletes each PDF right after its render
(disk is tight). SUBPROCESS-ISOLATED per row (fitz segfaults / OOM kills are
observed on this corpus per scan_closeability_full.py's docstring -- a crash
in-process would silently kill the whole batch and every remaining row, which
is what happened on the first run here: 17/51 done then the process vanished
with no error line). A crashed/timed-out row is skipped and reported; rerun
the batch to retry it (idempotent)."""
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
    out_jpg = os.path.join(OUTDIR, f"{permit}.jpg")
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
