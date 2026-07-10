#!/usr/bin/env python3
"""Probe 30 step 0 -- build the training roster from eyeball_verdicts.csv.

TRAIN_LAYERED roster = permits with verdict=CONFIRMED in
data/triage/eyeball_verdicts.csv (73 as of 2026-07-10). Sibling floor-plan
pages of the same doc were CONSIDERED (per task spec) but deliberately
EXCLUDED here: layered_plans.csv lists every page-with-a-wall-layer-token
per doc (451 rows across these 73 docs' doc_ids), but the 2026-07-09 audit's
dominant false-pass mode was EXACTLY this -- MEP/RCP/site sheets reusing the
architectural wall xref score as "layered" without being real floor plans.
Only the primary page per permit has an eyeball verdict; admitting
un-eyeballed siblings would silently reintroduce the false-pass contamination
the whole re-gate was built to remove. So: 1 page per permit, 73 pages,
73 unique doc_ids. This is a scope-limiting, documented choice.

If data/triage/train_layered_roster.csv (the sibling re-gate agent's output)
appears, this script's `--reconcile` mode adds any NEWLY CONFIRMED permits
not already in our roster to TRAIN ONLY (never touches an existing holdout).

Firm-diversity holdout: wall-layer-naming "signature" = the set of layer
tokens (tail after an xref '$' separator, upper-cased) that contain
wall|cmu|stud|gyp|stucco|partition|mason (classify_layer's own wall regex),
looked up per (doc_id, page) in layered_plans.csv. 10 held-out permits are
chosen to span as many DISTINCT signatures as possible.
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from probe8_layer_classes import classify_layer  # noqa: E402

VERDICTS_CSV = os.path.join(ROOT, "data", "triage", "eyeball_verdicts.csv")
LAYERED_CSV = os.path.join(ROOT, "data", "triage", "layered_plans.csv")
RECONCILE_CSV = os.path.join(ROOT, "data", "triage", "train_layered_roster.csv")
OUT_CSV = os.path.join(ROOT, "data", "probe30", "roster.csv")

WALL_TOKEN_RE = re.compile(r"wall|cmu|stud|gyp|stucco|partition|mason", re.I)

N_HOLDOUT = 10


def wall_sig(layers_str):
    toks = set((layers_str or "").split("|"))
    wall_toks = [t for t in toks if WALL_TOKEN_RE.search(t)]
    norm = set()
    for t in wall_toks:
        tail = t.split("$")[-1]
        norm.add(tail.upper())
    return tuple(sorted(norm))


def load_confirmed():
    rows = list(csv.DictReader(open(VERDICTS_CSV)))
    return [r for r in rows if r["verdict"] == "CONFIRMED"]


def load_layer_lookup():
    rows = list(csv.DictReader(open(LAYERED_CSV)))
    d = {}
    for r in rows:
        d[(int(r["doc_id"]), int(r["page"]))] = r["layers"]
    return d


def build_roster():
    confirmed = load_confirmed()
    layer_lookup = load_layer_lookup()
    roster = []
    for r in confirmed:
        doc_id, page = int(r["doc_id"]), int(r["page"])
        layers = layer_lookup.get((doc_id, page), "")
        sig = wall_sig(layers)
        roster.append(dict(permit=r["permit"], doc_id=doc_id, page=page,
                            layers=layers, wall_sig="|".join(sig) or "(none-matched)"))
    return roster


def choose_holdout(roster, n=N_HOLDOUT):
    """Greedy max-diversity: repeatedly pick the permit whose signature is
    least represented so far among CHOSEN holdout sigs (ties broken by
    permit id, deterministic)."""
    by_sig = {}
    for row in roster:
        by_sig.setdefault(row["wall_sig"], []).append(row)
    sigs_sorted = sorted(by_sig.keys())  # deterministic order
    chosen = []
    chosen_sigs = set()
    # first pass: one permit per DISTINCT signature, in order, until n reached
    i = 0
    while len(chosen) < n and i < len(sigs_sorted):
        sig = sigs_sorted[i]
        if sig not in chosen_sigs:
            # pick the permit within this sig group with the most segments
            # if available -- here just take the first (alphabetical permit)
            candidates = sorted(by_sig[sig], key=lambda r: r["permit"])
            chosen.append(candidates[0])
            chosen_sigs.add(sig)
        i += 1
    return chosen


def main():
    roster = build_roster()
    holdout_rows = choose_holdout(roster)
    holdout_permits = {r["permit"] for r in holdout_rows}

    for row in roster:
        row["split"] = "holdout" if row["permit"] in holdout_permits else "train"

    reconciled = []
    if os.path.exists(RECONCILE_CSV) and "--reconcile" in sys.argv:
        extra = list(csv.DictReader(open(RECONCILE_CSV)))
        existing_permits = {r["permit"] for r in roster}
        layer_lookup = load_layer_lookup()
        for r in extra:
            if r.get("verdict", "CONFIRMED") != "CONFIRMED":
                continue
            if r["permit"] in existing_permits:
                continue
            doc_id, page = int(r["doc_id"]), int(r["page"])
            layers = layer_lookup.get((doc_id, page), "")
            sig = wall_sig(layers)
            reconciled.append(dict(permit=r["permit"], doc_id=doc_id, page=page,
                                    layers=layers, wall_sig="|".join(sig) or "(none-matched)",
                                    split="train"))  # NEVER contaminate holdout mid-run
        roster.extend(reconciled)

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["permit", "doc_id", "page", "layers", "wall_sig", "split"])
        w.writeheader()
        for row in roster:
            w.writerow(row)

    print(f"roster: {len(roster)} permits/pages -> {OUT_CSV}")
    print(f"  train: {sum(1 for r in roster if r['split']=='train')}")
    print(f"  holdout: {sum(1 for r in roster if r['split']=='holdout')}")
    if reconciled:
        print(f"  reconciled in (TRAIN only): {len(reconciled)}")
    print("\nHOLDOUT LIST (permit, doc_id, page, wall_sig):")
    for r in holdout_rows:
        print(f"  {r['permit']:20s} doc={r['doc_id']:>9} page={r['page']:>3}  sig={r['wall_sig']}")


if __name__ == "__main__":
    main()
