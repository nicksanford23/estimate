#!/usr/bin/env python3
"""Model-1 rung-1 embedding sweep (Opus parallel implementation).

Trains cheap heads on top of cached page embeddings and evaluates them on the
benchmark that actually matters for flooring takeoffs: per-plan-set recall of
"keep" pages, with a hard eye on never missing finish_plan / finish_schedule.

Bake-off grid  =  backbone x head x task
    backbones : clip_vitl14, siglip_b16, dinov2_vitb14   (cached .npz files)
    heads     : logreg, mlp (256 hidden), xgboost
    tasks     : multiclass_collapse (predict category, sum keep-class prob)
                direct_binary       (predict keep directly)

Data flow
    embeddings : data/embeddings/<tag>_<backbone>.npz  (emb float16 [N,D], page_id [N])
    truth      : Neon Postgres, schema `estimate`  (latest label per page,
                 source-priority resolved; keep DERIVED from category)
    split      : BY PERMIT, ~80/20, fixed seed 42  (never by page or document)
    dedup      : cosine > 0.98 within each backbone => one eval representative
                 per duplicate group; train keeps all copies (counts noted)

Output
    one CSV row per experiment -> data/experiments_opus.csv
    a ranked leaderboard (finish_recall desc, then fp_rate asc) to stdout

This script does NOT run unless embeddings exist; a missing .npz yields a clear
error. Use `--self-test` to exercise the whole pipeline on synthetic data
(no DB, no GPU, no embeddings) for a fast smoke test.

Usage
    python3 scripts/train_sweep_opus.py                       # tag=base2, full grid
    python3 scripts/train_sweep_opus.py --tag base2
    python3 scripts/train_sweep_opus.py --backbones clip_vitl14 --heads logreg
    python3 scripts/train_sweep_opus.py --self-test           # offline smoke test
"""
import argparse
import csv
import datetime as dt
import os
import sys
import tempfile
import warnings

import numpy as np

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BACKBONES = ["clip_vitl14", "siglip_b16", "dinov2_vitb14"]
HEADS = ["logreg", "mlp", "xgboost"]
TASKS = ["multiclass_collapse", "direct_binary"]

# keep is DERIVED, never hand-labeled (CLAUDE.md / PLAN.md).
KEEP_CATEGORIES = {"floor_plan", "finish_plan", "finish_schedule", "demo_plan"}
# The must-not-miss classes: the benchmark demands zero missed finishes.
FINISH_CATEGORIES = {"finish_plan", "finish_schedule"}
FLOORDEMO_CATEGORIES = {"floor_plan", "demo_plan"}

# Label source priority: later (more authoritative) sources win. Pilot rows
# ('claude-code-pilot') count the same as ordinary 'claude-code'.
SOURCE_PRIORITY = {
    "human": 4,
    "claude-code-adjudicate": 3,
    "claude-code-review": 2,
    "claude-code": 1,
    "claude-code-pilot": 1,
}

SEED = 42
DEDUP_THRESHOLD = 0.98
TRAIN_FRACTION = 0.80

CSV_FIELDS = [
    "timestamp", "tag", "backbone", "head", "task",
    "n_train", "n_eval", "finish_recall", "keep_recall", "fp_rate",
    "threshold_for_full_finish_recall", "notes",
]


# ----------------------------------------------------------------------------
# Environment / database
# ----------------------------------------------------------------------------
def load_env():
    """Parse .env into a dict (same convention as the other repo scripts)."""
    env = {}
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def build_truth_table(database_url):
    """Return {page_id(int): (category, permit_num)} — latest label per page.

    Resolution order per page: highest SOURCE_PRIORITY, then latest created_at,
    then highest row id (append-only => higher id = later). keep is derived
    downstream from the category, never read from the DB.
    """
    import psycopg2  # imported lazily so --self-test needs no DB driver at call

    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(
            """
            SELECT pl.page_id, pl.source, pl.category, pl.created_at, pl.id,
                   d.permit_num
            FROM page_label pl
            JOIN page      p ON p.id = pl.page_id
            JOIN document  d ON d.id = p.document_id
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    best = {}  # page_id -> (priority, created_at, id, category, permit_num)
    for page_id, source, category, created_at, row_id, permit_num in rows:
        pri = SOURCE_PRIORITY.get(source, 0)
        key = (pri, str(created_at), int(row_id))
        cur_best = best.get(page_id)
        if cur_best is None or key > cur_best[0]:
            best[page_id] = (key, category, permit_num)

    truth = {int(pid): (cat, permit) for pid, (_, cat, permit) in best.items()}
    return truth


# ----------------------------------------------------------------------------
# Embeddings
# ----------------------------------------------------------------------------
def load_embeddings(tag, backbone):
    """Load one backbone's cached embeddings.

    Returns (page_ids: int64[N], emb: float32[N, D]).
    Raises FileNotFoundError with a clear, actionable message if absent.
    """
    path = os.path.join(ROOT, "data", "embeddings", f"{tag}_{backbone}.npz")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"missing embeddings file: {path}\n"
            f"  Expected data/embeddings/{tag}_{backbone}.npz produced by the "
            f"RunPod embed run (scripts/embed_gpu.py). If the GPU job has not "
            f"landed yet, wait for it or re-run the embed step, then retry."
        )
    with np.load(path) as z:
        if "emb" not in z or "page_id" not in z:
            raise ValueError(
                f"{path} is missing required arrays 'emb' and/or 'page_id' "
                f"(found: {list(z.keys())})"
            )
        emb = np.asarray(z["emb"], dtype=np.float32)
        # page_id is written from csv.reader string cells in embed_remote.sh,
        # so the array is string dtype -> cast to int explicitly.
        page_ids = np.asarray(z["page_id"]).astype(np.int64)
    if emb.shape[0] != page_ids.shape[0]:
        raise ValueError(
            f"{path}: emb rows ({emb.shape[0]}) != page_id length "
            f"({page_ids.shape[0]})"
        )
    return page_ids, emb


# ----------------------------------------------------------------------------
# Dedup (near-duplicate pages via cosine similarity, within a backbone)
# ----------------------------------------------------------------------------
def dedup_groups(page_ids, emb, threshold=DEDUP_THRESHOLD):
    """Greedy near-duplicate grouping ordered by ascending page_id.

    A page joins the group of the earliest already-seen representative it is
    > `threshold` cosine-similar to; otherwise it starts a new group. Returns an
    int array `group_of` (one group id per input row) aligned to `page_ids`.
    """
    n = len(page_ids)
    group_of = np.full(n, -1, dtype=np.int64)
    if n == 0:
        return group_of

    # unit-normalize rows so a dot product is cosine similarity
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = emb / norms

    order = np.argsort(page_ids, kind="stable")
    reps = np.empty((n, emb.shape[1]), dtype=np.float32)  # representative vecs
    rep_group = np.empty(n, dtype=np.int64)               # group id of each rep
    n_reps = 0
    next_gid = 0
    for pos in order:
        if n_reps:
            sims = reps[:n_reps] @ unit[pos]
            j = int(np.argmax(sims))
            if sims[j] > threshold:
                group_of[pos] = rep_group[j]
                continue
        group_of[pos] = next_gid
        reps[n_reps] = unit[pos]
        rep_group[n_reps] = next_gid
        n_reps += 1
        next_gid += 1
    return group_of


def eval_representative_mask(page_ids, group_of, is_eval):
    """Boolean mask over rows: True iff this page is the eval representative of
    its duplicate group (earliest-id eval page in the group). Non-eval pages
    are always False."""
    keep = np.zeros(len(page_ids), dtype=bool)
    seen = set()
    order = np.argsort(page_ids, kind="stable")
    for pos in order:
        if not is_eval[pos]:
            continue
        g = group_of[pos]
        if g not in seen:
            seen.add(g)
            keep[pos] = True
    return keep


# ----------------------------------------------------------------------------
# Split BY PERMIT
# ----------------------------------------------------------------------------
def split_permits(permits, seed=SEED, train_fraction=TRAIN_FRACTION):
    """Deterministic ~80/20 split over unique permits. Returns (train, eval)
    as sets. Guarantees a non-empty eval side when >=2 permits exist."""
    uniq = sorted(set(permits))
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    n_train = int(round(train_fraction * len(uniq)))
    n_train = min(n_train, len(uniq) - 1) if len(uniq) >= 2 else len(uniq)
    return set(uniq[:n_train]), set(uniq[n_train:])


# ----------------------------------------------------------------------------
# Heads: return per-eval-page "keep" scores in [0, 1]
# ----------------------------------------------------------------------------
def keep_scores(head, task, X_tr, cat_tr, keep_tr, X_ev):
    """Fit `head` on train, return keep-probability for each eval row.

    task == 'direct_binary'       -> predict keep in {0,1}, score = P(keep)
    task == 'multiclass_collapse' -> predict category, score = sum of P over
                                     keep-class columns
    Returns (scores, extra_note). scores is None if the head cannot be fit
    (degenerate single-class train), with a reason in extra_note.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import LabelEncoder, StandardScaler

    def sklearn_estimator(balanced):
        if head == "logreg":
            clf = LogisticRegression(
                max_iter=2000,
                C=1.0,
                class_weight="balanced" if balanced else None,
            )
            return make_pipeline(StandardScaler(), clf)
        if head == "mlp":
            clf = MLPClassifier(
                hidden_layer_sizes=(256,),
                max_iter=300,
                early_stopping=False,
                random_state=SEED,
            )
            return make_pipeline(StandardScaler(), clf)
        raise ValueError(head)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # convergence / undefined-metric noise

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
            est = sklearn_estimator(balanced=True)
            est.fit(X_tr, keep_tr)
            proba = est.predict_proba(X_ev)
            col = list(est.classes_).index(1)
            return proba[:, col], ""

        # multiclass_collapse
        if len(np.unique(cat_tr)) < 2:
            return None, "degenerate: train has a single category"
        enc = LabelEncoder()
        y = enc.fit_transform(cat_tr)
        keep_cols = [i for i, c in enumerate(enc.classes_) if c in KEEP_CATEGORIES]
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
            est = sklearn_estimator(balanced=True)
            est.fit(X_tr, y)
            proba = est.predict_proba(X_ev)
        # sklearn/xgb order proba columns by sorted class id == encoder order
        scores = proba[:, keep_cols].sum(axis=1)
        return scores, ""


# ----------------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------------
def _recall(mask_pos, pred_keep):
    """Recall over the positive subset defined by mask_pos."""
    n = int(mask_pos.sum())
    if n == 0:
        return None
    return float(pred_keep[mask_pos].sum()) / n


def _fp_rate(is_keep, pred_keep):
    neg = ~is_keep
    n = int(neg.sum())
    if n == 0:
        return None
    return float(pred_keep[neg].sum()) / n


def _precision(is_keep, pred_keep):
    pk = int(pred_keep.sum())
    if pk == 0:
        return None
    return float((pred_keep & is_keep).sum()) / pk


def compute_metrics(scores, cats, permits, threshold=0.5):
    """Overall (micro) and per-packet (macro over eval permits) metrics."""
    is_keep = np.array([c in KEEP_CATEGORIES for c in cats])
    is_finish = np.array([c in FINISH_CATEGORIES for c in cats])
    is_floordemo = np.array([c in FLOORDEMO_CATEGORIES for c in cats])
    pred = scores >= threshold

    overall = {
        "finish_recall": _recall(is_finish, pred),
        "floordemo_recall": _recall(is_floordemo, pred),
        "keep_recall": _recall(is_keep, pred),
        "fp_rate": _fp_rate(is_keep, pred),
        "keep_precision": _precision(is_keep, pred),
    }

    # per-packet: average the metric across permits that have the denominator
    fin_r, fd_r, fp_r = [], [], []
    for pm in set(permits):
        sel = permits == pm
        r = _recall(is_finish & sel, pred)
        if r is not None:
            fin_r.append(r)
        r = _recall(is_floordemo & sel, pred)
        if r is not None:
            fd_r.append(r)
        r = _fp_rate(is_keep[sel], pred[sel])
        if r is not None:
            fp_r.append(r)
    packet = {
        "finish_recall": float(np.mean(fin_r)) if fin_r else None,
        "floordemo_recall": float(np.mean(fd_r)) if fd_r else None,
        "fp_rate": float(np.mean(fp_r)) if fp_r else None,
    }
    return overall, packet, is_finish


def full_finish_threshold(scores, is_finish):
    """Largest threshold at which ALL finish pages are kept == min finish
    score. None if there are no finish pages in eval."""
    if int(is_finish.sum()) == 0:
        return None
    return float(scores[is_finish].min())


# ----------------------------------------------------------------------------
# One experiment
# ----------------------------------------------------------------------------
def _fmt(x):
    return "NA" if x is None else f"{x:.3f}"


def run_experiment(tag, backbone, head, task, data, out_csv):
    """Run one (backbone, head, task) cell; append a CSV row; return a result
    dict for the leaderboard."""
    X_tr, cat_tr, keep_tr = data["X_tr"], data["cat_tr"], data["keep_tr"]
    X_ev, cat_ev, permit_ev = data["X_ev"], data["cat_ev"], data["permit_ev"]
    n_train, n_eval = len(cat_tr), len(cat_ev)

    scores, degen = keep_scores(head, task, X_tr, cat_tr, keep_tr, X_ev)

    row = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "tag": tag, "backbone": backbone, "head": head, "task": task,
        "n_train": n_train, "n_eval": n_eval,
    }

    if scores is None or n_eval == 0:
        note = degen or "no eval pages"
        row.update({
            "finish_recall": "", "keep_recall": "", "fp_rate": "",
            "threshold_for_full_finish_recall": "",
            "notes": f"{note}; {data['dedup_note']}",
        })
        append_csv(out_csv, row)
        return {
            "backbone": backbone, "head": head, "task": task,
            "finish_recall": None, "fp_rate": None, "note": note,
        }

    overall, packet, is_finish = compute_metrics(scores, cat_ev, permit_ev, 0.5)
    thr_full = full_finish_threshold(scores, is_finish)

    # operating point where every finish page is caught
    if thr_full is not None:
        of, pf, _ = compute_metrics(scores, cat_ev, permit_ev, thr_full)
        full_note = (f"@fullfin(thr={thr_full:.3f}): "
                     f"kr={_fmt(of['keep_recall'])} fp={_fmt(of['fp_rate'])} "
                     f"kp={_fmt(of['keep_precision'])}")
    else:
        full_note = "no finish pages in eval"

    notes = (
        f"{full_note}; "
        f"pkt@0.5: fin_rec={_fmt(packet['finish_recall'])} "
        f"flrdemo_rec={_fmt(packet['floordemo_recall'])} "
        f"fp={_fmt(packet['fp_rate'])}; "
        f"kp@0.5={_fmt(overall['keep_precision'])} "
        f"flrdemo_rec@0.5={_fmt(overall['floordemo_recall'])}; "
        f"{data['dedup_note']}"
    )

    row.update({
        "finish_recall": _fmt(overall["finish_recall"]),
        "keep_recall": _fmt(overall["keep_recall"]),
        "fp_rate": _fmt(overall["fp_rate"]),
        "threshold_for_full_finish_recall": _fmt(thr_full),
        "notes": notes,
    })
    append_csv(out_csv, row)

    print(f"  {backbone:14s} {head:8s} {task:19s} | "
          f"fin_rec@0.5={_fmt(overall['finish_recall'])} "
          f"keep_rec@0.5={_fmt(overall['keep_recall'])} "
          f"fp@0.5={_fmt(overall['fp_rate'])} | {full_note}", flush=True)

    return {
        "backbone": backbone, "head": head, "task": task,
        "finish_recall": overall["finish_recall"], "fp_rate": overall["fp_rate"],
        "note": full_note,
    }


def append_csv(out_csv, row):
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    is_new = not os.path.exists(out_csv)
    with open(out_csv, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new:
            w.writeheader()
        w.writerow(row)


# ----------------------------------------------------------------------------
# Assemble per-backbone train/eval matrices, then run the head x task grid
# ----------------------------------------------------------------------------
def prepare_backbone_data(page_ids, emb, truth, train_permits, eval_permits,
                          dedup_threshold):
    """Intersect embeddings with truth, split by permit, dedup eval reps.
    Returns the matrices dict consumed by run_experiment, or None if unusable."""
    keep_row = np.array([pid in truth for pid in page_ids])
    if not keep_row.any():
        return None
    page_ids = page_ids[keep_row]
    emb = emb[keep_row]
    cats = np.array([truth[int(pid)][0] for pid in page_ids])
    permits = np.array([truth[int(pid)][1] for pid in page_ids])
    keeps = np.array([c in KEEP_CATEGORIES for c in cats]).astype(int)

    is_train = np.array([p in train_permits for p in permits])
    is_eval = np.array([p in eval_permits for p in permits])

    group_of = dedup_groups(page_ids, emb, dedup_threshold)
    eval_rep = eval_representative_mask(page_ids, group_of, is_eval)

    n_eval_all = int(is_eval.sum())
    n_eval_rep = int(eval_rep.sum())
    n_groups = len(set(group_of.tolist()))
    dedup_note = (f"dedup(thr={dedup_threshold}): eval {n_eval_all}->{n_eval_rep} "
                  f"reps ({n_eval_all - n_eval_rep} dups dropped), "
                  f"{n_groups} groups over {len(page_ids)} pages")

    return {
        "X_tr": emb[is_train], "cat_tr": cats[is_train], "keep_tr": keeps[is_train],
        "X_ev": emb[eval_rep], "cat_ev": cats[eval_rep],
        "permit_ev": permits[eval_rep],
        "dedup_note": dedup_note,
    }


def run_sweep(embeddings, truth, tag, out_csv, backbones, heads, tasks,
              seed=SEED, dedup_threshold=DEDUP_THRESHOLD):
    """Drive the full grid. `embeddings` is {backbone: (page_ids, emb)}."""
    # Permit split is GLOBAL (same across backbones) so results are comparable.
    usable_pids = set()
    for pids, _ in embeddings.values():
        usable_pids.update(int(p) for p in pids)
    permits_present = sorted({truth[p][1] for p in usable_pids if p in truth})
    if len(permits_present) < 2:
        raise SystemExit(
            f"need >=2 labeled permits with embeddings to split; "
            f"found {len(permits_present)}"
        )
    train_permits, eval_permits = split_permits(permits_present, seed)
    print(f"split by permit (seed={seed}): "
          f"{len(train_permits)} train / {len(eval_permits)} eval permits, "
          f"{len(permits_present)} total", flush=True)

    results = []
    for backbone in backbones:
        if backbone not in embeddings:
            print(f"[skip] {backbone}: no embeddings loaded", flush=True)
            continue
        pids, emb = embeddings[backbone]
        data = prepare_backbone_data(pids, emb, truth, train_permits,
                                     eval_permits, dedup_threshold)
        if data is None:
            print(f"[skip] {backbone}: no pages intersect truth", flush=True)
            continue
        print(f"\n[{backbone}] train={len(data['cat_tr'])} "
              f"eval={len(data['cat_ev'])} | {data['dedup_note']}", flush=True)
        for head in heads:
            for task in tasks:
                results.append(run_experiment(tag, backbone, head, task,
                                              data, out_csv))
    print_leaderboard(results, out_csv)
    return results


def print_leaderboard(results, out_csv):
    """Ranked by finish_recall (desc) then fp_rate (asc). None sorts last."""
    def key(r):
        fr = r["finish_recall"]
        fp = r["fp_rate"]
        return (
            0 if fr is not None else 1,
            -(fr if fr is not None else 0.0),
            fp if fp is not None else 1.0,
        )

    ranked = sorted(results, key=key)
    print("\n" + "=" * 78)
    print("LEADERBOARD  (rank by finish_recall@0.5 desc, then fp_rate asc)")
    print("=" * 78)
    print(f"{'#':>2}  {'backbone':14s} {'head':8s} {'task':19s} "
          f"{'finRec':>7} {'fpRate':>7}  note")
    print("-" * 78)
    for i, r in enumerate(ranked, 1):
        print(f"{i:>2}  {r['backbone']:14s} {r['head']:8s} {r['task']:19s} "
              f"{_fmt(r['finish_recall']):>7} {_fmt(r['fp_rate']):>7}  "
              f"{r.get('note', '')}")
    print("=" * 78)
    print(f"rows appended to: {out_csv}")


# ----------------------------------------------------------------------------
# Self-test: synthetic embeddings + truth, no DB / GPU / .npz required
# ----------------------------------------------------------------------------
def synthetic_data(seed=SEED):
    """Fabricate a small but structurally faithful dataset: multiple permits,
    16 categories, a keep-correlated signal, and injected near-duplicates."""
    rng = np.random.default_rng(seed)
    cats_all = [
        "floor_plan", "finish_plan", "finish_schedule", "demo_plan",      # keep
        "reflected_ceiling", "furniture_plan", "site_plan", "elevation_section",
        "detail", "schedule_other", "structural", "mep", "cover_index",
        "specs_notes", "life_safety", "other",                             # 16
    ]
    dim = 64
    # a "keep direction" so the head has real signal to learn
    keep_dir = rng.normal(size=dim)
    keep_dir /= np.linalg.norm(keep_dir)

    truth = {}
    pids, embs = [], []
    pid = 1000
    for permit_i in range(24):
        permit = f"P{permit_i:03d}"
        n_pages = int(rng.integers(6, 14))
        for _ in range(n_pages):
            cat = cats_all[int(rng.integers(len(cats_all)))]
            is_keep = cat in KEEP_CATEGORIES
            v = rng.normal(size=dim).astype(np.float32)
            if is_keep:
                v += 2.2 * keep_dir.astype(np.float32)
            truth[pid] = (cat, permit)
            pids.append(pid)
            embs.append(v)
            pid += 1
        # inject one near-duplicate page within this permit
        if n_pages:
            dup = embs[-1] + rng.normal(size=dim).astype(np.float32) * 0.001
            cat, _ = truth[pids[-1]]
            truth[pid] = (cat, permit)
            pids.append(pid)
            embs.append(dup)
            pid += 1

    page_ids = np.array(pids, dtype=np.int64)
    emb = np.array(embs, dtype=np.float16)  # mimic the real float16 storage
    return {"synthetic": (page_ids, emb.astype(np.float32))}, truth


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Model-1 rung-1 embedding sweep (Opus parallel impl).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--tag", default="base2", help="embedding run tag")
    p.add_argument("--backbones", nargs="+", default=BACKBONES,
                   help="subset of backbones to sweep")
    p.add_argument("--heads", nargs="+", default=HEADS, choices=HEADS,
                   help="subset of heads to sweep")
    p.add_argument("--tasks", nargs="+", default=TASKS, choices=TASKS,
                   help="subset of tasks to sweep")
    p.add_argument("--out", default=os.path.join(ROOT, "data",
                                                  "experiments_opus.csv"),
                   help="CSV to append experiment rows to")
    p.add_argument("--seed", type=int, default=SEED, help="permit-split seed")
    p.add_argument("--dedup-threshold", type=float, default=DEDUP_THRESHOLD,
                   help="cosine similarity above which pages are duplicates")
    p.add_argument("--self-test", action="store_true",
                   help="run the whole pipeline on synthetic data (no DB/GPU)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.self_test:
        print("SELF-TEST: synthetic embeddings + truth, no DB / GPU / .npz")
        embeddings, truth = synthetic_data(args.seed)
        with tempfile.TemporaryDirectory() as td:
            out_csv = os.path.join(td, "experiments_opus_selftest.csv")
            run_sweep(embeddings, truth, "selftest", out_csv,
                      backbones=["synthetic"], heads=args.heads,
                      tasks=args.tasks, seed=args.seed,
                      dedup_threshold=args.dedup_threshold)
            with open(out_csv) as f:
                n = sum(1 for _ in f) - 1
        print(f"\nSELF-TEST OK: {n} experiment rows written & leaderboard built.")
        return 0

    # --- real run: needs Neon + downloaded embeddings ---
    env = load_env()
    if "NEON_DATABASE_URL" not in env:
        print("ERROR: NEON_DATABASE_URL not found in .env", file=sys.stderr)
        return 2

    print(f"building truth table from Neon (schema estimate)...", flush=True)
    truth = build_truth_table(env["NEON_DATABASE_URL"])
    keep_n = sum(1 for c, _ in truth.values() if c in KEEP_CATEGORIES)
    print(f"truth: {len(truth)} labeled pages, {keep_n} keep "
          f"({100*keep_n/max(len(truth),1):.1f}%)", flush=True)

    embeddings = {}
    missing = []
    for backbone in args.backbones:
        try:
            embeddings[backbone] = load_embeddings(args.tag, backbone)
            n, d = embeddings[backbone][1].shape
            print(f"loaded {backbone}: {n} pages x {d} dims", flush=True)
        except FileNotFoundError as e:
            missing.append(backbone)
            print(f"[warn] {e}", file=sys.stderr)

    if not embeddings:
        print(f"\nERROR: no embeddings found for tag '{args.tag}'. "
              f"Nothing to sweep. Missing: {missing}", file=sys.stderr)
        return 1
    if missing:
        print(f"[warn] proceeding without: {missing}", file=sys.stderr)

    run_sweep(embeddings, truth, args.tag, args.out,
              backbones=[b for b in args.backbones if b in embeddings],
              heads=args.heads, tasks=args.tasks,
              seed=args.seed, dedup_threshold=args.dedup_threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
