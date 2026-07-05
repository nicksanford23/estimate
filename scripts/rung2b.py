#!/usr/bin/env python3
"""Rung-2b, Tasks 2+3: threshold/PR analysis of the rung-2 winner, then a
text+image router evaluation.

Context (STATE.md, "Rung-2 results + diagnosis"): text_only TF-IDF(1-2gram,
max_features=30000, min_df=2) + logreg(class_weight=balanced) + direct_binary
keep is the rung-2 winner: finish_recall@0.5 = 0.974 but fp_rate@0.5 = 0.794
(keeps most junk at the default 0.5 cut). Two prescriptions, both implemented
here after scripts/backfill_pagetext.py raises text coverage:

TASK 2 (threshold/PR table): retrain that exact winner on the canonical
permit split (seed 42, identical machinery to rung 1/rung 2 -- imported, not
copied) and print finish_recall / keep_recall / fp_rate / fraction-of-pages-
kept across a fixed threshold grid, then name the best operating points for
(a) finish_recall == 1.0 and (b) finish_recall >= 0.97, each at lowest fp.

TASK 3 (router): pages WITH non-empty extracted text go to the text model
above; pages WITHOUT go to an image model (dinov2_vitb14 embeddings + logreg
+ multiclass_collapse, the rung-1 config). Each branch is trained ONLY on its
own train-side population (has-text train pages / no-text train pages) so
train and eval populations match, and each branch's threshold is picked from
its OWN train-side scores (full_finish_threshold: the tightest threshold that
still catches every finish page in that branch's train subset) -- never from
eval -- so the reported eval numbers are a genuine generalization test, not a
post-hoc-fit operating point. This mirrors the spec's explicit instruction for
the image branch ("tuned for finish_recall=1.0 on its train side") and is
applied symmetrically to the text branch for the same no-leakage reason.

Reuse policy: imports (does not copy or modify) train_sweep_opus.py
(build_truth_table, load_embeddings, keep_scores, compute_metrics,
full_finish_threshold, FINISH_CATEGORIES, KEEP_CATEGORIES, append_csv/
CSV_FIELDS via train_sweep_rung2) and train_sweep_rung2.py (build_canonical_
split, load_page_paths, load_text_for_pages, text_path_for, TFIDF_KW,
fit_and_score, align_embeddings, append_csv, CSV_FIELDS).

Usage
    python3 scripts/rung2b.py                    # both tasks, appends router
                                                   # row to experiments_rung2.csv
    python3 scripts/rung2b.py --skip-router       # task 2 only
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_sweep_opus as r1     # noqa: E402  (reuse, not modified)
import train_sweep_rung2 as ts2   # noqa: E402  (reuse, not modified)

BACKBONE = "dinov2_vitb14"
TAG = "base2"
THRESHOLDS = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 0.02]


def _fmt(x):
    return "NA" if x is None else f"{x:.3f}"


# ----------------------------------------------------------------------------
# Shared setup: truth, canonical split, text
# ----------------------------------------------------------------------------
def build_context(db_url, tag=TAG, backbone=BACKBONE):
    print("building truth table from Neon (schema estimate)...", flush=True)
    truth = r1.build_truth_table(db_url)
    keep_n = sum(1 for c, _ in truth.values() if c in r1.KEEP_CATEGORIES)
    print(f"truth: {len(truth)} labeled pages, {keep_n} keep "
          f"({100 * keep_n / max(len(truth), 1):.1f}%)", flush=True)

    pids_d, emb_d = r1.load_embeddings(tag, backbone)
    print(f"loaded {backbone}: {len(pids_d)} pages x {emb_d.shape[1]} dims", flush=True)

    split = ts2.build_canonical_split({backbone: (pids_d, emb_d)}, truth)
    print(f"canonical split (seed={r1.SEED}): "
          f"{len(split['train_permits'])} train / {len(split['eval_permits'])} eval permits; "
          f"n_train={len(split['train_page_ids'])} n_eval={len(split['eval_page_ids'])} "
          f"| {split['dedup_note']}", flush=True)

    path_map = ts2.load_page_paths(db_url)
    text_tr = ts2.load_text_for_pages(split["train_page_ids"], path_map)
    text_ev = ts2.load_text_for_pages(split["eval_page_ids"], path_map)
    n_tr_text = sum(1 for t in text_tr if t.strip())
    n_ev_text = sum(1 for t in text_ev if t.strip())
    print(f"text coverage on canonical split: train {n_tr_text}/{len(text_tr)} "
          f"({100 * n_tr_text / max(len(text_tr), 1):.1f}%), "
          f"eval {n_ev_text}/{len(text_ev)} "
          f"({100 * n_ev_text / max(len(text_ev), 1):.1f}%)", flush=True)

    return {
        "truth": truth, "pids_d": pids_d, "emb_d": emb_d, "split": split,
        "path_map": path_map, "text_tr": text_tr, "text_ev": text_ev,
    }


# ----------------------------------------------------------------------------
# TASK 2 -- threshold / PR table for the rung-2 winner
# ----------------------------------------------------------------------------
def task2_threshold_table(ctx):
    from sklearn.feature_extraction.text import TfidfVectorizer

    split, text_tr, text_ev = ctx["split"], ctx["text_tr"], ctx["text_ev"]
    cat_tr, keep_tr = split["cat_tr"], split["keep_tr"]
    cat_ev, permit_ev = split["cat_ev"], split["permit_ev"]

    print(f"\nfitting winner (text_only TF-IDF {ts2.TFIDF_KW} + logreg "
          f"class_weight=balanced + direct_binary) on {len(text_tr)} train pages...",
          flush=True)
    vec = TfidfVectorizer(**ts2.TFIDF_KW)
    X_tr = vec.fit_transform(text_tr)
    X_ev = vec.transform(text_ev)
    print(f"TF-IDF vocab size: {len(vec.vocabulary_)}", flush=True)

    scores, note = ts2.fit_and_score(
        "logreg", "direct_binary", X_tr, cat_tr, keep_tr, X_ev, is_sparse=True)
    if scores is None:
        raise SystemExit(f"task2: degenerate fit ({note})")

    is_finish = np.isin(cat_ev, list(r1.FINISH_CATEGORIES))
    exact_full_thr = r1.full_finish_threshold(scores, is_finish)

    rows = []
    for thr in THRESHOLDS:
        overall, _packet, _ = r1.compute_metrics(scores, cat_ev, permit_ev, thr)
        pred = scores >= thr
        rows.append({
            "thr": thr,
            "finish_recall": overall["finish_recall"],
            "keep_recall": overall["keep_recall"],
            "fp_rate": overall["fp_rate"],
            "frac_kept": float(pred.mean()),
        })

    print("\n" + "=" * 78)
    print(f"TASK 2 -- threshold / PR table (n_eval={len(cat_ev)}, "
          f"finish pages in eval={int(is_finish.sum())})")
    print("=" * 78)
    print(f"{'thr':>6} {'finish_recall':>14} {'keep_recall':>12} "
          f"{'fp_rate':>9} {'frac_kept':>10}")
    for r in rows:
        print(f"{r['thr']:>6.2f} {_fmt(r['finish_recall']):>14} "
              f"{_fmt(r['keep_recall']):>12} {_fmt(r['fp_rate']):>9} "
              f"{r['frac_kept']:>10.3f}")
    print("-" * 78)

    # augment the discrete grid with the exact continuous full-recall anchor
    # point (min finish-page score) so (a)/(b) have a real answer even when no
    # *grid* threshold happens to clear the bar.
    cand_rows = list(rows)
    if exact_full_thr is not None:
        overall_x, _packet_x, _ = r1.compute_metrics(scores, cat_ev, permit_ev, exact_full_thr)
        pred_x = scores >= exact_full_thr
        cand_rows.append({
            "thr": exact_full_thr, "finish_recall": overall_x["finish_recall"],
            "keep_recall": overall_x["keep_recall"], "fp_rate": overall_x["fp_rate"],
            "frac_kept": float(pred_x.mean()), "exact": True,
        })
        anchor = cand_rows[-1]
        print(f"exact tightest threshold for finish_recall==1.0 (min finish-page "
              f"score in eval): thr={exact_full_thr:.4f} -> "
              f"finish_recall={_fmt(anchor['finish_recall'])} "
              f"keep_recall={_fmt(anchor['keep_recall'])} "
              f"fp_rate={_fmt(anchor['fp_rate'])} frac_kept={anchor['frac_kept']:.3f}")
    else:
        print("exact tightest threshold for finish_recall==1.0: NA (no finish pages in eval)")

    def best_at(min_recall):
        cands = [r for r in cand_rows
                 if r["finish_recall"] is not None and r["finish_recall"] >= min_recall - 1e-9]
        if not cands:
            return None
        best_fp = min(c["fp_rate"] for c in cands if c["fp_rate"] is not None)
        ties = [c for c in cands if c["fp_rate"] == best_fp]
        return max(ties, key=lambda c: c["thr"])  # prefer higher thr (fewer pages) on tie

    best_a = best_at(1.0)
    best_b = best_at(0.97)
    print(f"\n(a) finish_recall=1.0, lowest fp: "
          f"{best_a if best_a is None else {k: (round(v, 3) if isinstance(v, float) else v) for k, v in best_a.items()}}")
    print(f"(b) finish_recall>=0.97, lowest fp: "
          f"{best_b if best_b is None else {k: (round(v, 3) if isinstance(v, float) else v) for k, v in best_b.items()}}")
    print("=" * 78)

    return {
        "rows": rows, "exact_full_thr": exact_full_thr,
        "best_a": best_a, "best_b": best_b,
        "n_train": len(cat_tr), "n_eval": len(cat_ev),
    }


# ----------------------------------------------------------------------------
# TASK 3 -- router: text branch (has-text pages) + image branch (no-text)
# ----------------------------------------------------------------------------
def task3_router(ctx, out_csv):
    from sklearn.feature_extraction.text import TfidfVectorizer

    split = ctx["split"]
    text_tr, text_ev = ctx["text_tr"], ctx["text_ev"]
    pids_d, emb_d = ctx["pids_d"], ctx["emb_d"]
    cat_tr, keep_tr = split["cat_tr"], split["keep_tr"]
    cat_ev, permit_ev = split["cat_ev"], split["permit_ev"]
    train_ids, eval_ids = split["train_page_ids"], split["eval_page_ids"]

    has_text_tr = np.array([len(t.strip()) > 0 for t in text_tr])
    has_text_ev = np.array([len(t.strip()) > 0 for t in text_ev])
    n_tr_text, n_tr_img = int(has_text_tr.sum()), int((~has_text_tr).sum())
    n_ev_text, n_ev_img = int(has_text_ev.sum()), int((~has_text_ev).sum())
    print(f"\nrouter populations: train text={n_tr_text} img={n_tr_img}; "
          f"eval text={n_ev_text} img={n_ev_img}", flush=True)

    # ---------------- text branch ----------------
    text_tr_sub = [t for t, m in zip(text_tr, has_text_tr) if m]
    text_ev_sub = [t for t, m in zip(text_ev, has_text_ev) if m]
    cat_tr_t, keep_tr_t = cat_tr[has_text_tr], keep_tr[has_text_tr]
    cat_ev_t, permit_ev_t = cat_ev[has_text_ev], permit_ev[has_text_ev]
    ids_ev_t = eval_ids[has_text_ev]

    vec = TfidfVectorizer(**ts2.TFIDF_KW)
    Xtr_t = vec.fit_transform(text_tr_sub)
    Xev_t = vec.transform(text_ev_sub)

    is_finish_tr_t = np.isin(cat_tr_t, list(r1.FINISH_CATEGORIES))
    scores_tr_self_t, _ = ts2.fit_and_score(
        "logreg", "direct_binary", Xtr_t, cat_tr_t, keep_tr_t, Xtr_t, is_sparse=True)
    scores_ev_t, _ = ts2.fit_and_score(
        "logreg", "direct_binary", Xtr_t, cat_tr_t, keep_tr_t, Xev_t, is_sparse=True)
    thr_t = r1.full_finish_threshold(scores_tr_self_t, is_finish_tr_t)
    fallback_t = thr_t is None
    if fallback_t:
        thr_t = 0.5
    pred_t = scores_ev_t >= thr_t
    overall_t, _pkt_t, is_finish_ev_t = r1.compute_metrics(scores_ev_t, cat_ev_t, permit_ev_t, thr_t)

    # ---------------- image branch ----------------
    tr_img_ids = train_ids[~has_text_tr]
    ev_img_ids = eval_ids[~has_text_ev]
    Xtr_i = ts2.align_embeddings(pids_d, emb_d, tr_img_ids)
    Xev_i = ts2.align_embeddings(pids_d, emb_d, ev_img_ids)
    cat_tr_i, keep_tr_i = cat_tr[~has_text_tr], keep_tr[~has_text_tr]
    cat_ev_i, permit_ev_i = cat_ev[~has_text_ev], permit_ev[~has_text_ev]

    is_finish_tr_i = np.isin(cat_tr_i, list(r1.FINISH_CATEGORIES))
    scores_tr_self_i, note_i = r1.keep_scores(
        "logreg", "multiclass_collapse", Xtr_i, cat_tr_i, keep_tr_i, Xtr_i)
    fallback_i = False
    if scores_tr_self_i is None:
        print(f"[warn] image branch degenerate on train ({note_i}); "
              f"predicting 0 (discard) for all no-text eval pages", flush=True)
        thr_i = 0.5
        scores_ev_i = np.zeros(len(cat_ev_i))
        fallback_i = True
    else:
        scores_ev_i, _ = r1.keep_scores(
            "logreg", "multiclass_collapse", Xtr_i, cat_tr_i, keep_tr_i, Xev_i)
        thr_i = r1.full_finish_threshold(scores_tr_self_i, is_finish_tr_i)
        if thr_i is None:
            fallback_i = True
            thr_i = 0.5
    pred_i = scores_ev_i >= thr_i
    overall_i, _pkt_i, is_finish_ev_i = r1.compute_metrics(scores_ev_i, cat_ev_i, permit_ev_i, thr_i)

    # ---------------- combined ----------------
    combined_pred = np.empty(len(cat_ev), dtype=bool)
    combined_pred[has_text_ev] = pred_t
    combined_pred[~has_text_ev] = pred_i
    pseudo_scores = combined_pred.astype(float)
    overall_c, _pkt_c, is_finish_all = r1.compute_metrics(pseudo_scores, cat_ev, permit_ev, 0.5)

    def misses(ids, cats, permits, is_fin, pred):
        idx = np.where(is_fin & ~pred)[0]
        return [(int(ids[j]), str(cats[j]), str(permits[j])) for j in idx]

    miss_t = misses(ids_ev_t, cat_ev_t, permit_ev_t, is_finish_ev_t, pred_t)
    miss_i = misses(ev_img_ids, cat_ev_i, permit_ev_i, is_finish_ev_i, pred_i)

    print("\n" + "=" * 78)
    print("TASK 3 -- router (text branch has-text pages, image branch no-text pages)")
    print("=" * 78)
    print(f"TEXT branch : n_train={n_tr_text} n_eval={n_ev_text} thr={thr_t:.4f}"
          f"{' [FALLBACK 0.5, no finish pages in train subset]' if fallback_t else ''}\n"
          f"              finish_recall={_fmt(overall_t['finish_recall'])} "
          f"keep_recall={_fmt(overall_t['keep_recall'])} "
          f"fp_rate={_fmt(overall_t['fp_rate'])} misses={len(miss_t)}")
    print(f"IMAGE branch: n_train={n_tr_img} n_eval={n_ev_img} thr={thr_i:.4f}"
          f"{' [FALLBACK 0.5, degenerate/no finish pages in train subset]' if fallback_i else ''}\n"
          f"              finish_recall={_fmt(overall_i['finish_recall'])} "
          f"keep_recall={_fmt(overall_i['keep_recall'])} "
          f"fp_rate={_fmt(overall_i['fp_rate'])} misses={len(miss_i)}")
    print(f"\nCOMBINED    : n_eval={len(cat_ev)} "
          f"finish_recall={_fmt(overall_c['finish_recall'])} "
          f"keep_recall={_fmt(overall_c['keep_recall'])} "
          f"fp_rate={_fmt(overall_c['fp_rate'])} "
          f"total_misses={len(miss_t) + len(miss_i)}")
    if miss_t:
        print(f"  text-branch finish misses (page_id, category, permit): {miss_t}")
    if miss_i:
        print(f"  image-branch finish misses (page_id, category, permit): {miss_i}")
    print("=" * 78)

    row = {
        "run_id": "rung2b", "features": "router_v1", "backbone": f"text+{BACKBONE}",
        "head": "logreg+logreg", "task": "router",
        "n_train": len(cat_tr), "n_eval": len(cat_ev),
        "finish_recall": _fmt(overall_c["finish_recall"]),
        "keep_recall": _fmt(overall_c["keep_recall"]),
        "fp_rate": _fmt(overall_c["fp_rate"]),
        "thr_full_finish": f"text={thr_t:.4f};img={thr_i:.4f}",
        "fp_at_full_finish": _fmt(overall_c["fp_rate"]),
        "notes": (
            f"n_text_eval={n_ev_text} n_img_eval={n_ev_img} "
            f"(train: text={n_tr_text} img={n_tr_img}); "
            f"each branch trained + threshold-tuned on its OWN train-side "
            f"has-text/no-text subset (full_finish_threshold on in-sample "
            f"train scores), applied to its held-out eval subset -- no "
            f"eval-side leakage; "
            f"text_branch: fin_rec={_fmt(overall_t['finish_recall'])} "
            f"keep_rec={_fmt(overall_t['keep_recall'])} fp={_fmt(overall_t['fp_rate'])} "
            f"misses={len(miss_t)}{' [FALLBACK]' if fallback_t else ''}; "
            f"image_branch: fin_rec={_fmt(overall_i['finish_recall'])} "
            f"keep_rec={_fmt(overall_i['keep_recall'])} fp={_fmt(overall_i['fp_rate'])} "
            f"misses={len(miss_i)}{' [FALLBACK]' if fallback_i else ''}; "
            f"{split['dedup_note']}"
        ),
    }
    ts2.append_csv(out_csv, row)
    print(f"\nrouter row appended to: {out_csv}")

    return {
        "n_text_eval": n_ev_text, "n_img_eval": n_ev_img,
        "n_text_train": n_tr_text, "n_img_train": n_tr_img,
        "thr_text": thr_t, "thr_img": thr_i,
        "overall_text": overall_t, "overall_img": overall_i, "overall_combined": overall_c,
        "miss_text": miss_t, "miss_img": miss_i,
        "fallback_text": fallback_t, "fallback_img": fallback_i,
    }


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description="Rung-2b Tasks 2+3.")
    p.add_argument("--tag", default=TAG)
    p.add_argument("--backbone", default=BACKBONE)
    p.add_argument("--out", default=os.path.join(ROOT, "data", "experiments_rung2.csv"))
    p.add_argument("--skip-router", action="store_true", help="task 2 only")
    args = p.parse_args(argv)

    env = r1.load_env()
    if "NEON_DATABASE_URL" not in env:
        print("ERROR: NEON_DATABASE_URL not found in .env", file=sys.stderr)
        return 2
    db_url = env["NEON_DATABASE_URL"]

    ctx = build_context(db_url, tag=args.tag, backbone=args.backbone)
    task2_threshold_table(ctx)
    if not args.skip_router:
        task3_router(ctx, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
