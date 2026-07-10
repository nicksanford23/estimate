#!/usr/bin/env python3
"""Probe 30 Phase 2 -- split (already locked by probe30_roster.py, by
PERMIT, never by page) + train the wall_model_v2 HistGradientBoostingClassifier
+ its ablation (probe25's raw features, no fixes) + the learning curve
(15/30/45/60/all train permits).

Reads cached features from data/probe30/features/<tag>.npz (synced from R2
claude-repo/probe30_features/ -- see probe30_extract_worker.py). Writes:
  models/wall_model_v2.joblib          -- FIXED features, all 69 train permits
  models/wall_model_v2_ablation_raw.joblib -- RAW (probe25) features, same permits
  data/probe30/learning_curve/model_N{N}.joblib  -- fixed-feature models at each N
  data/probe30/segment_results.json    -- all segment-level tables + learning curve
"""
import csv
import json
import os
import random

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROSTER = os.path.join(ROOT, "data", "probe30", "roster.csv")
FEAT_DIR = os.path.join(ROOT, "data", "probe30", "features")
MODELS_DIR = os.path.join(ROOT, "models")
LC_DIR = os.path.join(ROOT, "data", "probe30", "learning_curve")
OUT_JSON = os.path.join(ROOT, "data", "probe30", "segment_results.json")
os.makedirs(LC_DIR, exist_ok=True)

LEARNING_CURVE_NS = [15, 30, 45, 60, "all"]
HGB_KW = dict(max_iter=200, learning_rate=0.08, max_depth=6,
              class_weight="balanced", random_state=0)


def load_roster():
    rows = list(csv.DictReader(open(ROSTER)))
    return rows


def load_npz(permit, doc_id, page):
    tag = f"{permit}_{doc_id}_p{page}"
    path = os.path.join(FEAT_DIR, f"{tag}.npz")
    z = np.load(path, allow_pickle=True)
    return z, tag


def build_dataset(rows):
    """Returns dict permit -> dict(X_raw, X_fixed, y, tag) and concatenated
    arrays + a parallel permit-id array (for grouping)."""
    per_permit = {}
    for r in rows:
        z, tag = load_npz(r["permit"], r["doc_id"], r["page"])
        entry = per_permit.setdefault(r["permit"], dict(X_raw=[], X_fixed=[], y=[], tags=[]))
        entry["X_raw"].append(z["X_raw"])
        entry["X_fixed"].append(z["X_fixed"])
        entry["y"].append(z["y"])
        entry["tags"].append(tag)
    return per_permit


def stack(per_permit, permits, feat_key):
    Xs, ys = [], []
    for p in permits:
        for X, y in zip(per_permit[p][feat_key], per_permit[p]["y"]):
            Xs.append(X)
            ys.append(y)
    return np.concatenate(Xs), np.concatenate(ys)


def best_f1_threshold(y_true, scores):
    best_f1, best_t = -1, 0.5
    for t in np.linspace(0.05, 0.95, 19):
        pred = scores >= t
        tp = np.sum(pred & (y_true == 1))
        fp = np.sum(pred & (y_true == 0))
        fn = np.sum((~pred) & (y_true == 1))
        prec = tp / (tp + fp) if (tp + fp) else 0
        rec = tp / (tp + fn) if (tp + fn) else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
        if f1 > best_f1:
            best_f1, best_t = f1, t
    return round(float(best_t), 2), round(float(best_f1), 3)


def per_permit_prauc(clf, per_permit, permits, feat_key):
    out = {}
    for p in permits:
        Xp, yp = stack(per_permit, [p], feat_key)
        if yp.sum() == 0:
            out[p] = dict(pr_auc=None, n_segs=int(len(yp)), n_wall=0, note="no wall-labeled segments on this page")
            continue
        scores = clf.predict_proba(Xp)[:, 1]
        ap = average_precision_score(yp, scores)
        out[p] = dict(pr_auc=round(float(ap), 4), n_segs=int(len(yp)), n_wall=int(yp.sum()),
                       base_rate=round(float(yp.mean()), 4))
    return out


def main():
    rows = load_roster()
    train_rows = [r for r in rows if r["split"] == "train"]
    holdout_rows = [r for r in rows if r["split"] == "holdout"]
    train_permits = sorted({r["permit"] for r in train_rows})
    holdout_permits = sorted({r["permit"] for r in holdout_rows})
    print(f"train permits: {len(train_permits)}  holdout permits: {len(holdout_permits)}")

    per_permit = build_dataset(train_rows + holdout_rows)

    results = dict(train_permits=train_permits, holdout_permits=holdout_permits)

    # ---------------- FULL fixed model ----------------
    X_train_fixed, y_train = stack(per_permit, train_permits, "X_fixed")
    clf_fixed = HistGradientBoostingClassifier(**HGB_KW)
    clf_fixed.fit(X_train_fixed, y_train)
    joblib.dump(clf_fixed, os.path.join(MODELS_DIR, "wall_model_v2.joblib"))

    train_scores_fixed = clf_fixed.predict_proba(X_train_fixed)[:, 1]
    t_fixed, f1_fixed = best_f1_threshold(y_train, train_scores_fixed)
    prauc_fixed = per_permit_prauc(clf_fixed, per_permit, holdout_permits, "X_fixed")
    vals = [v["pr_auc"] for v in prauc_fixed.values() if v["pr_auc"] is not None]
    X_hold_fixed, y_hold = stack(per_permit, holdout_permits, "X_fixed")
    pooled_prauc_fixed = round(float(average_precision_score(y_hold, clf_fixed.predict_proba(X_hold_fixed)[:, 1])), 4)

    results["fixed_model"] = dict(
        n_train_segs=int(len(y_train)), n_train_wall=int(y_train.sum()),
        canonical_threshold=t_fixed, train_f1_at_threshold=f1_fixed,
        per_holdout_permit_pr_auc=prauc_fixed,
        pooled_holdout_pr_auc=pooled_prauc_fixed,
        spread=dict(min=round(min(vals), 4), median=round(float(np.median(vals)), 4),
                    max=round(max(vals), 4)) if vals else None,
    )
    print("FIXED model:", json.dumps(results["fixed_model"], indent=2, default=str))

    # ---------------- ABLATION: raw (probe25) features, no fixes ----------------
    X_train_raw, y_train_r = stack(per_permit, train_permits, "X_raw")
    clf_raw = HistGradientBoostingClassifier(**HGB_KW)
    clf_raw.fit(X_train_raw, y_train_r)
    joblib.dump(clf_raw, os.path.join(MODELS_DIR, "wall_model_v2_ablation_raw.joblib"))

    train_scores_raw = clf_raw.predict_proba(X_train_raw)[:, 1]
    t_raw, f1_raw = best_f1_threshold(y_train_r, train_scores_raw)
    prauc_raw = per_permit_prauc(clf_raw, per_permit, holdout_permits, "X_raw")
    vals_r = [v["pr_auc"] for v in prauc_raw.values() if v["pr_auc"] is not None]
    X_hold_raw, y_hold_r = stack(per_permit, holdout_permits, "X_raw")
    pooled_prauc_raw = round(float(average_precision_score(y_hold_r, clf_raw.predict_proba(X_hold_raw)[:, 1])), 4)

    results["ablation_raw_model"] = dict(
        n_train_segs=int(len(y_train_r)), n_train_wall=int(y_train_r.sum()),
        canonical_threshold=t_raw, train_f1_at_threshold=f1_raw,
        per_holdout_permit_pr_auc=prauc_raw,
        pooled_holdout_pr_auc=pooled_prauc_raw,
        spread=dict(min=round(min(vals_r), 4), median=round(float(np.median(vals_r)), 4),
                    max=round(max(vals_r), 4)) if vals_r else None,
    )
    print("ABLATION (raw, probe25) model:", json.dumps(results["ablation_raw_model"], indent=2, default=str))

    # ---------------- probe25 baseline reference ----------------
    results["probe25_baseline_pr_auc_range"] = [0.11, 0.13]

    # ---------------- LEARNING CURVE ----------------
    rng = random.Random(42)
    shuffled = train_permits[:]
    rng.shuffle(shuffled)
    lc = []
    for n in LEARNING_CURVE_NS:
        subset = shuffled if n == "all" else shuffled[:n]
        Xn, yn = stack(per_permit, subset, "X_fixed")
        clf_n = HistGradientBoostingClassifier(**HGB_KW)
        clf_n.fit(Xn, yn)
        model_path = os.path.join(LC_DIR, f"model_N{n}.joblib")
        joblib.dump(clf_n, model_path)

        train_scores_n = clf_n.predict_proba(Xn)[:, 1]
        t_n, f1_n = best_f1_threshold(yn, train_scores_n)
        prauc_n = per_permit_prauc(clf_n, per_permit, holdout_permits, "X_fixed")
        vals_n = [v["pr_auc"] for v in prauc_n.values() if v["pr_auc"] is not None]
        X_hold_n, y_hold_n = stack(per_permit, holdout_permits, "X_fixed")
        pooled_n = round(float(average_precision_score(y_hold_n, clf_n.predict_proba(X_hold_n)[:, 1])), 4)
        entry = dict(n_train_permits=len(subset), permits=subset,
                     canonical_threshold=t_n, pooled_holdout_pr_auc=pooled_n,
                     median_holdout_pr_auc=round(float(np.median(vals_n)), 4) if vals_n else None,
                     model_path=os.path.relpath(model_path, ROOT))
        lc.append(entry)
        print(f"learning curve N={n}: pooled_pr_auc={pooled_n} median_pr_auc={entry['median_holdout_pr_auc']}")
    results["learning_curve"] = lc

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nwrote {OUT_JSON}")


if __name__ == "__main__":
    main()
