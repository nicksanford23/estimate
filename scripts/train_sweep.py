#!/usr/bin/env python3
"""Model-1 rung-1 training sweep: cached embeddings x heads x label-task.

Pulls the truth table from Neon Postgres (schema `estimate`), loads cached
embeddings from data/embeddings/<tag>_<backbone>.npz, dedups near-identical
pages (revisions/resubmittals of the same permit), splits by PERMIT (never
by page/document), trains {logreg, mlp, xgboost} x {direct-binary-keep,
16-class-then-collapse} for each backbone, evaluates with the flooring-takeoff
benchmark (must-not-miss finish pages, tolerate false positives), appends one
row per experiment to data/experiments.csv, and prints a ranked leaderboard.

Does not touch page_label.keep (legacy column) -- keep is DERIVED here from
category, per PLAN.md ("Everything else ... is DERIVED in code, never
hand-labeled").

Usage:
    python3 scripts/train_sweep.py
    python3 scripts/train_sweep.py --tag base2 --backbones clip_vitl14
    python3 scripts/train_sweep.py --heads logreg --tasks binary_direct

Requires: numpy, scikit-learn, xgboost, psycopg2 (pip install if missing).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import math
import os
import pathlib
import sys
import warnings

import numpy as np
import psycopg2

ROOT = pathlib.Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# Taxonomy / benchmark constants (PLAN.md, CLAUDE.md)
# --------------------------------------------------------------------------
FINISH_CATEGORIES = {"finish_plan", "finish_schedule"}          # must-not-miss
FLOOR_DEMO_CATEGORIES = {"floor_plan", "demo_plan"}              # >=95% recall target
KEEP_CATEGORIES = FINISH_CATEGORIES | FLOOR_DEMO_CATEGORIES      # keep = 1

# Priority for "latest label per page" (PLAN.md tiers; pilot rows count as
# claude-code). Unknown/future sources fall back to priority 0 (lowest) with
# a warning, rather than crashing the sweep.
SOURCE_PRIORITY = {
    "human": 4,
    "claude-code-adjudicate": 3,
    "claude-code-review": 2,
    "claude-code": 1,
    "claude-code-pilot": 1,
}

BACKBONES_DEFAULT = ["clip_vitl14", "siglip_b16", "dinov2_vitb14"]
HEADS_DEFAULT = ["logreg", "mlp", "xgboost"]
TASKS_DEFAULT = ["binary_direct", "class16_collapse"]

CSV_FIELDS = [
    "timestamp", "tag", "backbone", "head", "task", "n_train", "n_eval",
    "finish_recall", "keep_recall", "fp_rate", "threshold_for_full_finish_recall",
    "notes",
]


# --------------------------------------------------------------------------
# DB / truth table
# --------------------------------------------------------------------------
def load_db_url(args: argparse.Namespace) -> str:
    if args.db_url:
        return args.db_url
    if os.environ.get("NEON_DATABASE_URL"):
        return os.environ["NEON_DATABASE_URL"]
    env_path = pathlib.Path(args.env_file)
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k == "NEON_DATABASE_URL":
                    return v
    raise SystemExit(
        f"NEON_DATABASE_URL not found in environment or {env_path}. "
        "Set it in .env or pass --db-url."
    )


TRUTH_SQL = """
WITH prioritized AS (
    SELECT
        pl.id, pl.page_id, pl.source, pl.category, pl.created_at,
        COALESCE(
            CASE pl.source
                WHEN 'human' THEN 4
                WHEN 'claude-code-adjudicate' THEN 3
                WHEN 'claude-code-review' THEN 2
                WHEN 'claude-code' THEN 1
                WHEN 'claude-code-pilot' THEN 1
            END, 0
        ) AS src_priority
    FROM estimate.page_label pl
),
ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY page_id
            ORDER BY src_priority DESC, created_at DESC, id DESC
        ) AS rn
    FROM prioritized
)
SELECT r.page_id, r.category, r.source, p.document_id, d.permit_num
FROM ranked r
JOIN estimate.page p ON p.id = r.page_id
JOIN estimate.document d ON d.id = p.document_id
WHERE r.rn = 1
ORDER BY r.page_id;
"""


def fetch_truth_table(db_url: str) -> list[dict]:
    """One row per labeled page: page_id, category, permit_num (keep derived)."""
    conn = psycopg2.connect(db_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        # Warn (don't crash) about label sources we don't have a priority for.
        cur.execute("SELECT DISTINCT source FROM estimate.page_label")
        seen_sources = {r[0] for r in cur.fetchall()}
        unknown = seen_sources - set(SOURCE_PRIORITY)
        if unknown:
            print(f"WARNING: unrecognized page_label.source values (treated as "
                  f"lowest priority): {sorted(unknown)}", file=sys.stderr)

        cur.execute(TRUTH_SQL)
        rows = cur.fetchall()
    finally:
        conn.close()

    truth = []
    for page_id, category, source, document_id, permit_num in rows:
        truth.append({
            "page_id": int(page_id),
            "category": category,
            "keep": 1 if category in KEEP_CATEGORIES else 0,
            "source": source,
            "document_id": int(document_id),
            "permit_num": permit_num,
        })
    return truth


# --------------------------------------------------------------------------
# Permit split (by permit, never by page/document; stable under new labels)
# --------------------------------------------------------------------------
def permit_split(permits: set[str], seed: int, eval_frac: float) -> tuple[set[str], set[str]]:
    """Deterministic hash-based split, ~eval_frac to eval.

    A per-permit hash (not a shuffle of the whole list) so that adding more
    labeled permits in a later sweep never reassigns an existing permit's
    side -- important for the "label batch -> retrain sweep -> repeat" loop
    in PLAN.md, where a naive shuffle-based split would drift every run.
    """
    train, ev = set(), set()
    for p in sorted(permits):
        digest = hashlib.sha256(f"{seed}:{p}".encode()).hexdigest()
        frac = int(digest[:8], 16) / 0xFFFFFFFF
        (ev if frac < eval_frac else train).add(p)
    return train, ev


# --------------------------------------------------------------------------
# Embeddings
# --------------------------------------------------------------------------
def load_embeddings(tag: str, backbone: str, emb_dir: pathlib.Path) -> tuple[np.ndarray, np.ndarray]:
    path = emb_dir / f"{tag}_{backbone}.npz"
    if not path.exists():
        raise FileNotFoundError(
            f"embeddings file not found: {path}\n"
            f"  Expected output of scripts/embed_gpu.py {tag} (backbone={backbone}).\n"
            f"  Run that first, or pass --backbones to select only backbones "
            f"you already have, or --tag to point at a different run."
        )
    data = np.load(path)
    if "emb" not in data or "page_id" not in data:
        raise ValueError(f"{path} is missing 'emb' or 'page_id' array "
                          f"(found: {list(data.keys())})")
    emb = data["emb"].astype(np.float32)
    # embed_remote.sh writes page_id from a CSV column, so it may be stored
    # as unicode strings even though it's numeric -- coerce to int64.
    page_id = np.array([int(x) for x in data["page_id"]], dtype=np.int64)
    if emb.shape[0] != page_id.shape[0]:
        raise ValueError(f"{path}: emb has {emb.shape[0]} rows but page_id "
                          f"has {page_id.shape[0]}")
    return page_id, emb


# --------------------------------------------------------------------------
# Dedup: cosine similarity > threshold to an earlier page (by page_id, our
# best available proxy for "earlier" -- pages are inserted in render order).
# --------------------------------------------------------------------------
def dedup_groups(page_ids: np.ndarray, emb: np.ndarray, threshold: float,
                  block: int = 1024) -> dict[int, int]:
    """Returns {page_id: representative_page_id} for every input page_id.

    A page is its own representative unless it is >threshold cosine-similar
    to an earlier (smaller page_id) page, in which case it maps to that
    group's earliest member (union-find over pairwise similarity, computed
    in blocks so memory stays O(block * n) instead of O(n^2) all at once).
    """
    order = np.argsort(page_ids)
    ids_sorted = page_ids[order]
    n = len(ids_sorted)
    if n == 0:
        return {}
    norms = np.linalg.norm(emb[order], axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = (emb[order] / norms).astype(np.float32)

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            # Smaller index == smaller page_id == "earlier" stays root.
            if ra > rb:
                ra, rb = rb, ra
            parent[rb] = ra

    for i0 in range(0, n, block):
        i1 = min(i0 + block, n)
        sims = unit[i0:i1] @ unit.T  # (i1-i0, n)
        for local_i, global_i in enumerate(range(i0, i1)):
            # Only compare against later pages to avoid double work; earlier
            # pages (< global_i) were already handled when they were the row.
            tail = sims[local_i, global_i + 1:]
            hits = np.nonzero(tail > threshold)[0] + global_i + 1
            for j in hits:
                union(global_i, j)

    rep_page_id = {}
    for local_idx in range(n):
        root = find(local_idx)
        rep_page_id[int(ids_sorted[local_idx])] = int(ids_sorted[root])
    return rep_page_id


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
def get_model(head: str, is_multiclass: bool):
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    if head == "logreg":
        return Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=3000, class_weight="balanced",
                                        random_state=42)),
        ])
    if head == "mlp":
        # sklearn's MLPClassifier has no class_weight/sample_weight support,
        # so this head does not get balanced-class reweighting like the
        # other two (see final report / design decisions).
        return Pipeline([
            ("scale", StandardScaler()),
            ("clf", MLPClassifier(hidden_layer_sizes=(256,), activation="relu",
                                   early_stopping=True, max_iter=300,
                                   random_state=42)),
        ])
    if head == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.1,
            subsample=0.9, colsample_bytree=0.9, random_state=42,
            n_jobs=-1, tree_method="hist",
            eval_metric="mlogloss" if is_multiclass else "logloss",
        )
    raise ValueError(f"unknown head: {head}")


def fit_and_score(head: str, task: str, X_train: np.ndarray, cat_train: np.ndarray,
                   keep_train: np.ndarray, X_eval: np.ndarray) -> np.ndarray:
    """Fit `head` for `task` on train, return P(keep) per eval row."""
    is_multiclass = task == "class16_collapse"
    y_train = cat_train if is_multiclass else keep_train
    model = get_model(head, is_multiclass)

    label_enc = None
    if head == "xgboost":
        from sklearn.utils.class_weight import compute_sample_weight
        sw = compute_sample_weight("balanced", y_train)
        if is_multiclass:  # xgboost requires integer-encoded class labels
            from sklearn.preprocessing import LabelEncoder
            label_enc = LabelEncoder()
            y_train = label_enc.fit_transform(y_train)
        model.fit(X_train, y_train, sample_weight=sw)
    else:
        model.fit(X_train, y_train)

    classes = np.asarray(model.classes_)
    if label_enc is not None:
        classes = label_enc.inverse_transform(classes.astype(int))
    probs = model.predict_proba(X_eval)

    if is_multiclass:
        keep_idx = [i for i, c in enumerate(classes) if c in KEEP_CATEGORIES]
        if not keep_idx:
            return np.zeros(X_eval.shape[0], dtype=np.float64)
        return probs[:, keep_idx].sum(axis=1)

    if 1 not in classes:  # training fold had only one class -- degenerate
        return np.zeros(X_eval.shape[0], dtype=np.float64)
    return probs[:, list(classes).index(1)]


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def _rate(mask: np.ndarray, pred_keep: np.ndarray) -> float:
    """Fraction of rows in `mask` predicted keep. NaN if mask is empty."""
    if mask.sum() == 0:
        return float("nan")
    return float(pred_keep[mask].mean())


def eval_at_threshold(cat_eval: np.ndarray, keep_eval: np.ndarray,
                       score_eval: np.ndarray, thr: float) -> dict:
    pred = (score_eval >= thr).astype(int)
    return {
        "finish_recall": _rate(np.isin(cat_eval, list(FINISH_CATEGORIES)), pred),
        "floordemo_recall": _rate(np.isin(cat_eval, list(FLOOR_DEMO_CATEGORIES)), pred),
        "keep_recall": _rate(keep_eval == 1, pred),
        "fp_rate": _rate(keep_eval == 0, pred),
        "pred": pred,
    }


def threshold_for_full_finish_recall(cat_eval: np.ndarray, score_eval: np.ndarray) -> float:
    finish_scores = score_eval[np.isin(cat_eval, list(FINISH_CATEGORIES))]
    if finish_scores.size == 0:
        return float("nan")
    return float(finish_scores.min())  # highest threshold that keeps every finish page


def per_packet_summary(permit_eval: np.ndarray, cat_eval: np.ndarray,
                        pred_at_05: np.ndarray) -> dict:
    """Per-packet (=per eval permit) rollup of the must-not-miss metric."""
    n_finish_packets = 0
    n_full_recall_packets = 0
    for permit in np.unique(permit_eval):
        idx = permit_eval == permit
        finish_mask = np.isin(cat_eval[idx], list(FINISH_CATEGORIES))
        if finish_mask.sum() == 0:
            continue
        n_finish_packets += 1
        if pred_at_05[idx][finish_mask].all():
            n_full_recall_packets += 1
    return {
        "n_packets": int(len(np.unique(permit_eval))),
        "n_finish_packets": n_finish_packets,
        "n_full_finish_recall_packets": n_full_recall_packets,
    }


# --------------------------------------------------------------------------
# Experiment plumbing
# --------------------------------------------------------------------------
def append_experiment_row(csv_path: pathlib.Path, row: dict) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            w.writeheader()
        w.writerow(row)


def fmt(x: float, nd: int = 3) -> str:
    return "nan" if x != x else f"{x:.{nd}f}"


def run_backbone(tag: str, backbone: str, args: argparse.Namespace,
                  truth_by_page: dict, train_permits: set, eval_permits: set,
                  results: list) -> None:
    try:
        page_ids_emb, emb = load_embeddings(tag, backbone, pathlib.Path(args.embeddings_dir))
    except FileNotFoundError as e:
        print(f"\n=== {backbone}: SKIPPED ===\n{e}", file=sys.stderr)
        return

    # Join embeddings to truth table.
    pid_to_row = {}
    for pid, vec in zip(page_ids_emb, emb):
        row = truth_by_page.get(int(pid))
        if row is not None:
            pid_to_row[int(pid)] = vec  # last-wins if page_id repeats in npz
    common_ids = np.array(sorted(pid_to_row), dtype=np.int64)
    n_truth = len(truth_by_page)
    n_common = len(common_ids)
    print(f"\n=== {backbone} ===")
    print(f"truth-table labeled pages: {n_truth}; with embedding: {n_common} "
          f"({n_truth - n_common} labeled pages missing an embedding, skipped)")
    if n_common == 0:
        print(f"SKIPPED: no overlap between truth table and {backbone} embeddings.")
        return

    X = np.stack([pid_to_row[pid] for pid in common_ids])
    cat = np.array([truth_by_page[pid]["category"] for pid in common_ids])
    keep = np.array([truth_by_page[pid]["keep"] for pid in common_ids])
    permit = np.array([truth_by_page[pid]["permit_num"] for pid in common_ids])

    rep_of = dedup_groups(common_ids, X, args.dedup_threshold)
    is_rep = np.array([rep_of[pid] == pid for pid in common_ids])
    n_dup_groups = len(set(rep_of.values()))
    n_dup_pages = n_common - n_dup_groups
    print(f"dedup (cosine>{args.dedup_threshold}): {n_dup_groups} groups, "
          f"{n_dup_pages} duplicate pages (kept in train, collapsed to one "
          f"representative for eval)")

    train_mask = np.isin(permit, list(train_permits))
    eval_mask = np.isin(permit, list(eval_permits)) & is_rep
    eval_mask_predup = np.isin(permit, list(eval_permits))
    n_dup_excluded_eval = int(eval_mask_predup.sum() - eval_mask.sum())

    X_train, cat_train, keep_train = X[train_mask], cat[train_mask], keep[train_mask]
    X_eval, cat_eval, keep_eval, permit_eval = (
        X[eval_mask], cat[eval_mask], keep[eval_mask], permit[eval_mask])
    print(f"split: n_train={len(X_train)} ({len(set(permit[train_mask]))} permits), "
          f"n_eval={len(X_eval)} ({len(set(permit_eval))} permits, "
          f"{n_dup_excluded_eval} dup pages excluded from eval)")

    if len(X_train) == 0 or len(X_eval) == 0:
        print("SKIPPED: empty train or eval split for this backbone.")
        return
    if len(np.unique(keep_train)) < 2:
        print("WARNING: training fold has only one keep class -- results will "
              "be degenerate until more labels land.")

    for task in args.tasks:
        for head in args.heads:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                score_eval = fit_and_score(head, task, X_train, cat_train, keep_train, X_eval)

            m05 = eval_at_threshold(cat_eval, keep_eval, score_eval, 0.5)
            thr_full = threshold_for_full_finish_recall(cat_eval, score_eval)
            m_full = (eval_at_threshold(cat_eval, keep_eval, score_eval, thr_full)
                      if thr_full == thr_full else None)
            pp = per_packet_summary(permit_eval, cat_eval, m05["pred"])

            notes = (
                f"floordemo_recall@0.5={fmt(m05['floordemo_recall'])};"
                f"keep_recall@thr_full={fmt(m_full['keep_recall']) if m_full else 'nan'};"
                f"fp_rate@thr_full={fmt(m_full['fp_rate']) if m_full else 'nan'};"
                f"floordemo_recall@thr_full={fmt(m_full['floordemo_recall']) if m_full else 'nan'};"
                f"packets_full_finish_recall={pp['n_full_finish_recall_packets']}/{pp['n_finish_packets']}"
                f" (of {pp['n_packets']} eval permits);"
                f"dup_groups={n_dup_groups};dup_pages_train_kept={n_dup_pages};"
                f"dup_excluded_eval={n_dup_excluded_eval};"
                f"train_permits={len(set(permit[train_mask]))};"
                f"eval_permits={len(set(permit_eval))}"
            )

            row = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tag": tag,
                "backbone": backbone,
                "head": head,
                "task": task,
                "n_train": len(X_train),
                "n_eval": len(X_eval),
                "finish_recall": fmt(m05["finish_recall"]),
                "keep_recall": fmt(m05["keep_recall"]),
                "fp_rate": fmt(m05["fp_rate"]),
                "threshold_for_full_finish_recall": fmt(thr_full, 4),
                "notes": notes,
            }
            append_experiment_row(pathlib.Path(args.out), row)
            print(f"  {head:8s} {task:16s} finish_recall={fmt(m05['finish_recall'])} "
                  f"keep_recall={fmt(m05['keep_recall'])} fp_rate={fmt(m05['fp_rate'])} "
                  f"thr_full_finish={fmt(thr_full, 4)}")

            results.append({
                "backbone": backbone, "head": head, "task": task,
                "finish_recall": m05["finish_recall"], "keep_recall": m05["keep_recall"],
                "fp_rate": m05["fp_rate"], "n_eval": len(X_eval),
            })


def print_leaderboard(results: list) -> None:
    if not results:
        print("\nNo experiments ran -- nothing to rank.")
        return

    def sort_key(r):
        fr = r["finish_recall"]
        fp = r["fp_rate"]
        return (-(fr if fr == fr else -1.0), fp if fp == fp else 1.0)

    ranked = sorted(results, key=sort_key)
    print("\n=== Leaderboard (by finish_recall desc, then fp_rate asc) @ threshold 0.5 ===")
    header = f"{'rank':>4} {'backbone':14} {'head':8} {'task':16} {'finish_recall':>13} {'fp_rate':>8} {'keep_recall':>11} {'n_eval':>7}"
    print(header)
    for i, r in enumerate(ranked, 1):
        print(f"{i:>4} {r['backbone']:14} {r['head']:8} {r['task']:16} "
              f"{fmt(r['finish_recall']):>13} {fmt(r['fp_rate']):>8} "
              f"{fmt(r['keep_recall']):>11} {r['n_eval']:>7}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default="base2",
                    help="embedding run tag (default: base2)")
    ap.add_argument("--backbones", default=",".join(BACKBONES_DEFAULT),
                    help="comma-separated backbone list")
    ap.add_argument("--heads", default=",".join(HEADS_DEFAULT),
                    help="comma-separated head list: logreg,mlp,xgboost")
    ap.add_argument("--tasks", default=",".join(TASKS_DEFAULT),
                    help="comma-separated task list: binary_direct,class16_collapse")
    ap.add_argument("--embeddings-dir", default=str(ROOT / "data" / "embeddings"))
    ap.add_argument("--out", default=str(ROOT / "data" / "experiments.csv"))
    ap.add_argument("--env-file", default=str(ROOT / ".env"))
    ap.add_argument("--db-url", default=None, help="override NEON_DATABASE_URL")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--eval-frac", type=float, default=0.2)
    ap.add_argument("--dedup-threshold", type=float, default=0.98)
    args = ap.parse_args(argv)
    args.backbones = [b.strip() for b in args.backbones.split(",") if b.strip()]
    args.heads = [h.strip() for h in args.heads.split(",") if h.strip()]
    args.tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]

    bad_heads = set(args.heads) - set(HEADS_DEFAULT)
    bad_tasks = set(args.tasks) - set(TASKS_DEFAULT)
    if bad_heads:
        ap.error(f"unknown --heads: {sorted(bad_heads)} (choose from {HEADS_DEFAULT})")
    if bad_tasks:
        ap.error(f"unknown --tasks: {sorted(bad_tasks)} (choose from {TASKS_DEFAULT})")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    db_url = load_db_url(args)

    print(f"Fetching truth table from Neon (schema estimate)...")
    try:
        truth_rows = fetch_truth_table(db_url)
    except psycopg2.OperationalError as e:
        print(f"ERROR: could not connect to Neon: {e}", file=sys.stderr)
        return 1
    if not truth_rows:
        print("ERROR: truth table is empty -- no labeled pages found in "
              "estimate.page_label.", file=sys.stderr)
        return 1

    truth_by_page = {r["page_id"]: r for r in truth_rows}
    all_permits = {r["permit_num"] for r in truth_rows}
    train_permits, eval_permits = permit_split(all_permits, args.seed, args.eval_frac)
    n_keep = sum(r["keep"] for r in truth_rows)
    print(f"truth table: {len(truth_rows)} labeled pages, {len(all_permits)} permits, "
          f"keep-rate={n_keep/len(truth_rows):.1%}")
    print(f"permit split (seed={args.seed}): {len(train_permits)} train / "
          f"{len(eval_permits)} eval ({len(eval_permits)/len(all_permits):.1%} eval)")

    results = []
    for backbone in args.backbones:
        run_backbone(args.tag, backbone, args, truth_by_page, train_permits,
                     eval_permits, results)

    print_leaderboard(results)
    if not results:
        print(f"\nERROR: no backbone produced any experiments. Expected files "
              f"like {args.embeddings_dir}/{args.tag}_<backbone>.npz for "
              f"backbones: {args.backbones}", file=sys.stderr)
        return 1
    print(f"\nAppended {len(results)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
