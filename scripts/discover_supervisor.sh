#!/usr/bin/env bash
# Unattended full-sweep supervisor for discover_docs.py.
#
# Runs the whole targets file (no --limit) at the polite pace, auto-resumes
# after circuit-breaker trips with a 50-minute cooldown, and stops for good
# after 3 consecutive low-progress trips (that would mean One Stop changed
# something on their side, not transient throttling). Progress stamps land in
# data/triage/discovery_progress.log every ~500 settled permits so status can
# be checked without touching the process.
#
# Launch:  setsid nohup bash scripts/discover_supervisor.sh \
#            >> data/discover_supervisor.log 2>&1 &
set -u
ROOT=/workspaces/estimate
LOG="$ROOT/data/discover_run.log"
PROG="$ROOT/data/triage/discovery_progress.log"
COOLDOWN_S=3000          # 50 min between resume attempts after a trip
STRIKE_RESET_GAIN=100    # a trip after >=100 new permits is throttle, not a block
mkdir -p "$ROOT/data/triage"

stats_line() {  # prints: settled=N/TOTAL ok=N nf=N err_latest=N docs=N
  python3 - <<'PY'
import csv
from pathlib import Path
root = Path('/workspaces/estimate')
targets = sum(1 for _ in open(root/'data/discover_targets.csv')) - 1
latest = {}
p = root/'data/discovered_docs.csv'
docs = ok = nf = 0
if p.exists():
    for r in csv.DictReader(p.open()):
        latest[r['permitNum']] = r['status']
        if r['status'] == 'ok':
            docs += int(r.get('docCount') or 0)
    ok = sum(1 for s in latest.values() if s == 'ok')
    nf = sum(1 for s in latest.values() if s == 'not_found')
err = sum(1 for s in latest.values() if s == 'error')
print(f"settled={ok+nf}/{targets} ok={ok} nf={nf} err_latest={err} docs={docs}")
PY
}

settled_count() { stats_line | sed -E 's/settled=([0-9]+).*/\1/'; }
remaining_count() { stats_line | sed -E 's/settled=([0-9]+)\/([0-9]+).*/\2-\1/' | bc; }

stamp() { echo "$(date -u +%FT%TZ) $* $(stats_line)" >> "$PROG"; }

# --- background stamper: one line per ~500 settled permits -------------------
(
  last_bucket=$(( $(settled_count) / 500 ))
  while true; do
    sleep 60
    n=$(settled_count)
    bucket=$(( n / 500 ))
    if [ "$bucket" -ne "$last_bucket" ]; then
      stamp "checkpoint"
      last_bucket=$bucket
    fi
  done
) &
STAMP_PID=$!
trap 'kill "$STAMP_PID" 2>/dev/null' EXIT

stamp "supervisor start (req-interval=5.0, full targets)"
strikes=0
stalls=0
while true; do
  before=$(settled_count)
  python3 -u "$ROOT/scripts/discover_docs.py" \
    --proxies "$ROOT/data/proxies.txt" --req-interval 5.0 >> "$LOG" 2>&1
  after=$(settled_count)
  gained=$(( after - before ))

  if tail -n 6 "$LOG" | grep -q "CIRCUIT-BREAKER"; then
    if [ "$gained" -ge "$STRIKE_RESET_GAIN" ]; then strikes=0; else strikes=$(( strikes + 1 )); fi
    if [ "$strikes" -ge 3 ]; then
      stamp "THREE-STRIKE STOP: 3 consecutive low-progress breaker trips — halting for good"
      exit 2
    fi
    stamp "breaker trip (strike $strikes/3, gained $gained) — cooling ${COOLDOWN_S}s"
    sleep "$COOLDOWN_S"
    continue
  fi

  remaining=$(remaining_count)
  if [ "$remaining" -le 0 ]; then
    stamp "COMPLETE: all targets settled"
    exit 0
  fi
  # No breaker but permits remain: either the run drained its queue leaving
  # only hard-error rows (retried each pass), or it crashed. Two zero-gain
  # passes in a row means the remainder is permanently erroring — stop.
  if [ "$gained" -eq 0 ]; then
    stalls=$(( stalls + 1 ))
    if [ "$stalls" -ge 2 ]; then
      stamp "COMPLETE-WITH-ERRORS: $remaining permits unreachable after repeat passes"
      exit 0
    fi
  else
    stalls=0
  fi
  stamp "pass ended (gained $gained, $remaining remain) — resuming in 120s"
  sleep 120
done
