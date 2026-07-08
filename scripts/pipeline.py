#!/usr/bin/env python3
"""Permit worklist + status board — the front end for the triage/takeoff flow.

Starts from RAW permit data (estimate.permits, read-only), filters/ranks what to
work next, and tracks per-permit status so there's always a clear board of what's
DONE (like the bank) vs todo. Status is OUR data: append-only JSONL at
data/triage/permit_status.jsonl (latest record per permit wins), never the shared
tables.

Commands:
  python3 pipeline.py board                 # show all permits by status
  python3 pipeline.py worklist [--code NEWC] [--n 20]   # ranked TODO from raw permits
  python3 pipeline.py mark PERMIT STATUS [--tier T] [--note "..."]
        STATUS = todo | in_progress | done | dismissed
"""
import os, re, sys, json, argparse
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import ROOT

STATUS_FILE = os.path.join(ROOT, "data", "triage", "permit_status.jsonl")
os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
VALID = {"todo", "in_progress", "done", "dismissed"}
BUILDING_RE = re.compile(r"bank|retail|restaurant|medical|dental|office|warehouse|"
                         r"school|hotel|church|store|clinic|gym|salon|tenant|build-?out|"
                         r"interior|renovation", re.I)


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def cur():
    import psycopg2, psycopg2.extras
    return psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def load_status():
    """Latest record per permit."""
    out = {}
    if os.path.exists(STATUS_FILE):
        for line in open(STATUS_FILE):
            line = line.strip()
            if line:
                r = json.loads(line); out[r["permit"]] = r
    return out


def mark(permit, status, tier=None, note=None):
    assert status in VALID, f"status must be one of {VALID}"
    rec = dict(permit=permit, status=status, tier=tier, note=note,
               updated_at=datetime.now().strftime("%Y-%m-%dT%H-%M-%SZ"))
    with open(STATUS_FILE, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"marked {permit} -> {status}" + (f" ({tier})" if tier else ""))


def board():
    st = load_status()
    by = {"done": [], "in_progress": [], "todo": [], "dismissed": []}
    for p, r in st.items():
        by.setdefault(r["status"], []).append(r)
    print("===== PERMIT STATUS BOARD =====")
    for s in ("done", "in_progress", "todo", "dismissed"):
        rows = by.get(s, [])
        print(f"\n## {s.upper()}  ({len(rows)})")
        for r in sorted(rows, key=lambda x: x["permit"]):
            print(f"  {r['permit']:<16} {r.get('tier') or '':<15} {r.get('note') or ''}")
    if not st:
        print("  (empty — nothing tracked yet)")


def worklist(code=None, n=20):
    st = load_status()
    seen = set(st)   # skip anything already tracked (done/todo/etc.)
    c = cur()
    where = "doc_count > 0"
    args = []
    if code:
        where += " AND code = %s"; args.append(code)
    c.execute(f"""SELECT permit_num, code, sqft, cost, description
                  FROM estimate.permits WHERE {where}""", args)
    rows = c.fetchall()
    scored = []
    for r in rows:
        if r["permit_num"] in seen:
            continue
        s = 0
        if r["sqft"] and r["sqft"] > 0: s += 2          # has a total-SF anchor
        if r["code"] == "NEWC": s += 2                   # new construction = richest set
        if r["description"] and BUILDING_RE.search(r["description"]): s += 1
        scored.append((s, r))
    scored.sort(key=lambda x: (-x[0], -(x[1]["sqft"] or 0)))
    print(f"===== WORKLIST (ranked TODO{', code='+code if code else ''}) — top {n} =====")
    print(f"{'score':>5} {'permit':<16}{'code':<6}{'sqft':>8}  description")
    for s, r in scored[:n]:
        print(f"{s:>5} {r['permit_num']:<16}{r['code'] or '':<6}{str(r['sqft'] or ''):>8}  "
              f"{(r['description'] or '')[:60]}")
    print(f"\n{len(scored)} untracked candidates. Mark one in_progress to start it.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("board")
    w = sub.add_parser("worklist"); w.add_argument("--code"); w.add_argument("--n", type=int, default=20)
    m = sub.add_parser("mark"); m.add_argument("permit"); m.add_argument("status")
    m.add_argument("--tier"); m.add_argument("--note")
    a = ap.parse_args()
    if a.cmd == "board": board()
    elif a.cmd == "worklist": worklist(a.code, a.n)
    elif a.cmd == "mark": mark(a.permit, a.status, a.tier, a.note)
    else: ap.print_help()


if __name__ == "__main__":
    main()
