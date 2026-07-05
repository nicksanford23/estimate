#!/usr/bin/env python3
"""Train + package the FINAL Model-1 v1 (shippable) classifier.

This is the production artifact behind the demo service. It is the rung-2c
"text_only" winner config, retrained on the FROZEN split_v1 TRAIN side and
packaged (vectorizer + classifier + operating threshold + metadata) into a
single joblib blob that scripts/predict.py and the FastAPI demo load with no
training-code dependency.

Config (identical to scripts/rung2c.py CONFIG (b), the honest split_v1 winner):
    features : text_only
    text     : TF-IDF(word, ngram_range=(1,2), max_features=30000, min_df=2),
               fit on TRAIN pages only.
    head     : LogisticRegression(class_weight='balanced', C=1.0, max_iter=2000)
               inside make_pipeline(MaxAbsScaler(), ...) -- mirrors
               train_sweep_rung2.fit_and_score('logreg','direct_binary', sparse).
    target   : direct_binary keep, keep := category in {floor_plan, finish_plan,
               finish_schedule, demo_plan} (CLAUDE.md hard rule).
    split    : ALL split_v1 TRAIN permits are training data; eval = split_v1
               EVAL permits (used ONLY to pick the threshold + report metrics).

Threshold (the safety-first operating point):
    thr_star = largest threshold at which finish_recall == 1.0 on eval
               == min score over eval finish pages (train_sweep_opus.
               full_finish_threshold). This is the tightest cut that still
               catches every finish_plan/finish_schedule page.
    thr_v1   = thr_star / 2   (2x safety margin -- deploy strictly looser than
               the just-barely-full-recall point, so drift can't silently drop
               a finish page).
    Reported metrics at thr_v1: finish_recall (MUST be 1.0), fp_rate, frac_kept.

Package (models/model_v1.joblib, dict):
    vectorizer         : fitted TfidfVectorizer
    model              : fitted sklearn Pipeline (MaxAbsScaler + LogisticRegression)
    positive_class_index : column of model.predict_proba giving P(keep=1)
    threshold          : thr_v1 (the deployed cut)
    keep_rule          : {"keep_categories": [...], "definition": "..."}
    split_version      : "v1" (data/split_v1.json)
    metrics            : eval metrics dict at thr_v1 and thr_star
    meta               : sklearn version, tfidf kwargs, train/eval sizes, ts

Also uploads the blob to R2 claude-repo/models/model_v1.joblib (boto3).

Usage
    python3 scripts/train_v1.py                 # train, package, upload
    python3 scripts/train_v1.py --no-upload     # skip R2 upload
"""
import argparse
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_sweep_opus as r1     # noqa: E402  (reuse, not modified)
import train_sweep_rung2 as ts2   # noqa: E402  (reuse, not modified)

MODEL_DIR = os.path.join(ROOT, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "model_v1.joblib")
R2_KEY = "claude-repo/models/model_v1.joblib"


def _fmt(x):
    return "NA" if x is None else f"{x:.4f}"


def load_frozen_split(path):
    with open(path) as f:
        return json.load(f)


def build_train_eval(db_url, split_path):
    """Reproduce rung2c.build_frozen_ctx's page assignment for text_only.

    A page is EVAL iff its permit is in split_v1.json['eval']; every other
    labeled page (incl. permits labeled after the split was frozen) is TRAIN.
    """
    print("building truth table from Neon (schema estimate)...", flush=True)
    truth = r1.build_truth_table(db_url)  # {page_id: (category, permit)}
    keep_n = sum(1 for c, _ in truth.values() if c in r1.KEEP_CATEGORIES)
    print(f"truth: {len(truth)} labeled pages, {keep_n} keep "
          f"({100 * keep_n / max(len(truth), 1):.1f}%)", flush=True)

    split_json = load_frozen_split(split_path)
    eval_permits = set(split_json["eval"])

    page_ids = np.array(sorted(truth), dtype=np.int64)
    cats = np.array([truth[int(p)][0] for p in page_ids])
    permits = np.array([truth[int(p)][1] for p in page_ids])
    is_eval = np.array([p in eval_permits for p in permits])

    train_ids, eval_ids = page_ids[~is_eval], page_ids[is_eval]
    cat_tr, cat_ev = cats[~is_eval], cats[is_eval]
    permit_ev = permits[is_eval]
    keep_tr = np.array([c in r1.KEEP_CATEGORIES for c in cat_tr]).astype(int)

    n_finish_ev = int(np.isin(cat_ev, list(r1.FINISH_CATEGORIES)).sum())
    print(f"n_train={len(train_ids)} ({len(set(permits[~is_eval]))} permits) | "
          f"n_eval={len(eval_ids)} ({len(set(permit_ev))} permits, "
          f"{n_finish_ev} finish pages)", flush=True)

    path_map = ts2.load_page_paths(db_url)
    text_tr = ts2.load_text_for_pages(train_ids, path_map)
    text_ev = ts2.load_text_for_pages(eval_ids, path_map)
    n_tr_text = sum(1 for t in text_tr if t.strip())
    n_ev_text = sum(1 for t in text_ev if t.strip())
    print(f"text coverage: train {n_tr_text}/{len(text_tr)} "
          f"({100 * n_tr_text / max(len(text_tr), 1):.1f}%), "
          f"eval {n_ev_text}/{len(text_ev)} "
          f"({100 * n_ev_text / max(len(text_ev), 1):.1f}%)", flush=True)

    return {
        "cat_tr": cat_tr, "keep_tr": keep_tr, "text_tr": text_tr,
        "cat_ev": cat_ev, "permit_ev": permit_ev, "text_ev": text_ev,
        "n_train": len(train_ids), "n_eval": len(eval_ids),
        "n_finish_ev": n_finish_ev,
    }


def train_and_package(ctx, split_path, upload=True):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import MaxAbsScaler
    import sklearn
    import joblib

    text_tr, keep_tr = ctx["text_tr"], ctx["keep_tr"]
    text_ev, cat_ev, permit_ev = ctx["text_ev"], ctx["cat_ev"], ctx["permit_ev"]

    # ---- fit vectorizer on TRAIN only (no leakage), then the classifier ----
    vec = TfidfVectorizer(**ts2.TFIDF_KW)
    X_tr = vec.fit_transform(text_tr)
    X_ev = vec.transform(text_ev)
    print(f"\nTF-IDF vocab size: {len(vec.vocabulary_)} "
          f"(fit on {ctx['n_train']} train pages; kwargs={ts2.TFIDF_KW})",
          flush=True)

    model = make_pipeline(
        MaxAbsScaler(),
        LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"),
    )
    model.fit(X_tr, keep_tr)
    clf = model.steps[-1][1]
    pos_idx = int(list(clf.classes_).index(1))

    scores_ev = model.predict_proba(X_ev)[:, pos_idx]

    # ---- threshold selection: full-finish-recall point, then 2x margin ----
    is_finish_ev = np.isin(cat_ev, list(r1.FINISH_CATEGORIES))
    thr_star = r1.full_finish_threshold(scores_ev, is_finish_ev)
    if thr_star is None:
        raise SystemExit("no finish pages in eval -- cannot pick threshold")
    thr_v1 = thr_star / 2.0

    def metrics_at(thr):
        overall, _packet, _ = r1.compute_metrics(scores_ev, cat_ev, permit_ev, thr)
        pred = scores_ev >= thr
        return {
            "threshold": float(thr),
            "finish_recall": overall["finish_recall"],
            "keep_recall": overall["keep_recall"],
            "fp_rate": overall["fp_rate"],
            "frac_kept": float(pred.mean()),
        }

    m_star = metrics_at(thr_star)
    m_v1 = metrics_at(thr_v1)

    print("\n" + "=" * 78)
    print("V1 THRESHOLD SELECTION (frozen split_v1 eval)")
    print("=" * 78)
    print(f"thr_star (largest thr with finish_recall=1.0) = {thr_star:.6f}")
    print(f"  @thr_star : finish_recall={_fmt(m_star['finish_recall'])} "
          f"fp_rate={_fmt(m_star['fp_rate'])} frac_kept={_fmt(m_star['frac_kept'])}")
    print(f"thr_v1 = thr_star/2 = {thr_v1:.6f}  <-- DEPLOYED (2x safety margin)")
    print(f"  @thr_v1   : finish_recall={_fmt(m_v1['finish_recall'])} "
          f"fp_rate={_fmt(m_v1['fp_rate'])} frac_kept={_fmt(m_v1['frac_kept'])}")
    assert abs(m_v1["finish_recall"] - 1.0) < 1e-9, \
        f"finish_recall at thr_v1 must be 1.0, got {m_v1['finish_recall']}"
    print("ASSERT OK: finish_recall == 1.0 at deployed threshold")

    keep_rule = {
        "keep_categories": sorted(r1.KEEP_CATEGORIES),
        "definition": ("keep=1 iff page category in keep_categories "
                       "(CLAUDE.md hard rule; site plans never keep)"),
        "no_text_conservative": ("pages with <50 chars extracted text are "
                                 "force-kept by the serving layer, not scored"),
    }
    package = {
        "vectorizer": vec,
        "model": model,
        "positive_class_index": pos_idx,
        "threshold": float(thr_v1),
        "threshold_full_finish": float(thr_star),
        "keep_rule": keep_rule,
        "split_version": "v1",
        "metrics": {
            "at_thr_v1": m_v1,
            "at_thr_full_finish": m_star,
            "n_train": ctx["n_train"],
            "n_eval": ctx["n_eval"],
            "n_finish_eval": ctx["n_finish_ev"],
        },
        "meta": {
            "config": "text_only TF-IDF(1-2gram,30k,min_df=2) + logreg(balanced) direct_binary",
            "tfidf_kwargs": dict(ts2.TFIDF_KW),
            "sklearn_version": sklearn.__version__,
            "split_file": os.path.basename(split_path),
            "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "min_text_chars_for_scoring": 50,
        },
    }

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(package, MODEL_PATH)
    size_kb = os.path.getsize(MODEL_PATH) / 1024
    print(f"\nwrote {MODEL_PATH} ({size_kb:.0f} KB)")

    if upload:
        upload_to_r2(MODEL_PATH)

    return package


def upload_to_r2(path):
    import boto3
    env = r1.load_env()
    s3 = boto3.client(
        "s3", endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    s3.upload_file(path, env["R2_BUCKET"], R2_KEY)
    print(f"uploaded to R2: s3://{env['R2_BUCKET']}/{R2_KEY}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Train + package Model-1 v1.")
    p.add_argument("--split", default=os.path.join(ROOT, "data", "split_v1.json"))
    p.add_argument("--no-upload", action="store_true", help="skip R2 upload")
    args = p.parse_args(argv)

    env = r1.load_env()
    if "NEON_DATABASE_URL" not in env:
        print("ERROR: NEON_DATABASE_URL not in .env", file=sys.stderr)
        return 2

    ctx = build_train_eval(env["NEON_DATABASE_URL"], args.split)
    pkg = train_and_package(ctx, args.split, upload=not args.no_upload)

    print("\n" + "=" * 78)
    print("V1 SUMMARY")
    print("=" * 78)
    print(json.dumps({
        "threshold_deployed": pkg["threshold"],
        "threshold_full_finish": pkg["threshold_full_finish"],
        "metrics_at_thr_v1": pkg["metrics"]["at_thr_v1"],
        "n_train": pkg["metrics"]["n_train"],
        "n_eval": pkg["metrics"]["n_eval"],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
