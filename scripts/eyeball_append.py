#!/usr/bin/env python3
"""Append one verdict row to data/triage/eyeball_verdicts.csv. Single-line,
append-mode, flushed immediately -- safe for concurrent writers (each writer
opens/writes/closes per call, O_APPEND is atomic for writes under PIPE_BUF).

Usage: python3 eyeball_append.py <permit> <doc_id> <page> <verdict> \
           <is_floor_plan> <reason> <slice_id>
"""
import csv
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "triage", "eyeball_verdicts.csv")
FIELDS = ["permit", "doc_id", "page", "verdict", "is_floor_plan", "reason", "slice", "ts_utc"]


def append_row(permit, doc_id, page, verdict, is_floor_plan, reason, slice_id):
    write_header = not os.path.exists(OUT) or os.path.getsize(OUT) == 0
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerow(dict(permit=permit, doc_id=doc_id, page=page, verdict=verdict,
                         is_floor_plan=is_floor_plan, reason=reason, slice=slice_id, ts_utc=ts))
        f.flush()


if __name__ == "__main__":
    args = sys.argv[1:8]
    append_row(*args)
    print("appended", args[0], args[3])
