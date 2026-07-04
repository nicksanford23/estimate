#!/usr/bin/env python3
"""Rung-2c, Task 1: a FROZEN, stable-under-corpus-growth eval permit split.

Context (STATE.md, "Rung-2b results"): the by-permit hash split used by every
prior rung (train_sweep.py / train_sweep_opus.py.split_permits) reshuffles
membership of the *entire current permit list* every time new permits get
labeled -- same seed does NOT mean same train/eval membership as the corpus
grows. That let a single whale permit (26-12298-NEWC, 1059 labeled pages,
~36% of the corpus) land 100%-eval in one run, collapsing finish_recall@0.5
from 0.974 to 0.339 on identical model code. Not a model regression -- a
split-stability bug.

This script builds data/split_v1.json once: a permit-level train/eval
assignment that (a) can never again be dominated by a single huge permit, and
(b) is defined by a PER-PERMIT hash (not a shuffle of the whole list), so
adding newly-labeled permits later never changes any existing permit's side.

Rules (also recorded verbatim in the output JSON's "rules" field):
  1. Any permit with > 300 labeled pages is forced TRAIN. A packet that large
     can never be a fair, representative EVAL packet (rung-2b diagnosis).
  2. Every remaining permit gets sha256(f"{seed}:{permit_num}") hashed to a
     fraction in [0, 1) via its first 8 hex digits; the lowest ~25% of that
     hash space -> EVAL, the rest -> TRAIN.
  3. Floors: eval must have >= 8 permits AND >= 15 finish
     (finish_plan + finish_schedule) pages. If rule 2's cut doesn't clear
     both floors, the next-lowest-hash TRAIN permits that contain >= 1
     finish page are moved into EVAL, in ascending hash order, one at a
     time, until both floors hold (or train permits-with-finish-pages are
     exhausted, which is logged as a warning).
  4. FROZEN: this eval permit list is closed as of generation time. Any
     permit labeled AFTER this file is written is not in either list here;
     downstream code (scripts/rung2c.py) must treat "not in eval" as TRAIN
     by default, so the eval set's membership and size never drift as more
     labels land. Regenerating this file (re-running this script) is the
     only way to change it, and that should be a deliberate, reviewed act,
     not an automatic side effect of labeling more pages.

Truth table: same source-priority resolution as every prior rung (imported
from train_sweep_opus.py, unmodified) -- highest SOURCE_PRIORITY, then latest
created_at, then highest row id.

Usage
    python3 scripts/make_split.py
    python3 scripts/make_split.py --seed 42 --out data/split_v1.json
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_sweep_opus as r1  # noqa: E402  (reuse truth table, unmodified)

SEED = 42
WHALE_MAX_PAGES = 300     # > this many labeled pages -> forced TRAIN
EVAL_HASH_FRAC = 0.25     # lowest ~25% of hash space -> EVAL candidate pool
MIN_EVAL_PERMITS = 8
MIN_EVAL_FINISH_PAGES = 15
VERSION = "v1"


def permit_hash_frac(seed: int, permit: str) -> float:
    """Deterministic per-permit hash fraction in [0, 1). Depends only on
    (seed, permit_num) -- never on the rest of the permit list -- so it is
    stable as the corpus grows (the property train_sweep.py's permit_split
    was designed for, but the by-permit hash needs to be paired with the
    whale rule + floors below to actually be *fair*, not just *stable*)."""
    digest = hashlib.sha256(f"{seed}:{permit}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def build_split(truth: dict, seed: int = SEED) -> dict:
    """truth: {page_id: (category, permit_num)} as returned by
    train_sweep_opus.build_truth_table. Returns the full split dict that
    gets serialized to JSON."""
    pages_by_permit: dict[str, int] = {}
    finish_by_permit: dict[str, int] = {}
    for _pid, (cat, permit) in truth.items():
        pages_by_permit[permit] = pages_by_permit.get(permit, 0) + 1
        if cat in r1.FINISH_CATEGORIES:
            finish_by_permit[permit] = finish_by_permit.get(permit, 0) + 1

    all_permits = sorted(pages_by_permit)

    whales = sorted(p for p in all_permits if pages_by_permit[p] > WHALE_MAX_PAGES)
    whale_set = set(whales)
    candidates = [p for p in all_permits if p not in whale_set]

    # Rule 2: hash-sort candidates ascending, lowest EVAL_HASH_FRAC -> eval.
    hash_of = {p: permit_hash_frac(seed, p) for p in candidates}
    hashed_asc = sorted(candidates, key=lambda p: hash_of[p])
    n_cand = len(hashed_asc)
    n_eval_initial = int(round(EVAL_HASH_FRAC * n_cand))
    eval_set = set(hashed_asc[:n_eval_initial])
    remaining_train_asc = hashed_asc[n_eval_initial:]  # ascending hash order

    def eval_finish_pages() -> int:
        return sum(finish_by_permit.get(p, 0) for p in eval_set)

    # Rule 3: top up with next-lowest-hash TRAIN permits that have finish
    # pages, until both floors hold.
    moved_to_eval = []
    exhausted = False
    while len(eval_set) < MIN_EVAL_PERMITS or eval_finish_pages() < MIN_EVAL_FINISH_PAGES:
        candidate = next(
            (p for p in remaining_train_asc
             if p not in eval_set and finish_by_permit.get(p, 0) > 0),
            None,
        )
        if candidate is None:
            exhausted = True
            print("WARNING: exhausted TRAIN permits with >=1 finish page "
                  "before both eval floors were met -- floors NOT fully "
                  "satisfied; see 'floors_met' in the output JSON.",
                  file=sys.stderr)
            break
        eval_set.add(candidate)
        moved_to_eval.append(candidate)

    eval_permits = sorted(eval_set)
    train_permits = sorted(set(all_permits) - eval_set)
    assert set(eval_permits) & whale_set == set(), "a whale leaked into eval"

    def side_stats(permits):
        pages = sum(pages_by_permit[p] for p in permits)
        finish = sum(finish_by_permit.get(p, 0) for p in permits)
        return {"permits": len(permits), "pages": pages, "finish_pages": finish}

    rules = (
        f"v1: (1) any permit with >{WHALE_MAX_PAGES} labeled pages is forced "
        f"TRAIN (a whale can never be a fair eval packet -- rung-2b "
        f"diagnosis: 26-12298-NEWC, 1059 pages, swinging 100%-eval collapsed "
        f"finish_recall@0.5 from 0.974 to 0.339 on identical model code). "
        f"(2) remaining permits: sha256(f'{{seed}}:{{permit_num}}')[:8] hex "
        f"-> fraction of hash space; lowest {EVAL_HASH_FRAC:.0%} -> EVAL, "
        f"rest -> TRAIN. (3) floors: eval must have >={MIN_EVAL_PERMITS} "
        f"permits and >={MIN_EVAL_FINISH_PAGES} finish_plan+finish_schedule "
        f"pages; if unmet after (2), the next-lowest-hash TRAIN permits that "
        f"contain >=1 finish page are moved into eval (ascending hash order) "
        f"one at a time until both floors hold. "
        f"(4) FROZEN: this eval list is closed as of generation time -- any "
        f"permit labeled AFTER this file was written is NOT in either list "
        f"here, and downstream training code must default any permit not "
        f"found in 'eval' to TRAIN (never grow or re-derive eval from a "
        f"fresh permit list). Regenerating this file is the only way to "
        f"change membership, and must be a deliberate act."
    )

    return {
        "version": VERSION,
        "seed": seed,
        "rules": rules,
        "train": train_permits,
        "eval": eval_permits,
        "stats": {
            "train": side_stats(train_permits),
            "eval": side_stats(eval_permits),
            "total_permits": len(all_permits),
            "total_pages": sum(pages_by_permit.values()),
            "total_finish_pages": sum(finish_by_permit.values()),
            "whales_forced_train": [
                {"permit_num": p, "pages": pages_by_permit[p]} for p in whales
            ],
            "moved_to_eval_to_meet_floors": [
                {"permit_num": p, "pages": pages_by_permit[p],
                 "finish_pages": finish_by_permit.get(p, 0)}
                for p in moved_to_eval
            ],
            "floors_met": (len(eval_set) >= MIN_EVAL_PERMITS
                            and eval_finish_pages() >= MIN_EVAL_FINISH_PAGES),
            "floors_exhausted_without_meeting": exhausted,
        },
    }


def print_stats(split: dict) -> None:
    s = split["stats"]
    print("=" * 78)
    print(f"split_v1 (seed={split['seed']})")
    print("=" * 78)
    print(f"total: {s['total_permits']} permits, {s['total_pages']} labeled "
          f"pages, {s['total_finish_pages']} finish pages")
    print(f"TRAIN: {s['train']['permits']} permits, {s['train']['pages']} "
          f"pages, {s['train']['finish_pages']} finish pages")
    print(f"EVAL : {s['eval']['permits']} permits, {s['eval']['pages']} "
          f"pages, {s['eval']['finish_pages']} finish pages")
    print(f"whales forced TRAIN (>{WHALE_MAX_PAGES} pages): "
          f"{s['whales_forced_train']}")
    print(f"permits moved into eval to meet floors "
          f"(>= {MIN_EVAL_PERMITS} permits, >= {MIN_EVAL_FINISH_PAGES} "
          f"finish pages): {s['moved_to_eval_to_meet_floors']}")
    print(f"floors met: {s['floors_met']} "
          f"(exhausted candidates without meeting: "
          f"{s['floors_exhausted_without_meeting']})")
    print("=" * 78)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "split_v1.json"))
    ap.add_argument("--db-url", default=None, help="override NEON_DATABASE_URL")
    args = ap.parse_args(argv)

    db_url = args.db_url
    if db_url is None:
        env = r1.load_env()
        db_url = env.get("NEON_DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
    if not db_url:
        print("ERROR: NEON_DATABASE_URL not found in .env or --db-url", file=sys.stderr)
        return 2

    print("building truth table from Neon (schema estimate)...", flush=True)
    truth = r1.build_truth_table(db_url)
    print(f"truth: {len(truth)} labeled pages", flush=True)

    split = build_split(truth, seed=args.seed)
    print_stats(split)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(split, f, indent=2)
        f.write("\n")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
