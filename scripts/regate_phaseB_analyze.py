#!/usr/bin/env python3
"""Analyze Phase B results: for each permit in data/triage/_phaseB_permits.txt,
find its best gate-passing page across ALL its scored candidates (original
top-8 rows with regate_phaseA's recomputed bad_title where available, plus
the newly-scored widened rows which carry patched bad_title natively).
Emits data/triage/_regate_phaseB_render.csv (permit,doc_id,page,fpp) for the
render + eyeball pass, and prints a summary.

bad_title source of truth per row:
- if (doc,page) appears in regate_phaseA.csv -> use new_bad_title (patched)
- else (new Phase-B row) -> closeability_full.csv bad_title is already
  patched (scored by the updated scan_closeability_full.py)
Rows predating the patch that were NOT recomputed (i.e. not part of any
FALSE_PASS permit's candidate set) can't appear here because the permit list
IS the FALSE_PASS set.
"""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import ROOT

PERMITS_F = os.path.join(ROOT, "data", "triage", "_phaseB_permits.txt")
CLOSE = os.path.join(ROOT, "data", "triage", "closeability_full.csv")
PHASEA = os.path.join(ROOT, "data", "triage", "regate_phaseA.csv")
OUT = os.path.join(ROOT, "data", "triage", "_regate_phaseB_render.csv")
GATE = dict(n_mid=8, cov_mid=0.2, largest_frac=0.7)


def fnum(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def main():
    permits = set(l.strip() for l in open(PERMITS_F) if l.strip())

    # patched bad_title for the original candidate rows
    patched = {}
    for r in csv.DictReader(open(PHASEA)):
        if r["new_bad_title"] in ("True", "False"):
            patched[(r["permit"], r["doc_id"], r["page"])] = r["new_bad_title"]

    by_key = {}
    for r in csv.DictReader(open(CLOSE)):
        if r["permit"] not in permits:
            continue
        k = (r["permit"], r["doc_id"], r["page"])
        note = r.get("note") or ""
        bad = note.startswith(("crash:", "dl_err", "score_err", "skip_too_big"))
        if k in by_key:
            prev_bad = (by_key[k].get("note") or "").startswith(
                ("crash:", "dl_err", "score_err", "skip_too_big"))
            if bad and not prev_bad:
                continue
        by_key[k] = r

    by_permit = defaultdict(list)
    for k, r in by_key.items():
        note = r.get("note") or ""
        if note.startswith(("crash:", "dl_err", "score_err", "skip_too_big")):
            continue
        bt = patched.get(k, r["bad_title"])
        by_permit[r["permit"]].append(dict(r, bad_title_eff=bt))

    render_rows = []
    none_found = []
    for permit in sorted(permits):
        rows = by_permit.get(permit, [])
        cands = [r for r in rows if r["rep_flag"] == "False"
                 and r["bad_title_eff"] == "False"
                 and fnum(r["n_mid"]) >= GATE["n_mid"]
                 and fnum(r["cov_mid"]) >= GATE["cov_mid"]
                 and fnum(r["largest_frac"]) <= GATE["largest_frac"]]
        if not cands:
            none_found.append(permit)
            continue
        best = max(cands, key=lambda r: (fnum(r["n_mid"]), fnum(r["cov_mid"])))
        render_rows.append(dict(permit=permit, doc_id=best["doc_id"],
                                page=best["page"], fpp=best["best_fpp"],
                                n_mid=best["n_mid"], cov_mid=best["cov_mid"],
                                largest_frac=best["largest_frac"]))

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["permit", "doc_id", "page", "fpp"])
        w.writeheader()
        for r in render_rows:
            w.writerow({k: r[k] for k in ("permit", "doc_id", "page", "fpp")})

    print(f"{len(permits)} phase-B permits: {len(render_rows)} have a new "
          f"gate-passing page (render+eyeball queue -> {OUT}); "
          f"{len(none_found)} have none (settled FALSE_PASS).")
    for r in render_rows:
        print(f"  {r['permit']}  d{r['doc_id']} p{r['page']} "
              f"mid={r['n_mid']} cov_mid={r['cov_mid']} largest={r['largest_frac']}")


if __name__ == "__main__":
    main()
