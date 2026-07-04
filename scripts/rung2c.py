#!/usr/bin/env python3
"""Rung-2c, Task 2: first trustworthy leaderboard, on the FROZEN split.

Context (STATE.md "Rung-2b results" + scripts/make_split.py): every prior
rung's by-permit hash split reshuffled membership as the corpus grew, and one
run let a 1059-page whale permit land 100%-eval, collapsing
finish_recall@0.5 from 0.974 to 0.339 on identical model code -- a
split-stability bug, not a model regression. scripts/make_split.py fixed
that once, producing data/split_v1.json: a frozen permit-level train/eval
assignment (whales forced train, hash-based for the rest, floors on eval
permit count and eval finish-page count). This script retrains and
re-evaluates on THAT split, with CURRENT labels and CURRENT backfilled page
text (91% coverage per STATE.md), so the resulting numbers are finally
apples-to-apples across reruns.

Split semantics (frozen, per split_v1.json's own "rules" field): a page is
EVAL iff its permit is in split_v1.json's "eval" list; every other page --
including pages from permits labeled AFTER split_v1.json was generated -- is
TRAIN. No near-duplicate dedup is applied here (unlike rung-1/rung-2's
canonical split): the frozen split is defined purely at the permit level,
and the point of this rung is split-membership stability, not re-litigating
the dedup question.

Configs
    a. image_only : dinov2_vitb14 embeddings + logreg, multiclass_collapse.
                     Pages without a cached embedding are excluded (count
                     reported), same as every prior rung.
    b. text_only   : TF-IDF (word 1-2gram, max_features=30000, min_df=2, fit
                     on TRAIN pages only) + logreg(class_weight=balanced),
                     direct_binary -- the rung-2 winner config.
    c. router_v2   : text branch (b) for pages with non-empty extracted
                     text, image branch (a) for pages without. Each branch's
                     deployed threshold is tuned on that branch's OWN
                     TRAIN-side scores only (full_finish_threshold: the
                     tightest cut that still catches every finish page in
                     the branch's train subset) -- never picked from eval,
                     so eval numbers are a genuine generalization test.
                     Pages with neither text nor a cached embedding (can't
                     be scored by either branch) are conservatively always
                     predicted KEEP.

For each config this prints/reports:
    - finish_recall / keep_recall / fp_rate @ threshold 0.5
    - a full threshold table over {0.9 .. 0.02}
    - the exact full-finish-recall operating point (thr, fp_rate, frac_kept)
    - a per-eval-permit ("per-packet") finish-recall table

Reuse policy: imports (does not copy or modify) train_sweep_opus.py (r1:
build_truth_table, load_embeddings, keep_scores, compute_metrics,
full_finish_threshold, FINISH_CATEGORIES, KEEP_CATEGORIES, load_env) and
train_sweep_rung2.py (ts2: load_page_paths, load_text_for_pages, TFIDF_KW,
fit_and_score, align_embeddings, append_csv, CSV_FIELDS).

Usage
    python3 scripts/rung2c.py
    python3 scripts/rung2c.py --split data/split_v1.json
"""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_sweep_opus as r1     # noqa: E402  (reuse, not modified)
import train_sweep_rung2 as ts2   # noqa: E402  (reuse, not modified)

TAG = "base2"
IMAGE_BACKBONE = "dinov2_vitb14"
THRESHOLDS = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 0.02]


def _fmt(x):
    return "NA" if x is None else f"{x:.3f}"


# ----------------------------------------------------------------------------
# Frozen split -> per-page train/eval assignment
# ----------------------------------------------------------------------------
def load_frozen_split(path):
    with open(path) as f:
        return json.load(f)


def build_frozen_ctx(db_url, split_path):
    """truth (current labels) x split_v1.json -> per-page train/eval arrays.

    A page is EVAL iff its permit is in split_json['eval']; every other page
    (including pages whose permit isn't in split_json at all, i.e. permits
    labeled after the split was frozen) defaults to TRAIN -- this is the
    "closed/frozen eval list" behavior split_v1.json's own rules mandate.
    """
    print("building truth table from Neon (schema estimate)...", flush=True)
    truth = r1.build_truth_table(db_url)  # {page_id: (category, permit)}
    keep_n = sum(1 for c, _ in truth.values() if c in r1.KEEP_CATEGORIES)
    print(f"truth: {len(truth)} labeled pages, {keep_n} keep "
          f"({100 * keep_n / max(len(truth), 1):.1f}%)", flush=True)

    split_json = load_frozen_split(split_path)
    eval_permits = set(split_json["eval"])
    frozen_train_permits = set(split_json["train"])
    print(f"frozen split ({split_json.get('version')}, seed={split_json.get('seed')}): "
          f"{len(frozen_train_permits)} train / {len(eval_permits)} eval permits "
          f"recorded in {split_path}", flush=True)

    page_ids = np.array(sorted(truth), dtype=np.int64)
    cats = np.array([truth[int(p)][0] for p in page_ids])
    permits = np.array([truth[int(p)][1] for p in page_ids])
    is_eval = np.array([p in eval_permits for p in permits])

    new_permits = sorted(set(permits.tolist()) - eval_permits - frozen_train_permits)
    if new_permits:
        new_pages = int(np.isin(permits, new_permits).sum())
        print(f"NOTE: {len(new_permits)} permit(s) labeled since split_v1.json "
              f"was frozen ({new_pages} pages) -- defaulted to TRAIN per the "
              f"frozen-eval-list rule: {new_permits}", flush=True)

    train_ids, eval_ids = page_ids[~is_eval], page_ids[is_eval]
    cat_tr, cat_ev = cats[~is_eval], cats[is_eval]
    permit_tr, permit_ev = permits[~is_eval], permits[is_eval]
    keep_tr = np.array([c in r1.KEEP_CATEGORIES for c in cat_tr]).astype(int)

    n_finish_ev = int(np.isin(cat_ev, list(r1.FINISH_CATEGORIES)).sum())
    print(f"n_train={len(train_ids)} ({len(set(permit_tr))} permits) | "
          f"n_eval={len(eval_ids)} ({len(set(permit_ev))} permits, "
          f"{n_finish_ev} finish pages) | no dedup applied (frozen split is "
          f"permit-level)", flush=True)

    path_map = ts2.load_page_paths(db_url)
    text_tr_all = ts2.load_text_for_pages(train_ids, path_map)
    text_ev_all = ts2.load_text_for_pages(eval_ids, path_map)
    n_tr_text = sum(1 for t in text_tr_all if t.strip())
    n_ev_text = sum(1 for t in text_ev_all if t.strip())
    print(f"text coverage on frozen split: train {n_tr_text}/{len(text_tr_all)} "
          f"({100 * n_tr_text / max(len(text_tr_all), 1):.1f}%), "
          f"eval {n_ev_text}/{len(text_ev_all)} "
          f"({100 * n_ev_text / max(len(text_ev_all), 1):.1f}%)", flush=True)

    pids_d, emb_d = r1.load_embeddings(TAG, IMAGE_BACKBONE)
    print(f"loaded {IMAGE_BACKBONE}: {len(pids_d)} pages x {emb_d.shape[1]} dims",
          flush=True)

    return {
        "train_ids": train_ids, "eval_ids": eval_ids,
        "cat_tr": cat_tr, "cat_ev": cat_ev,
        "permit_tr": permit_tr, "permit_ev": permit_ev,
        "keep_tr": keep_tr,
        "text_tr_all": text_tr_all, "text_ev_all": text_ev_all,
        "pids_d": pids_d, "emb_d": emb_d,
        "split_path": split_path, "split_json": split_json,
    }


# ----------------------------------------------------------------------------
# Generic reporting helpers, reused across all three configs
# ----------------------------------------------------------------------------
def threshold_table(scores, cat_ev, permit_ev, thresholds=THRESHOLDS):
    rows = []
    for thr in thresholds:
        overall, _packet, _ = r1.compute_metrics(scores, cat_ev, permit_ev, thr)
        pred = scores >= thr
        rows.append({
            "thr": thr,
            "finish_recall": overall["finish_recall"],
            "keep_recall": overall["keep_recall"],
            "fp_rate": overall["fp_rate"],
            "frac_kept": float(pred.mean()) if len(pred) else float("nan"),
        })
    return rows


def print_threshold_table(rows, n_eval, n_finish_ev, label):
    print(f"\nfull threshold table -- {label} (n_eval={n_eval}, "
          f"finish pages in eval={n_finish_ev})")
    print(f"{'thr':>6} {'finish_recall':>14} {'keep_recall':>12} "
          f"{'fp_rate':>9} {'frac_kept':>10}")
    for r in rows:
        print(f"{r['thr']:>6.2f} {_fmt(r['finish_recall']):>14} "
              f"{_fmt(r['keep_recall']):>12} {_fmt(r['fp_rate']):>9} "
              f"{r['frac_kept']:>10.3f}")


def exact_full_recall_point(scores, cat_ev, permit_ev):
    is_finish = np.isin(cat_ev, list(r1.FINISH_CATEGORIES))
    thr = r1.full_finish_threshold(scores, is_finish)
    if thr is None:
        return None
    overall, _packet, _ = r1.compute_metrics(scores, cat_ev, permit_ev, thr)
    pred = scores >= thr
    return {
        "thr": thr, "finish_recall": overall["finish_recall"],
        "keep_recall": overall["keep_recall"], "fp_rate": overall["fp_rate"],
        "frac_kept": float(pred.mean()),
    }


def per_packet_finish_recall(cat_ev, permit_ev, pred_bool):
    """{permit: {n_finish, n_caught, recall}} for eval permits with >=1
    finish page, using whatever boolean prediction array is passed in."""
    table = {}
    for permit in sorted(set(permit_ev.tolist())):
        idx = permit_ev == permit
        finish_mask = np.isin(cat_ev[idx], list(r1.FINISH_CATEGORIES))
        n_finish = int(finish_mask.sum())
        if n_finish == 0:
            continue
        n_caught = int(pred_bool[idx][finish_mask].sum())
        table[permit] = {
            "n_finish": n_finish, "n_caught": n_caught,
            "recall": n_caught / n_finish,
        }
    return table


def print_packet_table(table, label):
    print(f"\nper-packet finish recall -- {label} "
          f"({len(table)} eval permits with >=1 finish page)")
    print(f"{'permit':16} {'n_finish':>8} {'n_caught':>8} {'recall':>7}")
    for permit, d in table.items():
        print(f"{permit:16} {d['n_finish']:>8} {d['n_caught']:>8} "
              f"{d['recall']:>7.3f}")
    if table:
        full = sum(1 for d in table.values() if d["recall"] >= 1.0 - 1e-9)
        print(f"-> {full}/{len(table)} eval packets with 100% finish recall "
              f"at this operating point")


# ----------------------------------------------------------------------------
# Config (a): image_only
# ----------------------------------------------------------------------------
def run_image_only(ctx, out_csv):
    print("\n" + "=" * 88)
    print("CONFIG (a) image_only: dinov2_vitb14 + logreg, multiclass_collapse")
    print("=" * 88)

    pids_d, emb_d = ctx["pids_d"], ctx["emb_d"]
    train_ids, eval_ids = ctx["train_ids"], ctx["eval_ids"]
    emb_set = set(int(p) for p in pids_d)

    tr_has_emb = np.array([int(p) in emb_set for p in train_ids])
    ev_has_emb = np.array([int(p) in emb_set for p in eval_ids])
    n_tr_missing = int((~tr_has_emb).sum())
    n_ev_missing = int((~ev_has_emb).sum())
    print(f"pages missing a cached embedding, excluded: train={n_tr_missing} "
          f"eval={n_ev_missing}")

    tr_ids_use, ev_ids_use = train_ids[tr_has_emb], eval_ids[ev_has_emb]
    X_tr = ts2.align_embeddings(pids_d, emb_d, tr_ids_use)
    X_ev = ts2.align_embeddings(pids_d, emb_d, ev_ids_use)
    cat_tr, keep_tr = ctx["cat_tr"][tr_has_emb], ctx["keep_tr"][tr_has_emb]
    cat_ev, permit_ev = ctx["cat_ev"][ev_has_emb], ctx["permit_ev"][ev_has_emb]
    n_train, n_eval = len(cat_tr), len(cat_ev)
    n_finish_ev = int(np.isin(cat_ev, list(r1.FINISH_CATEGORIES)).sum())

    scores, note = r1.keep_scores("logreg", "multiclass_collapse", X_tr, cat_tr,
                                   keep_tr, X_ev)
    if scores is None:
        raise SystemExit(f"image_only: degenerate fit ({note})")

    overall05, _, _ = r1.compute_metrics(scores, cat_ev, permit_ev, 0.5)
    pred05 = scores >= 0.5
    print(f"\n@0.5: finish_recall={_fmt(overall05['finish_recall'])} "
          f"keep_recall={_fmt(overall05['keep_recall'])} "
          f"fp_rate={_fmt(overall05['fp_rate'])} "
          f"frac_kept={float(pred05.mean()):.3f}")

    rows = threshold_table(scores, cat_ev, permit_ev)
    print_threshold_table(rows, n_eval, n_finish_ev, "image_only")

    exact = exact_full_recall_point(scores, cat_ev, permit_ev)
    if exact:
        print(f"\nexact full-finish-recall op point: thr={exact['thr']:.4f} "
              f"finish_recall={_fmt(exact['finish_recall'])} "
              f"fp_rate={_fmt(exact['fp_rate'])} "
              f"frac_kept={exact['frac_kept']:.3f}")
    else:
        print("\nexact full-finish-recall op point: NA (no finish pages in eval)")

    pkt = per_packet_finish_recall(cat_ev, permit_ev, pred05)
    print_packet_table(pkt, "image_only @0.5")

    row = {
        "run_id": "rung2c", "features": "image_only_splitv1",
        "backbone": IMAGE_BACKBONE, "head": "logreg", "task": "multiclass_collapse",
        "n_train": n_train, "n_eval": n_eval,
        "finish_recall": _fmt(overall05["finish_recall"]),
        "keep_recall": _fmt(overall05["keep_recall"]),
        "fp_rate": _fmt(overall05["fp_rate"]),
        "thr_full_finish": _fmt(exact["thr"]) if exact else "NA",
        "fp_at_full_finish": _fmt(exact["fp_rate"]) if exact else "NA",
        "notes": (
            f"frozen split ({ctx['split_path']}); missing_embedding: "
            f"train={n_tr_missing} eval={n_ev_missing}; "
            f"frac_kept@0.5={float(pred05.mean()):.3f}; "
            f"frac_kept@full_finish={exact['frac_kept']:.3f}" if exact else "no finish pages in eval"
        ),
    }
    ts2.append_csv(out_csv, row)

    return {"name": "image_only", "n_train": n_train, "n_eval": n_eval,
            "overall05": overall05, "exact": exact, "packet": pkt,
            "frac_kept05": float(pred05.mean())}


# ----------------------------------------------------------------------------
# Config (b): text_only
# ----------------------------------------------------------------------------
def run_text_only(ctx, out_csv):
    from sklearn.feature_extraction.text import TfidfVectorizer

    print("\n" + "=" * 88)
    print("CONFIG (b) text_only: TF-IDF(1-2gram,max_features=30000,min_df=2) "
          "+ logreg(balanced), direct_binary")
    print("=" * 88)

    cat_tr, keep_tr = ctx["cat_tr"], ctx["keep_tr"]
    cat_ev, permit_ev = ctx["cat_ev"], ctx["permit_ev"]
    text_tr_all, text_ev_all = ctx["text_tr_all"], ctx["text_ev_all"]
    n_train, n_eval = len(cat_tr), len(cat_ev)
    n_finish_ev = int(np.isin(cat_ev, list(r1.FINISH_CATEGORIES)).sum())

    vec = TfidfVectorizer(**ts2.TFIDF_KW)
    X_tr = vec.fit_transform(text_tr_all)
    X_ev = vec.transform(text_ev_all)
    print(f"TF-IDF vocab size: {len(vec.vocabulary_)} (fit on {n_train} train pages)")

    scores, note = ts2.fit_and_score("logreg", "direct_binary", X_tr, cat_tr,
                                      keep_tr, X_ev, is_sparse=True)
    if scores is None:
        raise SystemExit(f"text_only: degenerate fit ({note})")

    overall05, _, _ = r1.compute_metrics(scores, cat_ev, permit_ev, 0.5)
    pred05 = scores >= 0.5
    print(f"\n@0.5: finish_recall={_fmt(overall05['finish_recall'])} "
          f"keep_recall={_fmt(overall05['keep_recall'])} "
          f"fp_rate={_fmt(overall05['fp_rate'])} "
          f"frac_kept={float(pred05.mean()):.3f}")

    rows = threshold_table(scores, cat_ev, permit_ev)
    print_threshold_table(rows, n_eval, n_finish_ev, "text_only")

    exact = exact_full_recall_point(scores, cat_ev, permit_ev)
    if exact:
        print(f"\nexact full-finish-recall op point: thr={exact['thr']:.4f} "
              f"finish_recall={_fmt(exact['finish_recall'])} "
              f"fp_rate={_fmt(exact['fp_rate'])} "
              f"frac_kept={exact['frac_kept']:.3f}")
    else:
        print("\nexact full-finish-recall op point: NA (no finish pages in eval)")

    pkt = per_packet_finish_recall(cat_ev, permit_ev, pred05)
    print_packet_table(pkt, "text_only @0.5")

    row = {
        "run_id": "rung2c", "features": "text_only_splitv1",
        "backbone": "none", "head": "logreg", "task": "direct_binary",
        "n_train": n_train, "n_eval": n_eval,
        "finish_recall": _fmt(overall05["finish_recall"]),
        "keep_recall": _fmt(overall05["keep_recall"]),
        "fp_rate": _fmt(overall05["fp_rate"]),
        "thr_full_finish": _fmt(exact["thr"]) if exact else "NA",
        "fp_at_full_finish": _fmt(exact["fp_rate"]) if exact else "NA",
        "notes": (
            f"frozen split ({ctx['split_path']}); tfidf_vocab={len(vec.vocabulary_)}; "
            f"frac_kept@0.5={float(pred05.mean()):.3f}; "
            + (f"frac_kept@full_finish={exact['frac_kept']:.3f}" if exact else "no finish pages in eval")
        ),
    }
    ts2.append_csv(out_csv, row)

    return {"name": "text_only", "n_train": n_train, "n_eval": n_eval,
            "overall05": overall05, "exact": exact, "packet": pkt,
            "frac_kept05": float(pred05.mean())}


# ----------------------------------------------------------------------------
# Config (c): router_v2
# ----------------------------------------------------------------------------
def run_router_v2(ctx, out_csv):
    from sklearn.feature_extraction.text import TfidfVectorizer

    print("\n" + "=" * 88)
    print("CONFIG (c) router_v2: text branch (has-text) + image branch "
          "(no-text), each threshold-tuned on its OWN train-side for "
          "finish_recall=1.0")
    print("=" * 88)

    train_ids, eval_ids = ctx["train_ids"], ctx["eval_ids"]
    cat_tr, keep_tr = ctx["cat_tr"], ctx["keep_tr"]
    cat_ev, permit_ev = ctx["cat_ev"], ctx["permit_ev"]
    text_tr_all, text_ev_all = ctx["text_tr_all"], ctx["text_ev_all"]
    pids_d, emb_d = ctx["pids_d"], ctx["emb_d"]
    n_train, n_eval = len(cat_tr), len(cat_ev)
    n_finish_ev = int(np.isin(cat_ev, list(r1.FINISH_CATEGORIES)).sum())

    has_text_tr = np.array([len(t.strip()) > 0 for t in text_tr_all])
    has_text_ev = np.array([len(t.strip()) > 0 for t in text_ev_all])
    emb_set = set(int(p) for p in pids_d)
    has_emb_tr = np.array([int(p) in emb_set for p in train_ids])
    has_emb_ev = np.array([int(p) in emb_set for p in eval_ids])

    text_branch_tr, text_branch_ev = has_text_tr, has_text_ev
    img_branch_tr = (~has_text_tr) & has_emb_tr
    img_branch_ev = (~has_text_ev) & has_emb_ev
    missing_both_tr = (~has_text_tr) & (~has_emb_tr)
    missing_both_ev = (~has_text_ev) & (~has_emb_ev)
    print(f"populations: train text={int(text_branch_tr.sum())} "
          f"img={int(img_branch_tr.sum())} missing_both={int(missing_both_tr.sum())} | "
          f"eval text={int(text_branch_ev.sum())} img={int(img_branch_ev.sum())} "
          f"missing_both={int(missing_both_ev.sum())} (conservative: always predicted KEEP)")

    # ---------------- text branch ----------------
    text_tr_sub = [t for t, m in zip(text_tr_all, text_branch_tr) if m]
    text_ev_sub = [t for t, m in zip(text_ev_all, text_branch_ev) if m]
    cat_tr_t, keep_tr_t = cat_tr[text_branch_tr], keep_tr[text_branch_tr]
    cat_ev_t, permit_ev_t = cat_ev[text_branch_ev], permit_ev[text_branch_ev]

    vec = TfidfVectorizer(**ts2.TFIDF_KW)
    Xtr_t = vec.fit_transform(text_tr_sub)
    Xev_t = vec.transform(text_ev_sub)
    is_finish_tr_t = np.isin(cat_tr_t, list(r1.FINISH_CATEGORIES))
    scores_tr_self_t, _ = ts2.fit_and_score(
        "logreg", "direct_binary", Xtr_t, cat_tr_t, keep_tr_t, Xtr_t, is_sparse=True)
    scores_ev_t, _ = ts2.fit_and_score(
        "logreg", "direct_binary", Xtr_t, cat_tr_t, keep_tr_t, Xev_t, is_sparse=True)
    thr_t = r1.full_finish_threshold(scores_tr_self_t, is_finish_tr_t) if scores_tr_self_t is not None else None
    fallback_t = thr_t is None
    if fallback_t:
        thr_t = 0.5
    pred_t = scores_ev_t >= thr_t
    overall_t, _, _ = r1.compute_metrics(scores_ev_t, cat_ev_t, permit_ev_t, thr_t)

    # ---------------- image branch ----------------
    tr_img_ids, ev_img_ids = train_ids[img_branch_tr], eval_ids[img_branch_ev]
    Xtr_i = ts2.align_embeddings(pids_d, emb_d, tr_img_ids)
    Xev_i = ts2.align_embeddings(pids_d, emb_d, ev_img_ids)
    cat_tr_i, keep_tr_i = cat_tr[img_branch_tr], keep_tr[img_branch_tr]
    cat_ev_i, permit_ev_i = cat_ev[img_branch_ev], permit_ev[img_branch_ev]

    scores_tr_self_i, note_i = r1.keep_scores(
        "logreg", "multiclass_collapse", Xtr_i, cat_tr_i, keep_tr_i, Xtr_i)
    fallback_i = False
    if scores_tr_self_i is None:
        print(f"[warn] image branch degenerate on train ({note_i}); predicting "
              f"0 (discard) for all no-text/has-embedding eval pages", flush=True)
        thr_i, fallback_i = 0.5, True
        scores_ev_i = np.zeros(len(cat_ev_i))
    else:
        scores_ev_i, _ = r1.keep_scores(
            "logreg", "multiclass_collapse", Xtr_i, cat_tr_i, keep_tr_i, Xev_i)
        thr_i = r1.full_finish_threshold(scores_tr_self_i, np.isin(cat_tr_i, list(r1.FINISH_CATEGORIES)))
        if thr_i is None:
            fallback_i, thr_i = True, 0.5
    pred_i = scores_ev_i >= thr_i
    overall_i, _, _ = r1.compute_metrics(scores_ev_i, cat_ev_i, permit_ev_i, thr_i)

    # ---------------- combined (canonical, per-branch-tuned) operating point --
    combined_pred = np.empty(len(cat_ev), dtype=bool)
    combined_pred[text_branch_ev] = pred_t
    combined_pred[img_branch_ev] = pred_i
    combined_pred[missing_both_ev] = True  # conservative: can't be scored -> keep
    overall_c, _, _ = r1.compute_metrics(combined_pred.astype(float), cat_ev, permit_ev, 0.5)
    frac_kept_c = float(combined_pred.mean())

    print(f"\nTEXT branch : n_train={int(text_branch_tr.sum())} n_eval={int(text_branch_ev.sum())} "
          f"thr={thr_t:.4f}{' [FALLBACK 0.5]' if fallback_t else ''} "
          f"finish_recall={_fmt(overall_t['finish_recall'])} fp_rate={_fmt(overall_t['fp_rate'])}")
    print(f"IMAGE branch: n_train={int(img_branch_tr.sum())} n_eval={int(img_branch_ev.sum())} "
          f"thr={thr_i:.4f}{' [FALLBACK 0.5]' if fallback_i else ''} "
          f"finish_recall={_fmt(overall_i['finish_recall'])} fp_rate={_fmt(overall_i['fp_rate'])}")
    print(f"\nCOMBINED (canonical op point, per-branch train-tuned thresholds): "
          f"finish_recall={_fmt(overall_c['finish_recall'])} "
          f"keep_recall={_fmt(overall_c['keep_recall'])} "
          f"fp_rate={_fmt(overall_c['fp_rate'])} frac_kept={frac_kept_c:.3f}")

    # ---------------- "at 0.5" + full threshold table: SHARED grid threshold
    # applied to both branches (missing-both always kept regardless of thr,
    # via a sentinel score above the whole grid). This answers "what if we
    # used one global cutoff for both branches", distinct from the canonical
    # per-branch-tuned deployment point above. ---------------------------
    combined_scores = np.empty(len(cat_ev), dtype=float)
    combined_scores[text_branch_ev] = scores_ev_t
    combined_scores[img_branch_ev] = scores_ev_i
    combined_scores[missing_both_ev] = 2.0  # always kept, above any grid thr

    rows = threshold_table(combined_scores, cat_ev, permit_ev)
    row05 = next(r for r in rows if r["thr"] == 0.5)
    print(f"\n@0.5 (shared threshold applied to both branches): "
          f"finish_recall={_fmt(row05['finish_recall'])} "
          f"keep_recall={_fmt(row05['keep_recall'])} "
          f"fp_rate={_fmt(row05['fp_rate'])} frac_kept={row05['frac_kept']:.3f}")
    print_threshold_table(rows, n_eval, n_finish_ev,
                           "router_v2 (shared threshold across both branches)")

    exact_shared = exact_full_recall_point(combined_scores, cat_ev, permit_ev)
    print(f"\nexact full-finish-recall op point [CANONICAL, per-branch-tuned -- "
          f"THIS is the router's actual deployed config per the task spec]: "
          f"thr=text:{thr_t:.4f};img:{thr_i:.4f} "
          f"finish_recall={_fmt(overall_c['finish_recall'])} "
          f"fp_rate={_fmt(overall_c['fp_rate'])} frac_kept={frac_kept_c:.3f} "
          f"{'*** DOES NOT REACH finish_recall=1.0 -- generalization gap ***' if (overall_c['finish_recall'] or 0) < 1.0 else ''}")
    if exact_shared:
        print(f"exact full-finish-recall op point [shared-threshold variant, "
              f"parallel to (a)/(b)'s eval-fit convention -- NOT how the "
              f"router is actually deployed]: thr={exact_shared['thr']:.4f} "
              f"finish_recall={_fmt(exact_shared['finish_recall'])} "
              f"fp_rate={_fmt(exact_shared['fp_rate'])} "
              f"frac_kept={exact_shared['frac_kept']:.3f}")

    pkt = per_packet_finish_recall(cat_ev, permit_ev, combined_pred)
    print_packet_table(pkt, "router_v2 @ canonical per-branch-tuned op point")

    # CSV columns kept PARALLEL to (a)/(b): finish_recall/keep_recall/fp_rate
    # = the shared-threshold @0.5 headline (row05); thr_full_finish/
    # fp_at_full_finish = the shared-threshold exact full-recall point
    # (exact_shared) -- both computed off the SAME combined_scores array used
    # for (a)/(b), so the CSV is apples-to-apples across all three rows. The
    # router's actual DESIGNED/deployed operating point (each branch's own
    # train-tuned threshold, per the task spec) is the "canonical" numbers
    # above -- notably finish_recall=0.267, NOT 1.0 -- recorded in notes
    # since it is the single most important finding of this config and does
    # not fit the a/b-parallel column schema.
    row = {
        "run_id": "rung2c", "features": "router_v2_splitv1",
        "backbone": f"text+{IMAGE_BACKBONE}", "head": "logreg+logreg", "task": "router",
        "n_train": n_train, "n_eval": n_eval,
        "finish_recall": _fmt(row05["finish_recall"]),
        "keep_recall": _fmt(row05["keep_recall"]),
        "fp_rate": _fmt(row05["fp_rate"]),
        "thr_full_finish": _fmt(exact_shared["thr"]) if exact_shared else "NA",
        "fp_at_full_finish": _fmt(exact_shared["fp_rate"]) if exact_shared else "NA",
        "notes": (
            f"frozen split ({ctx['split_path']}); finish_recall/keep_recall/"
            f"fp_rate/thr_full_finish here use a SHARED threshold across both "
            f"branches (parallel to a/b's columns); n_missing_both_eval="
            f"{int(missing_both_ev.sum())} (conservative always-keep); "
            f"CANONICAL deployed router (each branch's OWN train-tuned "
            f"full_finish_threshold, no eval leakage, per task spec): "
            f"thr=text:{thr_t:.4f}{'[FALLBACK]' if fallback_t else ''};"
            f"img:{thr_i:.4f}{'[FALLBACK]' if fallback_i else ''} -> "
            f"finish_recall={_fmt(overall_c['finish_recall'])} "
            f"keep_recall={_fmt(overall_c['keep_recall'])} "
            f"fp_rate={_fmt(overall_c['fp_rate'])} frac_kept={frac_kept_c:.3f} "
            f"(DOES NOT reach 1.0 -- text_branch fin_rec="
            f"{_fmt(overall_t['finish_recall'])} fp={_fmt(overall_t['fp_rate'])}, "
            f"image_branch fin_rec={_fmt(overall_i['finish_recall'])} "
            f"fp={_fmt(overall_i['fp_rate'])})"
        ),
    }
    ts2.append_csv(out_csv, row)

    return {"name": "router_v2", "n_train": n_train, "n_eval": n_eval,
            "overall05": row05, "exact": exact_shared or {
                "thr": float("nan"), "finish_recall": None, "fp_rate": None,
                "frac_kept": float("nan"),
            },
            "packet": pkt, "frac_kept05": row05["frac_kept"],
            "canonical_overall": overall_c,
            "canonical_thr": f"text={thr_t:.4f};img={thr_i:.4f}",
            "canonical_frac_kept": frac_kept_c}


# ----------------------------------------------------------------------------
# Leaderboard
# ----------------------------------------------------------------------------
def print_leaderboard(results):
    print("\n" + "=" * 96)
    print("RUNG-2C LEADERBOARD (frozen split_v1) -- @0.5 headline, then exact "
          "full-finish-recall operating point")
    print("=" * 96)
    print(f"{'config':16} {'n_train':>8} {'n_eval':>7} {'fin_rec@0.5':>11} "
          f"{'fp@0.5':>7} | {'full-recall thr':>18} {'fp@full':>8} {'frac_kept':>9}")
    for r in results:
        o5 = r["overall05"]
        ex = r["exact"]
        thr_disp = ex["thr"] if isinstance(ex["thr"], str) else f"{ex['thr']:.4f}"
        print(f"{r['name']:16} {r['n_train']:>8} {r['n_eval']:>7} "
              f"{_fmt(o5['finish_recall']):>11} {_fmt(o5['fp_rate']):>7} | "
              f"{thr_disp:>18} {_fmt(ex['fp_rate']):>8} {ex['frac_kept']:>9.3f}")
    print("=" * 96)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description="Rung-2c: leaderboard on the frozen split_v1.")
    p.add_argument("--split", default=os.path.join(ROOT, "data", "split_v1.json"))
    p.add_argument("--out", default=os.path.join(ROOT, "data", "experiments_rung2.csv"))
    args = p.parse_args(argv)

    env = r1.load_env()
    if "NEON_DATABASE_URL" not in env:
        print("ERROR: NEON_DATABASE_URL not found in .env", file=sys.stderr)
        return 2
    db_url = env["NEON_DATABASE_URL"]

    ctx = build_frozen_ctx(db_url, args.split)

    results = [
        run_image_only(ctx, args.out),
        run_text_only(ctx, args.out),
        run_router_v2(ctx, args.out),
    ]
    print_leaderboard(results)
    print(f"\nrows appended to: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
