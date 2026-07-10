#!/usr/bin/env python3
"""Overnight auto-downloader — drains the discovery crawl as it fills.

Loop (every 30 min): query estimate.discovered_docs (Neon, read-only) for
plan-like PDF filenames not yet in R2, download directly via GetDocument
(never One Stop search), %PDF-validate, upload to R2 docs/{doc_id}.pdf,
append to the standing download log, then run the resumable layer harvest
so new arrivals enter the funnel immediately. Zero tokens; survives via
setsid nohup. Exits after the discovery run reports a terminal state AND
two consecutive idle cycles.

Reuses download_batch.py machinery (fetch/validate/upload/log) and
select_batch.py's junk filter. Caps per cycle to stay gentle on disk.

Run:  setsid nohup python3 scripts/overnight_downloader.py \
        > data/triage/overnight_dl.log 2>&1 &
"""
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from download_batch import (already_logged, append_log_row, head_r2,
                            load_env, r2_client, worker)
from select_batch import JUNK_RE

BUCKET = "nola-permit-docs"
CYCLE_SECONDS = 900
PER_CYCLE_CAP = 800
WORKERS = 6
PLAN_LIKE = re.compile(r"\.pdf$", re.I)


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def discovery_state(cur) -> str:
    try:
        cur.execute("SELECT final_state FROM estimate.discovery_runs "
                    "ORDER BY run_id DESC LIMIT 1")
        row = cur.fetchone()
        return (row[0] or "running") if row else "unknown"
    except Exception:
        return "unknown"


def candidates(cur, logged: set) -> list:
    cur.execute("SELECT doc_id, permit_num, filename FROM estimate.discovered_docs "
                "WHERE doc_id > 0 ORDER BY discovered_at")
    out = []
    for doc_id, permit, name in cur.fetchall():
        name = name or ""
        if not PLAN_LIKE.search(name):
            continue
        if JUNK_RE.search(name):
            continue
        if str(doc_id) in logged:
            continue
        out.append({"doc_id": str(doc_id), "permit_num": permit,
                    "name": name, "priority": "disc"})
    return out


def main() -> int:
    import psycopg2
    env = load_env()
    s3 = r2_client(env)
    worker.s3 = s3  # the download_batch worker reads its client from here
    idle_cycles = 0
    log("overnight downloader start")
    while True:
        try:
            conn = psycopg2.connect(env["NEON_DATABASE_URL"])
            cur = conn.cursor()
            logged = already_logged()
            todo = candidates(cur, logged)
            state = discovery_state(cur)
            conn.close()
        except Exception as ex:
            log(f"WARN neon query failed: {ex}")
            time.sleep(CYCLE_SECONDS)
            continue

        batch = todo[:PER_CYCLE_CAP]
        log(f"cycle: {len(todo)} candidates pending, taking {len(batch)}, "
            f"discovery={state}")
        ok = dead = 0
        if batch:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                futs = [pool.submit(worker, env, BUCKET, row) for row in batch]
                for f in as_completed(futs):
                    row = f.result()
                    append_log_row(row)
                    if row.get("status") == "ok":
                        ok += 1
                    elif row.get("status") not in ("already_in_r2",):
                        dead += 1
            log(f"cycle done: {ok} uploaded, {dead} dead/failed")
            try:
                from download_batch import LOG_PATH as _LOG
                s3.upload_file(str(_LOG), BUCKET,
                               "claude-repo/overnight/download_log.csv")
                log("log snapshot -> R2")
            except Exception as ex:
                log(f"WARN log snapshot: {ex}")
            harvest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "harvest_layered_full.py")
            if os.path.exists(harvest):
                try:
                    subprocess.run([sys.executable, harvest],
                                   timeout=1500, capture_output=True)
                    log("harvest pass complete")
                except Exception as ex:
                    log(f"WARN harvest pass: {ex}")
            idle_cycles = 0
        else:
            idle_cycles += 1
            log(f"idle cycle {idle_cycles}")
            if state not in ("running", "unknown") and idle_cycles >= 2:
                log(f"discovery terminal ({state}) + idle x2 — exiting clean")
                return 0
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
