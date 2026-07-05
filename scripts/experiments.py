#!/usr/bin/env python3
"""Consolidate the Model-1 experiment-result CSVs into one Neon table.

Across the rung ladder the sweeps wrote their results to three different CSVs
under data/ (all gitignored), with two different header shapes:

    data/experiments.csv       rung-1 Sonnet embedding sweep
    data/experiments_opus.csv  rung-1 Opus  embedding sweep
        header: timestamp,tag,backbone,head,task,n_train,n_eval,
                finish_recall,keep_recall,fp_rate,
                threshold_for_full_finish_recall,notes

    data/experiments_rung2.csv rung-2 / 2b / 2c text-feature + router sweeps
        header: run_id,features,backbone,head,task,n_train,n_eval,
                finish_recall,keep_recall,fp_rate,thr_full_finish,
                fp_at_full_finish,notes

This script folds every row from all three files into a single unified table,
estimate.experiment, so the whole Model-1 experiment log is queryable in one
place with the honest, split-frozen numbers on top.

Design notes on the unified mapping (see STATE.md for the narrative):
  - run_id      : rung-2 CSV carries it verbatim (rung2/rung2b/rung2c). The two
                  rung-1 CSVs have none, so we derive 'rung1_sonnet' /
                  'rung1_opus' from the filename.
  - features    : rung-2 CSV carries it; the rung-1 CSVs are all image-embedding
                  runs, so they map to 'image_only'.
  - tag         : only the rung-1 CSVs have it (e.g. base2); NULL for rung-2.
  - thr_full_finish : the rung-1 'threshold_for_full_finish_recall' and the
                  rung-2 'thr_full_finish' are the same quantity, merged here.
  - fp_at_full_finish : rung-2 CSV only; NULL for rung-1 rows.
  - split_version : rows whose features end in '_splitv1' ran on the FROZEN,
                  whale-safe permit split (data/split_v1.json) -> 'split_v1';
                  everything else ran on the old reshuffle-every-run seed-42
                  split -> 'seed42_canonical'. Per STATE.md the two are NOT
                  comparable: pre-split_v1 numbers were inflated by a split
                  artifact (the whale permit landing entirely in train).
  - content_hash : sha256(source_csv + '|' + raw_csv_line), UNIQUE. Re-running
                  the loader is idempotent via ON CONFLICT (content_hash).

Usage
    python3 scripts/experiments.py --init         # create the table if absent
    python3 scripts/experiments.py --load         # parse + insert (default)
    python3 scripts/experiments.py                # same as --load
    python3 scripts/experiments.py --leaderboard  # ranked, split_v1 on top
"""
import argparse
import csv
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

TABLE = "estimate.experiment"

# Per-source configuration. 'kind' selects the header shape; rung-1 files also
# supply the derived run_id (the rung-2 file reads run_id from each row).
SOURCES = [
    {"basename": "experiments.csv", "kind": "rung1", "run_id": "rung1_sonnet"},
    {"basename": "experiments_opus.csv", "kind": "rung1", "run_id": "rung1_opus"},
    {"basename": "experiments_rung2.csv", "kind": "rung2"},
]

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id                bigserial PRIMARY KEY,
    source_csv        text,
    run_id            text,
    features          text,
    tag               text,
    backbone          text,
    head              text,
    task              text,
    n_train           int,
    n_eval            int,
    finish_recall     real,
    keep_recall       real,
    fp_rate           real,
    thr_full_finish   real,
    fp_at_full_finish real,
    split_version     text,
    run_ts            timestamptz,
    notes             text,
    content_hash      text UNIQUE,
    loaded_at         timestamptz NOT NULL DEFAULT now()
);
"""

# Column order used for every INSERT (id / loaded_at are DB-generated).
INSERT_COLS = [
    "source_csv", "run_id", "features", "tag", "backbone", "head", "task",
    "n_train", "n_eval", "finish_recall", "keep_recall", "fp_rate",
    "thr_full_finish", "fp_at_full_finish", "split_version", "run_ts",
    "notes", "content_hash",
]


# ----------------------------------------------------------------------------
# Environment / database (same .env convention as the other repo scripts)
# ----------------------------------------------------------------------------
def load_env():
    """Parse .env into a dict (mirrors train_sweep_opus.load_env)."""
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


def connect():
    """psycopg2 connection with search_path pinned to our schema."""
    import psycopg2

    env = load_env()
    if "NEON_DATABASE_URL" not in env:
        print("ERROR: NEON_DATABASE_URL not found in .env", file=sys.stderr)
        sys.exit(2)
    conn = psycopg2.connect(env["NEON_DATABASE_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET search_path TO estimate, public")
    return conn


# ----------------------------------------------------------------------------
# Parsing / mapping
# ----------------------------------------------------------------------------
def _f(s):
    """CSV cell -> float, or None if blank."""
    if s is None or str(s).strip() == "":
        return None
    return float(s)


def _i(s):
    """CSV cell -> int, or None if blank."""
    if s is None or str(s).strip() == "":
        return None
    return int(float(s))


def _thr(raw, notes):
    """thr_full_finish is a scalar real, but a router row can carry a compound
    'text=..;img=..' value there. Keep the row: store NULL in the real column
    and preserve the raw string in notes so no information is lost.
    Returns (value_or_None, possibly_augmented_notes)."""
    if raw is None or str(raw).strip() == "":
        return None, notes
    try:
        return float(raw), notes
    except ValueError:
        extra = f"thr_full_finish_raw={str(raw).strip()}"
        return None, (f"{notes}; {extra}" if notes else extra)


def _parse_ts(s):
    """rung-1 timestamp -> datetime; tolerate trailing 'Z'. None if blank."""
    if s is None or str(s).strip() == "":
        return None
    import datetime as dt

    txt = str(s).strip().replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(txt)
    except ValueError:
        return str(s).strip()  # let Postgres cast the raw text as a fallback


def _split_version(features):
    """Frozen-split rows are tagged in their features name."""
    if features and features.endswith("_splitv1"):
        return "split_v1"
    return "seed42_canonical"


def _content_hash(basename, raw_line):
    payload = f"{basename}|{raw_line}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def map_row(source, header, fields, raw_line):
    """Turn one parsed CSV record into a unified estimate.experiment row dict."""
    d = dict(zip(header, fields))
    basename = source["basename"]

    if source["kind"] == "rung1":
        features = "image_only"
        thr, notes = _thr(d.get("threshold_for_full_finish_recall"),
                          d.get("notes") or None)
        row = {
            "source_csv": basename,
            "run_id": source["run_id"],
            "features": features,
            "tag": d.get("tag") or None,
            "backbone": d.get("backbone") or None,
            "head": d.get("head") or None,
            "task": d.get("task") or None,
            "n_train": _i(d.get("n_train")),
            "n_eval": _i(d.get("n_eval")),
            "finish_recall": _f(d.get("finish_recall")),
            "keep_recall": _f(d.get("keep_recall")),
            "fp_rate": _f(d.get("fp_rate")),
            "thr_full_finish": thr,
            "fp_at_full_finish": None,  # rung-1 CSVs don't carry this column
            "split_version": _split_version(features),
            "run_ts": _parse_ts(d.get("timestamp")),
            "notes": notes,
        }
    else:  # rung2
        features = d.get("features") or None
        thr, notes = _thr(d.get("thr_full_finish"), d.get("notes") or None)
        row = {
            "source_csv": basename,
            "run_id": d.get("run_id") or None,
            "features": features,
            "tag": None,  # rung-2 CSV has no tag column
            "backbone": d.get("backbone") or None,
            "head": d.get("head") or None,
            "task": d.get("task") or None,
            "n_train": _i(d.get("n_train")),
            "n_eval": _i(d.get("n_eval")),
            "finish_recall": _f(d.get("finish_recall")),
            "keep_recall": _f(d.get("keep_recall")),
            "fp_rate": _f(d.get("fp_rate")),
            "thr_full_finish": thr,
            "fp_at_full_finish": _f(d.get("fp_at_full_finish")),
            "split_version": _split_version(features),
            "run_ts": None,  # rung-2 CSV has no timestamp column
            "notes": notes,
        }

    row["content_hash"] = _content_hash(basename, raw_line)
    return row


def parse_file(source):
    """Yield (row_dict, raw_line) for each data line, plus a list of failures.

    One physical line == one CSV record for these files (no quoted newlines);
    each line is parsed on its own so the content_hash is over the literal
    raw line, keeping re-loads idempotent.
    """
    path = os.path.join(DATA_DIR, source["basename"])
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing source CSV: {path}")

    with open(path, newline="", encoding="utf-8") as f:
        raw_lines = f.read().splitlines()
    if not raw_lines:
        return [], []

    header = next(csv.reader([raw_lines[0]]))
    rows, failures = [], []
    for raw in raw_lines[1:]:
        if raw.strip() == "":
            continue
        try:
            fields = next(csv.reader([raw]))
            if len(fields) != len(header):
                raise ValueError(
                    f"expected {len(header)} fields, got {len(fields)}"
                )
            rows.append((map_row(source, header, fields, raw), raw))
        except Exception as e:  # noqa: BLE001 - record and keep going
            failures.append((raw, str(e)))
    return rows, failures


# ----------------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------------
def init_table(conn):
    cur = conn.cursor()
    cur.execute(DDL)
    print(f"table {TABLE} ready (CREATE TABLE IF NOT EXISTS).")


def load(conn):
    init_table(conn)  # safe/idempotent; --load works on a fresh DB
    cur = conn.cursor()
    placeholders = ", ".join(["%s"] * len(INSERT_COLS))
    sql = (
        f"INSERT INTO {TABLE} ({', '.join(INSERT_COLS)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (content_hash) DO NOTHING"
    )

    grand_ins = grand_skip = grand_fail = 0
    for source in SOURCES:
        rows, failures = parse_file(source)
        inserted = skipped = 0
        for row, _raw in rows:
            cur.execute(sql, [row[c] for c in INSERT_COLS])
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
        for raw, err in failures:
            print(f"  [PARSE FAIL] {source['basename']}: {err} :: {raw}",
                  file=sys.stderr)
        print(f"{source['basename']:26s}  inserted={inserted:3d}  "
              f"skipped={skipped:3d}  parse_failed={len(failures)}")
        grand_ins += inserted
        grand_skip += skipped
        grand_fail += len(failures)

    cur.execute(f"SELECT count(*) FROM {TABLE}")
    total = cur.fetchone()[0]
    print(f"{'TOTAL':26s}  inserted={grand_ins:3d}  skipped={grand_skip:3d}  "
          f"parse_failed={grand_fail}")
    print(f"rows now in {TABLE}: {total}")


def leaderboard(conn, top_n=None):
    """Ranked so the honest frozen-split numbers sit at the top: split_v1
    first, then finish_recall desc, then fp_rate asc."""
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT run_id, features, backbone, head, task, split_version,
               n_train, n_eval, finish_recall, fp_rate,
               thr_full_finish, fp_at_full_finish
        FROM {TABLE}
        ORDER BY (split_version = 'split_v1') DESC,
                 finish_recall DESC NULLS LAST,
                 fp_rate ASC NULLS LAST
        """
    )
    rows = cur.fetchall()
    if top_n:
        rows = rows[:top_n]

    def fmt(x):
        return "  NA " if x is None else f"{x:5.3f}"

    print("=" * 118)
    print("LEADERBOARD  estimate.experiment  "
          "(split_v1 first, then finish_recall desc, then fp_rate asc)")
    print("=" * 118)
    print(f"{'#':>2}  {'run_id':13s} {'features':24s} {'head':13s} "
          f"{'task':19s} {'split':16s} {'finRec':>6} {'fp':>6} "
          f"{'thrFull':>7} {'fpFull':>6}")
    print("-" * 118)
    for i, r in enumerate(rows, 1):
        (run_id, features, backbone, head, task, split_version,
         n_tr, n_ev, fr, fp, thr, fpf) = r
        print(f"{i:>2}  {str(run_id):13s} {str(features):24s} {str(head):13s} "
              f"{str(task):19s} {str(split_version):16s} "
              f"{fmt(fr):>6} {fmt(fp):>6} {fmt(thr):>7} {fmt(fpf):>6}")
    print("=" * 118)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Consolidate Model-1 experiment CSVs into estimate.experiment.",
    )
    p.add_argument("--init", action="store_true",
                   help="create the estimate.experiment table if absent")
    p.add_argument("--load", action="store_true",
                   help="parse the three CSVs and upsert rows (default action)")
    p.add_argument("--leaderboard", action="store_true",
                   help="print a ranked leaderboard (split_v1 numbers on top)")
    p.add_argument("--top", type=int, default=None,
                   help="limit the leaderboard to the top N rows")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    conn = connect()

    did_something = False
    if args.init:
        init_table(conn)
        did_something = True
    # --load is the default when neither --init nor --leaderboard is given.
    if args.load or not (args.init or args.leaderboard):
        load(conn)
        did_something = True
    if args.leaderboard:
        leaderboard(conn, top_n=args.top)
        did_something = True

    conn.close()
    return 0 if did_something else 1


if __name__ == "__main__":
    sys.exit(main())
