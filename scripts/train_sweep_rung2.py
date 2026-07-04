#!/usr/bin/env python3
"""Model-1 rung-2 sweep: TEXT features (TF-IDF over rendered page text), alone
and concatenated with the rung-1 image embeddings.

Rung 1 (image embeddings only) topped out at finish_recall@0.5 = 0.365
(dinov2 + logreg + multiclass_collapse; see data/experiments_opus.csv). The
diagnosis in STATE.md is that the discriminating signal for
finish_plan/finish_schedule vs. floor_plan/demo_plan lives in the page TEXT
("FINISH SCHEDULE", "LVT-1", room-finish codes), not in a 224px photo of the
sheet. This script tests that directly.

Reuse policy: this file imports (does NOT copy or modify) the truth-table
query, permit split, dedup, and metric functions from train_sweep_opus.py so
rung-2 numbers are directly comparable to rung-1 numbers.

Feature variants
    text_only          : TF-IDF(1-2 grams, lowercase, max_features=30000,
                          min_df=2) fit on TRAIN pages only, transformed on
                          eval. No leakage.
    text_svd+<backbone> : the same TF-IDF, reduced to 256 dims via
                          TruncatedSVD (fit on train only), L2-normalized and
                          concatenated with the L2-normalized image embedding,
                          for each of the 3 base2 backbones.
    text_sparse+<backbone> (logreg only) : raw scipy.sparse.hstack of the
                          TF-IDF matrix and the dense image embedding (also
                          made sparse). No SVD compression -- often the best
                          setup for a linear model.

Heads: logreg (class_weight=balanced) and xgboost (scale_pos_weight /
LabelEncoder for multiclass). MLP is skipped per the rung-2 spec.
Tasks: multiclass_collapse and direct_binary, same definitions as rung 1.

Split/eval: identical machinery to rung 1 -- permit split (seed 42, same
hash/shuffle as train_sweep_opus.split_permits), and near-duplicate dedup
in eval. Dedup is inherently a property of the *pages* (revisions /
resubmittals render near-identical images), not of whichever feature set a
given experiment happens to use, so this script computes ONE canonical
train/eval page split (using the dinov2_vitb14 embedding space for the
cosine-similarity dedup pass -- the strongest, most diagnostic rung-1
backbone) and reuses it for every feature variant. That makes n_train/n_eval
identical across all rung-2 rows and directly comparable to each other; the
rung-1 baseline row is copied verbatim from experiments_opus.csv rather than
recomputed, so it is unaffected by this choice.

Output: appends rows to data/experiments_rung2.csv and prints a ranked
leaderboard that includes the rung-1 best as a labeled baseline row.

Usage
    python3 scripts/train_sweep_rung2.py
    python3 scripts/train_sweep_rung2.py --tag base2 --out data/experiments_rung2.csv
"""
import argparse
import os
import sys
import warnings

import numpy as np
import scipy.sparse as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_sweep_opus as r1  # noqa: E402  (reuse truth/split/dedup/metrics)

BACKBONES = r1.BACKBONES  # ["clip_vitl14", "siglip_b16", "dinov2_vitb14"]
HEADS = ["logreg", "xgboost"]
TASKS = ["multiclass_collapse", "direct_binary"]
DEDUP_BACKBONE = "dinov2_vitb14"

SVD_DIM = 256
TFIDF_KW = dict(ngram_range=(1, 2), lowercase=True, max_features=30000, min_df=2)

# rung-1 best, copied verbatim from data/experiments_opus.csv for comparison
# (2026-07-04 sweep; dinov2_vitb14 + logreg + multiclass_collapse).
RUNG1_BASELINE = {
    "features": "image_only(rung1)", "backbone": "dinov2_vitb14",
    "head": "logreg", "task": "multiclass_collapse",
    "n_train": 1206, "n_eval": 1256,
    "finish_recall": 0.365, "keep_recall": 0.490, "fp_rate": 0.155,
    "note": "RUNG-1 BASELINE (copied from experiments_opus.csv)",
}

CSV_FIELDS = [
    "run_id", "features", "backbone", "head", "task",
    "n_train", "n_eval", "finish_recall", "keep_recall", "fp_rate",
    "thr_full_finish", "fp_at_full_finish", "notes",
]


def _fmt(x):
    return "NA" if x is None else f"{x:.3f}"


# ----------------------------------------------------------------------------
# Text loading
# ----------------------------------------------------------------------------
def text_path_for(image_path):
    """data/pages/<docid>/page_0007.png -> data/pagetext/<docid>/page_0007.txt"""
    rel = image_path.replace("data/pages/", "data/pagetext/", 1)
    rel = os.path.splitext(rel)[0] + ".txt"
    return os.path.join(ROOT, rel)


def load_page_paths(database_url):
    """{page_id(int): image_path(str)} for every page row."""
    import psycopg2
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute("SELECT id, image_path FROM page")
        rows = cur.fetchall()
    finally:
        conn.close()
    return {int(pid): path for pid, path in rows}


def load_text_for_pages(page_ids, path_map):
    """Return list[str], aligned to page_ids, empty string if no text file."""
    out = []
    for pid in page_ids:
        ip = path_map.get(int(pid))
        txt = ""
        if ip is not None:
            fp = text_path_for(ip)
            if os.path.exists(fp):
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
        out.append(txt)
    return out


# ----------------------------------------------------------------------------
# Canonical page split (shared across all rung-2 feature variants)
# ----------------------------------------------------------------------------
def build_canonical_split(embeddings, truth, seed=r1.SEED,
                           dedup_threshold=r1.DEDUP_THRESHOLD):
    """Permit split identical to rung 1, dedup via the dinov2 embedding space.

    Returns dict with train_page_ids, eval_page_ids (eval = dedup reps only),
    cat_tr/cat_ev, keep_tr, permit_ev, train_permits, eval_permits, dedup_note.
    """
    usable_pids = set()
    for pids, _ in embeddings.values():
        usable_pids.update(int(p) for p in pids)
    permits_present = sorted({truth[p][1] for p in usable_pids if p in truth})
    if len(permits_present) < 2:
        raise SystemExit(f"need >=2 labeled permits; found {len(permits_present)}")
    train_permits, eval_permits = r1.split_permits(permits_present, seed)

    pids_d, emb_d = embeddings[DEDUP_BACKBONE]
    keep_row = np.array([int(p) in truth for p in pids_d])
    pids_d = pids_d[keep_row]
    emb_d = emb_d[keep_row]
    cats_d = np.array([truth[int(p)][0] for p in pids_d])
    permits_d = np.array([truth[int(p)][1] for p in pids_d])

    is_train = np.array([p in train_permits for p in permits_d])
    is_eval = np.array([p in eval_permits for p in permits_d])

    group_of = r1.dedup_groups(pids_d, emb_d, dedup_threshold)
    eval_rep = r1.eval_representative_mask(pids_d, group_of, is_eval)

    n_eval_all = int(is_eval.sum())
    n_eval_rep = int(eval_rep.sum())
    dedup_note = (f"dedup(thr={dedup_threshold}, basis={DEDUP_BACKBONE}): "
                  f"eval {n_eval_all}->{n_eval_rep} reps "
                  f"({n_eval_all - n_eval_rep} dups dropped)")

    return {
        "train_page_ids": pids_d[is_train],
        "eval_page_ids": pids_d[eval_rep],
        "cat_tr": cats_d[is_train], "cat_ev": cats_d[eval_rep],
        "keep_tr": np.array([c in r1.KEEP_CATEGORIES for c in cats_d[is_train]]).astype(int),
        "permit_ev": permits_d[eval_rep],
        "train_permits": train_permits, "eval_permits": eval_permits,
        "dedup_note": dedup_note,
    }


def align_embeddings(pids_all, emb_all, target_ids):
    """Row-align a backbone's (pids, emb) to an arbitrary target_ids order."""
    idx_map = {int(p): i for i, p in enumerate(pids_all)}
    idx = np.array([idx_map[int(p)] for p in target_ids])
    return emb_all[idx]


def l2norm_rows(x):
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


# ----------------------------------------------------------------------------
# Heads (mirrors train_sweep_opus.keep_scores: same head defs / task defs /
# keep-column-collapse logic, extended to accept sparse features and drop MLP)
# ----------------------------------------------------------------------------
def fit_and_score(head, task, X_tr, cat_tr, keep_tr, X_ev, is_sparse):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import LabelEncoder, StandardScaler, MaxAbsScaler

    def build_logreg():
        scaler = MaxAbsScaler() if is_sparse else StandardScaler()
        clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
        return make_pipeline(scaler, clf)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if task == "direct_binary":
            if len(np.unique(keep_tr)) < 2:
                return None, "degenerate: train keep is single-class"
            if head == "xgboost":
                import xgboost as xgb
                pos = int(keep_tr.sum())
                neg = int(len(keep_tr) - pos)
                clf = xgb.XGBClassifier(
                    n_estimators=400, max_depth=6, learning_rate=0.1,
                    subsample=0.9, colsample_bytree=0.9,
                    tree_method="hist", n_jobs=-1, verbosity=0,
                    eval_metric="logloss",
                    scale_pos_weight=(neg / pos) if pos else 1.0,
                )
                clf.fit(X_tr, keep_tr)
                proba = clf.predict_proba(X_ev)
                col = list(clf.classes_).index(1)
                return proba[:, col], ""
            est = build_logreg()
            est.fit(X_tr, keep_tr)
            proba = est.predict_proba(X_ev)
            col = list(est.classes_).index(1)
            return proba[:, col], ""

        # multiclass_collapse
        if len(np.unique(cat_tr)) < 2:
            return None, "degenerate: train has a single category"
        enc = LabelEncoder()
        y = enc.fit_transform(cat_tr)
        keep_cols = [i for i, c in enumerate(enc.classes_) if c in r1.KEEP_CATEGORIES]
        if not keep_cols:
            return None, "no keep-class categories present in train"
        if head == "xgboost":
            import xgboost as xgb
            clf = xgb.XGBClassifier(
                n_estimators=400, max_depth=6, learning_rate=0.1,
                subsample=0.9, colsample_bytree=0.9,
                tree_method="hist", n_jobs=-1, verbosity=0,
                objective="multi:softprob", num_class=len(enc.classes_),
                eval_metric="mlogloss",
            )
            clf.fit(X_tr, y)
            proba = clf.predict_proba(X_ev)
        else:
            est = build_logreg()
            est.fit(X_tr, y)
            proba = est.predict_proba(X_ev)
        scores = proba[:, keep_cols].sum(axis=1)
        return scores, ""


# ----------------------------------------------------------------------------
# One experiment
# ----------------------------------------------------------------------------
def run_experiment(features, backbone, head, task, X_tr, X_ev, split, is_sparse,
                    out_csv, extra_note=""):
    cat_tr, keep_tr = split["cat_tr"], split["keep_tr"]
    cat_ev, permit_ev = split["cat_ev"], split["permit_ev"]
    n_train, n_eval = len(cat_tr), len(cat_ev)

    scores, degen = fit_and_score(head, task, X_tr, cat_tr, keep_tr, X_ev, is_sparse)

    row = {
        "run_id": "rung2", "features": features, "backbone": backbone,
        "head": head, "task": task, "n_train": n_train, "n_eval": n_eval,
    }

    if scores is None or n_eval == 0:
        note = degen or "no eval pages"
        row.update({
            "finish_recall": "", "keep_recall": "", "fp_rate": "",
            "thr_full_finish": "", "fp_at_full_finish": "",
            "notes": f"{note}; {split['dedup_note']}; {extra_note}",
        })
        append_csv(out_csv, row)
        return {"features": features, "backbone": backbone, "head": head,
                "task": task, "finish_recall": None, "fp_rate": None, "note": note}

    overall, packet, is_finish = r1.compute_metrics(scores, cat_ev, permit_ev, 0.5)
    thr_full = r1.full_finish_threshold(scores, is_finish)

    if thr_full is not None:
        of, _, _ = r1.compute_metrics(scores, cat_ev, permit_ev, thr_full)
        fp_at_full = of["fp_rate"]
        full_note = (f"@fullfin(thr={thr_full:.3f}): kr={_fmt(of['keep_recall'])} "
                     f"fp={_fmt(of['fp_rate'])} kp={_fmt(of['keep_precision'])}")
    else:
        fp_at_full = None
        full_note = "no finish pages in eval"

    notes = (f"{full_note}; pkt@0.5: fin_rec={_fmt(packet['finish_recall'])} "
             f"flrdemo_rec={_fmt(packet['floordemo_recall'])} fp={_fmt(packet['fp_rate'])}; "
             f"kp@0.5={_fmt(overall['keep_precision'])} "
             f"flrdemo_rec@0.5={_fmt(overall['floordemo_recall'])}; "
             f"{split['dedup_note']}; {extra_note}")

    row.update({
        "finish_recall": _fmt(overall["finish_recall"]),
        "keep_recall": _fmt(overall["keep_recall"]),
        "fp_rate": _fmt(overall["fp_rate"]),
        "thr_full_finish": _fmt(thr_full),
        "fp_at_full_finish": _fmt(fp_at_full),
        "notes": notes,
    })
    append_csv(out_csv, row)

    print(f"  {features:22s} {backbone:14s} {head:8s} {task:19s} | "
          f"fin_rec@0.5={_fmt(overall['finish_recall'])} "
          f"keep_rec@0.5={_fmt(overall['keep_recall'])} "
          f"fp@0.5={_fmt(overall['fp_rate'])} | {full_note}", flush=True)

    return {"features": features, "backbone": backbone, "head": head, "task": task,
            "finish_recall": overall["finish_recall"], "fp_rate": overall["fp_rate"],
            "note": full_note}


def append_csv(out_csv, row):
    import csv
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    is_new = not os.path.exists(out_csv)
    with open(out_csv, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new:
            w.writeheader()
        w.writerow(row)


def print_leaderboard(results, out_csv, top_n=10):
    def key(r):
        fr, fp = r["finish_recall"], r["fp_rate"]
        return (0 if fr is not None else 1, -(fr if fr is not None else 0.0),
                fp if fp is not None else 1.0)

    ranked = sorted(results, key=key)
    print("\n" + "=" * 96)
    print(f"LEADERBOARD  (rank by finish_recall@0.5 desc, then fp_rate asc) -- top {top_n}")
    print("=" * 96)
    print(f"{'#':>2}  {'features':22s} {'backbone':14s} {'head':8s} {'task':19s} "
          f"{'finRec':>7} {'fpRate':>7}  note")
    print("-" * 96)
    for i, r in enumerate(ranked[:top_n], 1):
        print(f"{i:>2}  {r['features']:22s} {r['backbone']:14s} {r['head']:8s} "
              f"{r['task']:19s} {_fmt(r['finish_recall']):>7} {_fmt(r['fp_rate']):>7}  "
              f"{r.get('note', '')}")
    print("=" * 96)
    print(f"rows appended to: {out_csv}")
    if ranked:
        best = ranked[0]
        print(f"\nBEST rung-2 config: features={best['features']} "
              f"backbone={best['backbone']} head={best['head']} task={best['task']} "
              f"finish_recall@0.5={_fmt(best['finish_recall'])} "
              f"fp_rate@0.5={_fmt(best['fp_rate'])}")


# ----------------------------------------------------------------------------
# Main sweep
# ----------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description="Model-1 rung-2 text-feature sweep.")
    p.add_argument("--tag", default="base2")
    p.add_argument("--out", default=os.path.join(ROOT, "data", "experiments_rung2.csv"))
    p.add_argument("--heads", nargs="+", default=HEADS, choices=HEADS)
    p.add_argument("--tasks", nargs="+", default=TASKS, choices=TASKS)
    p.add_argument("--backbones", nargs="+", default=BACKBONES)
    args = p.parse_args(argv)

    env = r1.load_env()
    if "NEON_DATABASE_URL" not in env:
        print("ERROR: NEON_DATABASE_URL not found in .env", file=sys.stderr)
        return 2
    db_url = env["NEON_DATABASE_URL"]

    print("building truth table from Neon (schema estimate)...", flush=True)
    truth = r1.build_truth_table(db_url)
    keep_n = sum(1 for c, _ in truth.values() if c in r1.KEEP_CATEGORIES)
    print(f"truth: {len(truth)} labeled pages, {keep_n} keep "
          f"({100 * keep_n / max(len(truth), 1):.1f}%)", flush=True)

    embeddings = {}
    for backbone in args.backbones:
        embeddings[backbone] = r1.load_embeddings(args.tag, backbone)
        n, d = embeddings[backbone][1].shape
        print(f"loaded {backbone}: {n} pages x {d} dims", flush=True)

    print("\nloading page text (data/pagetext/<docid>/page_XXXX.txt)...", flush=True)
    path_map = load_page_paths(db_url)
    n_nonempty, n_total = 0, 0
    for pid in truth:
        ip = path_map.get(pid)
        if ip is None:
            continue
        n_total += 1
        fp = text_path_for(ip)
        if os.path.exists(fp):
            with open(fp, encoding="utf-8", errors="ignore") as f:
                if f.read().strip():
                    n_nonempty += 1
    coverage = n_nonempty / n_total if n_total else 0.0
    print(f"TEXT COVERAGE: {n_nonempty}/{n_total} labeled pages "
          f"({100 * coverage:.1f}%) have non-empty extracted text "
          f"(rest are scans or pre-text-extraction renders).", flush=True)

    split = build_canonical_split(embeddings, truth)
    print(f"\ncanonical split (seed={r1.SEED}): "
          f"{len(split['train_permits'])} train / {len(split['eval_permits'])} eval permits; "
          f"n_train={len(split['train_page_ids'])} n_eval={len(split['eval_page_ids'])} "
          f"| {split['dedup_note']}", flush=True)

    text_tr = load_text_for_pages(split["train_page_ids"], path_map)
    text_ev = load_text_for_pages(split["eval_page_ids"], path_map)

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD

    print(f"\nfitting TF-IDF on {len(text_tr)} train pages "
          f"({TFIDF_KW})...", flush=True)
    vec = TfidfVectorizer(**TFIDF_KW)
    tfidf_tr = vec.fit_transform(text_tr)
    tfidf_ev = vec.transform(text_ev)
    print(f"TF-IDF vocab size: {len(vec.vocabulary_)}", flush=True)

    print(f"fitting TruncatedSVD(n_components={SVD_DIM}) on train TF-IDF...", flush=True)
    svd = TruncatedSVD(n_components=SVD_DIM, random_state=r1.SEED)
    text_svd_tr = l2norm_rows(svd.fit_transform(tfidf_tr))
    text_svd_ev = l2norm_rows(svd.transform(tfidf_ev))

    results = []

    # --- variant a: text_only (sparse TF-IDF) -------------------------------
    print("\n[text_only]", flush=True)
    for head in args.heads:
        for task in args.tasks:
            results.append(run_experiment(
                "text_only", "none", head, task,
                tfidf_tr, tfidf_ev, split, is_sparse=True, out_csv=args.out,
                extra_note=f"tfidf_vocab={len(vec.vocabulary_)}",
            ))

    # --- variant b: text_svd + <backbone> (dense concat) --------------------
    for backbone in args.backbones:
        pids_bb, emb_bb = embeddings[backbone]
        emb_tr = l2norm_rows(align_embeddings(pids_bb, emb_bb, split["train_page_ids"]))
        emb_ev = l2norm_rows(align_embeddings(pids_bb, emb_bb, split["eval_page_ids"]))
        X_tr = np.hstack([text_svd_tr, emb_tr])
        X_ev = np.hstack([text_svd_ev, emb_ev])
        print(f"\n[text_svd+{backbone}]  X_tr={X_tr.shape} X_ev={X_ev.shape}", flush=True)
        for head in args.heads:
            for task in args.tasks:
                results.append(run_experiment(
                    f"text_svd+{backbone}", backbone, head, task,
                    X_tr, X_ev, split, is_sparse=False, out_csv=args.out,
                    extra_note=f"svd_dim={SVD_DIM}, L2-norm each block pre-concat",
                ))

    # --- variant c: raw sparse hstack, logreg only --------------------------
    for backbone in args.backbones:
        if "logreg" not in args.heads:
            continue
        pids_bb, emb_bb = embeddings[backbone]
        emb_tr = align_embeddings(pids_bb, emb_bb, split["train_page_ids"])
        emb_ev = align_embeddings(pids_bb, emb_bb, split["eval_page_ids"])
        X_tr = sp.hstack([tfidf_tr, sp.csr_matrix(emb_tr.astype(np.float64))]).tocsr()
        X_ev = sp.hstack([tfidf_ev, sp.csr_matrix(emb_ev.astype(np.float64))]).tocsr()
        print(f"\n[text_sparse+{backbone}]  X_tr={X_tr.shape} X_ev={X_ev.shape}", flush=True)
        for task in args.tasks:
            results.append(run_experiment(
                f"text_sparse+{backbone}", backbone, "logreg", task,
                X_tr, X_ev, split, is_sparse=True, out_csv=args.out,
                extra_note="raw TF-IDF+emb sparse hstack, no SVD",
            ))

    baseline_result = dict(RUNG1_BASELINE)
    all_for_board = results + [baseline_result]
    print_leaderboard(all_for_board, args.out, top_n=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
