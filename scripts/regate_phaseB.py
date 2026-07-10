#!/usr/bin/env python3
"""Re-gate step 3, Phase B: for FALSE_PASS permits where Phase A found no
replacement among the already-scored top-8 candidates (status UNCHANGED or
LOST_NO_REPLACEMENT in data/triage/regate_phaseA.csv), widen the candidate
pool to top-N (default 20) by harvested wall_segs from layered_plans.csv,
score any NOT-yet-scored candidates with the same score_page_v2 + title_flag
pipeline scan_closeability_full.py uses, append new rows to
closeability_full.csv (append-only, same schema), and re-pick the best
gate-passing page per permit.

Only runs for the permit list given on argv (so the caller can bound cost
after seeing Phase A's numbers first).
"""
import csv
import os
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import ROOT, r2_client, PDF_TMP_DIR
from scan_closeability_full import (FIELDS, err_row, write_row, OUT as CLOSE,
                                     r2_sizes, SIZE_SKIP, PER_DOC_TIMEOUT)

LAYERED = os.path.join(ROOT, "data", "triage", "layered_plans.csv")
TOPN = int(os.getenv("REGATE_TOPN", "20"))
WORKERS = 4


def widen_candidates(permits, n=TOPN):
    """top-N candidates per permit (widened from the original top-8)."""
    by_permit = defaultdict(dict)
    with open(LAYERED) as f:
        for r in csv.DictReader(f):
            if r["permit"] not in permits:
                continue
            key = (int(r["doc_id"]), int(r["page"]))
            row = (int(r["doc_id"]), int(r["page"]), int(r["wall_segs"]), r["layers"])
            prev = by_permit[r["permit"]].get(key)
            if prev is None or row[2] > prev[2]:
                by_permit[r["permit"]][key] = row
    out = {}
    for permit, rowmap in by_permit.items():
        rows = sorted(rowmap.values(), key=lambda x: -x[2])
        out[permit] = rows[:n]
    return out


def already_scored_keys():
    d = set()
    if os.path.exists(CLOSE):
        with open(CLOSE) as f:
            for r in csv.DictReader(f):
                note = (r.get("note") or "")
                if note.startswith(("crash:", "dl_err", "score_err")):
                    continue
                d.add((r["permit"], str(r["doc_id"]), str(r["page"])))
    return d


def main(permits_file):
    permits = set(l.strip() for l in open(permits_file) if l.strip())
    print(f"{len(permits)} permits to widen (top-{TOPN})", flush=True)

    by_permit = widen_candidates(permits, TOPN)
    done = already_scored_keys()
    sizes = r2_sizes()

    by_doc = defaultdict(list)
    n_new = 0
    for permit, rows in by_permit.items():
        for doc_id, page, wsr, lyr in rows:
            if (permit, str(doc_id), str(page)) in done:
                continue
            if sizes.get(doc_id, 0) > SIZE_SKIP:
                write_row(err_row(permit, doc_id, page, wsr, lyr, "skip_too_big"))
                continue
            by_doc[doc_id].append((permit, page, wsr, lyr))
            n_new += 1
    print(f"{n_new} NEW candidate pages to score across {len(by_doc)} docs", flush=True)

    def run_doc(doc_id, tasks):
        arg = ";".join(f"{p}:{pi}:{wsr}" for p, pi, wsr, _ in tasks)
        cmd = [sys.executable,
               os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_closeability_full.py"),
               "--one", str(doc_id), arg]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=PER_DOC_TIMEOUT)
        except subprocess.TimeoutExpired:
            p = None
        try:
            os.remove(os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf"))
        except OSError:
            pass
        if p is None or p.returncode != 0 or "<<ROWS>>" not in p.stdout or "<<END>>" not in p.stdout:
            why = "timeout" if p is None else f"rc={p.returncode}"
            return [err_row(permit, doc_id, pi, wsr, lyr, f"crash:{why}")
                    for permit, pi, wsr, lyr in tasks]
        body = p.stdout.split("<<ROWS>>", 1)[1].split("<<END>>", 1)[0].strip()
        rows = []
        if body:
            for r in csv.DictReader(body.splitlines(), fieldnames=FIELDS):
                rows.append(r)
        return rows

    n = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_doc, doc_id, tasks): doc_id for doc_id, tasks in by_doc.items()}
        for fut in as_completed(futs):
            doc_id = futs[fut]
            try:
                rows = fut.result()
            except Exception as e:
                print(f"ERROR doc {doc_id}: {e}", flush=True)
                rows = []
            for r in rows:
                write_row(r)
            n += 1
            if n % 10 == 0 or n == len(by_doc):
                print(f"[{n}/{len(by_doc)} docs]", flush=True)
    print("PHASE B SCORING DONE ->", CLOSE, flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
