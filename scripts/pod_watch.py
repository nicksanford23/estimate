#!/usr/bin/env python3
"""Pod watchdog — every 10 min, log whether the rented pods are RUNNING and
PRODUCING (output freshness), so idle-billing or silent stalls get caught.
Lesson from 2026-07-09: "pod created" != "pod working".

Checks:
  * RunPod API: which pods exist, status, $/hr.
  * audit pod liveness: claude-repo/audit_out/*.csv LastModified age.
  * discovery liveness: estimate.discovered_docs max(discovered_at) age +
    count (should grow between checks except during ~50min throttle naps).
  * local scans: layered_plans.csv / closeability_full.csv row counts.

Log: data/triage/pod_watch.log (append-only, one line per check per subject).
WARN lines when: a pod bills >$0.30/hr total unexpectedly, audit output stale
>30 min while pod RUNNING, discovery stale >150 min (three nap cycles).
Run detached:  setsid nohup python3 scripts/pod_watch.py >/dev/null 2>&1 &
"""
import os, sys, time, json, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
LOG = os.path.join(ROOT, "data", "triage", "pod_watch.log")
INTERVAL = 600


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"{ts} {msg}\n")


def check_once(E):
    # pods
    try:
        req = urllib.request.Request("https://rest.runpod.io/v1/pods",
            headers={"Authorization": f"Bearer {E['RUNPOD_API_KEY']}"})
        pods = json.load(urllib.request.urlopen(req, timeout=30))
        total = sum(float(p.get("costPerHr") or 0) for p in pods)
        names = ", ".join(f"{p['name']}={p.get('desiredStatus')}(${p.get('costPerHr')}/hr)" for p in pods) or "none"
        log(f"pods: {names} total=${total:.2f}/hr")
        if total > 0.35:
            log(f"WARN pods billing ${total:.2f}/hr — expected <=0.30; check for strays")
    except Exception as ex:
        log(f"WARN pods api error: {type(ex).__name__} {str(ex)[:80]}"); pods = []

    # audit pod output freshness
    try:
        from probe2_sf import r2_client
        r = r2_client().list_objects_v2(Bucket="nola-permit-docs", Prefix="claude-repo/audit_out/")
        newest = max((o["LastModified"] for o in r.get("Contents", [])), default=None)
        if newest:
            age = (datetime.now(timezone.utc) - newest).total_seconds() / 60
            log(f"audit_out newest={age:.0f}min ago ({r.get('KeyCount',0)} keys)")
            if age > 30 and any(p["name"] == "audit-sweep" for p in pods):
                log("WARN audit pod RUNNING but output stale >30min — likely stalled or done; verify/terminate")
    except Exception as ex:
        log(f"WARN audit_out check error: {str(ex)[:80]}")

    # discovery freshness
    try:
        import psycopg2
        cur = psycopg2.connect(E["NEON_DATABASE_URL"]).cursor()
        cur.execute("SELECT count(DISTINCT permit_num), count(*), max(discovered_at) FROM estimate.discovered_docs")
        p, d, ts = cur.fetchone()
        age = (datetime.now(timezone.utc) - ts).total_seconds() / 60 if ts else 9999
        log(f"discovery: permits={p} docs={d} last_write={age:.0f}min ago")
        if age > 150:
            log("WARN discovery stale >150min (three nap cycles) — check estimate.discovery_runs / pod")
    except Exception as ex:
        log(f"WARN discovery check error: {str(ex)[:80]}")

    # local scan progress
    for name in ("layered_plans.csv", "closeability_full.csv"):
        try:
            n = sum(1 for _ in open(os.path.join(ROOT, "data", "triage", name)))
            log(f"local {name}: {n} rows")
        except Exception:
            pass


def main():
    E = env()
    log("=== pod_watch start ===")
    while True:
        check_once(E)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
