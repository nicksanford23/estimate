#!/usr/bin/env python3
"""RunPod-side unattended supervisor for the One Stop discovery sweep.

Runs discover_docs.py in passes at the polite pace (--req-interval 5.0),
auto-resumes after circuit-breaker trips with a 50-minute cooldown, mirrors
every result into Neon (estimate.discovered_docs, INSERT ... ON CONFLICT DO
NOTHING) so progress is durable off-box, and TERMINATES ITS OWN POD via the
RunPod REST API when the queue drains or on a 3-strike stop. Terminal state is
recorded in estimate.discovery_runs so the outcome is visible from any box.

Layout on the pod (all under /app):
  discover_docs.py  proxies.txt  discover_targets.csv  discovered_docs.csv
Env required: NEON_DATABASE_URL, RUNPOD_API_KEY; RUNPOD_POD_ID is injected
by RunPod itself.

One Stop empirically allows bursts of ~90-180 permits per proxy-pool warmup
before throttling everyone (seen at both 1.5s and 5.0s per-proxy intervals) —
so trips are EXPECTED steady-state, and a trip after >=50 new permits resets
the strike counter. Three consecutive low-progress trips = they changed
something; stop for good rather than burn the endpoint.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

APP = Path("/app")
CSV_PATH = APP / "discovered_docs.csv"
TARGETS = APP / "discover_targets.csv"
RUN_LOG = APP / "run.log"

REQ_INTERVAL = "5.0"
COOLDOWN_S = 3000          # 50 min after a breaker trip
STRIKE_RESET_GAIN = 50     # a trip after >=50 new permits is throttle, not a block
MAX_STRIKES = 3
SYNC_EVERY_S = 60

import psycopg2  # noqa: E402  (installed by bootstrap)


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {msg}", flush=True)


def db():
    conn = psycopg2.connect(os.environ["NEON_DATABASE_URL"])
    conn.autocommit = True
    return conn


def ensure_tables(cur) -> None:
    cur.execute("""CREATE TABLE IF NOT EXISTS estimate.discovered_docs (
        permit_num text NOT NULL, doc_id bigint NOT NULL, filename text,
        status text, discovered_at timestamptz DEFAULT now(),
        PRIMARY KEY (permit_num, doc_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS estimate.discovery_runs (
        run_id bigserial PRIMARY KEY, pod_id text,
        started_at timestamptz DEFAULT now(), ended_at timestamptz,
        final_state text, settled integer, docs integer, note text)""")


def read_results(include_errors: bool = False):
    """Latest row per permit from the CSV -> list of Neon rows."""
    if not CSV_PATH.exists():
        return [], 0, 0
    latest = {}
    for r in csv.DictReader(CSV_PATH.open()):
        latest[r["permitNum"]] = r
    rows, settled, docs = [], 0, 0
    for pn, r in latest.items():
        st = r["status"]
        if st in ("ok", "not_found"):
            settled += 1
        if st == "ok":
            pairs = [p for p in (r["docPairs"] or "").split(";") if p]
            docs += len(pairs)
            if pairs:
                for p in pairs:
                    did, _, fn = p.partition("|")
                    if did.strip().isdigit():
                        rows.append((pn, int(did), fn, "ok"))
            else:
                rows.append((pn, 0, "", "ok_empty"))
        elif st == "not_found":
            rows.append((pn, 0, "", "not_found"))
        elif include_errors and st == "error":
            rows.append((pn, 0, "", "error"))
    return rows, settled, docs


def sync_to_neon(include_errors: bool = False) -> tuple[int, int]:
    rows, settled, docs = read_results(include_errors)
    if rows:
        conn = db()
        try:
            cur = conn.cursor()
            args = b",".join(
                cur.mogrify("(%s,%s,%s,%s)", row) for row in rows
            ).decode()
            cur.execute(
                "INSERT INTO estimate.discovered_docs "
                "(permit_num, doc_id, filename, status) VALUES "
                + args + " ON CONFLICT (permit_num, doc_id) DO NOTHING"
            )
        finally:
            conn.close()
    return settled, docs


def syncer(stop: threading.Event) -> None:
    while not stop.wait(SYNC_EVERY_S):
        try:
            settled, docs = sync_to_neon()
            log(f"neon sync: settled={settled} docs={docs}")
        except Exception as exc:  # noqa: BLE001 — Neon hiccup must not kill the crawl
            log(f"neon sync FAILED (will retry): {type(exc).__name__}: {exc}")


def settled_count() -> int:
    _, settled, _ = read_results()
    return settled


def targets_count() -> int:
    return max(sum(1 for _ in TARGETS.open()) - 1, 0)


def finish_run(run_id: int, state: str, note: str) -> None:
    try:
        settled, docs = sync_to_neon(include_errors=True)
    except Exception as exc:  # noqa: BLE001
        settled, docs = -1, -1
        note += f" | final sync failed: {exc}"
    try:
        conn = db()
        conn.cursor().execute(
            "UPDATE estimate.discovery_runs SET ended_at=now(), final_state=%s,"
            " settled=%s, docs=%s, note=%s WHERE run_id=%s",
            (state, settled, docs, note[:500], run_id))
        conn.close()
    except Exception as exc:  # noqa: BLE001
        log(f"could not record terminal state: {exc}")
    log(f"terminal: {state} settled={settled} docs={docs} note={note}")


def self_terminate() -> None:
    pod_id = os.environ.get("RUNPOD_POD_ID", "")
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not pod_id or not key:
        log("no RUNPOD_POD_ID/RUNPOD_API_KEY — cannot self-terminate")
        return
    req = urllib.request.Request(
        f"https://rest.runpod.io/v1/pods/{pod_id}", method="DELETE",
        headers={"Authorization": f"Bearer {key}"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                log(f"self-terminate: HTTP {resp.getcode()}")
                return
        except Exception as exc:  # noqa: BLE001
            log(f"self-terminate attempt {attempt+1} failed: {exc}")
            time.sleep(30)


def main() -> None:
    conn = db()
    cur = conn.cursor()
    ensure_tables(cur)
    cur.execute(
        "INSERT INTO estimate.discovery_runs (pod_id, final_state, note) "
        "VALUES (%s, 'running', %s) RETURNING run_id",
        (os.environ.get("RUNPOD_POD_ID", "?"),
         f"req_interval={REQ_INTERVAL} cooldown={COOLDOWN_S}s"))
    run_id = cur.fetchone()[0]
    conn.close()
    log(f"discovery_runs row {run_id}; baseline sync...")
    sync_to_neon()

    stop = threading.Event()
    threading.Thread(target=syncer, args=(stop,), daemon=True).start()

    total = targets_count()
    strikes = stalls = 0
    state, note = "crashed", ""
    try:
        while True:
            before = settled_count()
            with RUN_LOG.open("a") as lf:
                subprocess.run(
                    [sys.executable, "-u", str(APP / "discover_docs.py"),
                     "--targets", str(TARGETS), "--proxies", str(APP / "proxies.txt"),
                     "--out", str(CSV_PATH), "--req-interval", REQ_INTERVAL],
                    stdout=lf, stderr=subprocess.STDOUT, cwd=str(APP))
            after = settled_count()
            gained = after - before
            tail = "".join(RUN_LOG.open().readlines()[-6:])

            if "CIRCUIT-BREAKER" in tail:
                strikes = 0 if gained >= STRIKE_RESET_GAIN else strikes + 1
                if strikes >= MAX_STRIKES:
                    state, note = "three_strike_stop", \
                        f"3 consecutive low-progress trips; settled {after}/{total}"
                    return
                log(f"breaker trip (strike {strikes}/{MAX_STRIKES}, gained {gained},"
                    f" settled {after}/{total}) — cooling {COOLDOWN_S}s")
                time.sleep(COOLDOWN_S)
                continue

            if after >= total:
                state, note = "complete", f"all {total} targets settled"
                return
            if gained == 0:
                stalls += 1
                if stalls >= 2:
                    state, note = "complete_with_errors", \
                        f"{total - after} permits unreachable after repeat passes"
                    return
            else:
                stalls = 0
            log(f"pass ended (gained {gained}, settled {after}/{total}) — resuming in 120s")
            time.sleep(120)
    except Exception as exc:  # noqa: BLE001
        state, note = "crashed", f"{type(exc).__name__}: {exc}"
        raise
    finally:
        stop.set()
        finish_run(run_id, state, note)
        self_terminate()


if __name__ == "__main__":
    main()
