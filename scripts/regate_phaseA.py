#!/usr/bin/env python3
"""Re-gate step 3, Phase A: for every FALSE_PASS permit (per
data/triage/eyeball_verdicts.csv), recompute bad_title (only) on its
ALREADY-SCORED candidate rows in data/triage/closeability_full.csv using the
patched scan_closeability_full.title_flag, and see whether a DIFFERENT
candidate page now becomes the permit's best gate-passing page. Geometry
metrics (rep_flag, n_mid, cov_mid, largest_frac) are untouched -- only
bad_title is recomputed, since that's the only thing the patch changed.

Downloads each doc ONCE (subprocess-isolated per doc, same crash-tolerance
pattern as scan_closeability_full.py), computes title_flag for every page of
that doc needed by any FALSE_PASS permit, deletes the PDF.

Output: data/triage/regate_phaseA.csv (permit, doc_id, page, old_bad_title,
new_bad_title, n_mid, cov_mid, largest_frac, rep_flag, old_best_key,
new_best_key, status) -- status in {UNCHANGED, RECOVERED, LOST_NO_REPLACEMENT}
"""
import csv
import os
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import ROOT, r2_client, download_pdf, PDF_TMP_DIR

VERDICTS = os.path.join(ROOT, "data", "triage", "eyeball_verdicts.csv")
CLOSE = os.path.join(ROOT, "data", "triage", "closeability_full.csv")
OUT = os.path.join(ROOT, "data", "triage", "regate_phaseA.csv")
GATE = dict(n_mid=8, cov_mid=0.2, largest_frac=0.7)
WORKERS = 4


def fnum(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def passes(r, bad_title_val):
    return (r["rep_flag"] == "False" and bad_title_val is False
            and fnum(r["n_mid"]) >= GATE["n_mid"]
            and fnum(r["cov_mid"]) >= GATE["cov_mid"]
            and fnum(r["largest_frac"]) <= GATE["largest_frac"])


def one_doc_mode(doc_id, pages_csv):
    """Child: recompute title_flag for each page of this doc. Prints
    'page:bad' lines between markers."""
    from scan_closeability_full import title_flag
    s3 = r2_client()
    pages = [int(p) for p in pages_csv.split(",")]
    print("<<ROWS>>")
    try:
        pdf = download_pdf(s3, doc_id)
    except Exception as e:
        for p in pages:
            print(f"{p}:ERR:{type(e).__name__}")
        print("<<END>>")
        return
    try:
        for p in pages:
            try:
                bad = title_flag(pdf, p)
                print(f"{p}:{bad}")
            except Exception as e:
                print(f"{p}:ERR:{type(e).__name__}")
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass
    print("<<END>>")


def run_doc(doc_id, pages):
    cmd = [sys.executable, os.path.abspath(__file__), "--one", str(doc_id),
           ",".join(str(p) for p in pages)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        p = None
    try:
        os.remove(os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf"))
    except OSError:
        pass
    out = {}
    if p is None or p.returncode != 0 or "<<ROWS>>" not in p.stdout:
        for pg in pages:
            out[pg] = "CRASH"
        return out
    body = p.stdout.split("<<ROWS>>", 1)[1].split("<<END>>", 1)[0].strip()
    for line in body.splitlines():
        pg_s, val = line.split(":", 1)
        out[int(pg_s)] = val
    return out


def main():
    verdicts = list(csv.DictReader(open(VERDICTS)))
    fp_permits = sorted({r["permit"] for r in verdicts if r["verdict"] == "FALSE_PASS"})
    print(f"{len(fp_permits)} FALSE_PASS permits", flush=True)

    close_rows = list(csv.DictReader(open(CLOSE)))
    by_key = {}
    for r in close_rows:
        k = (r["permit"], r["doc_id"], r["page"])
        note = r.get("note") or ""
        bad = note.startswith(("crash:", "dl_err", "score_err"))
        if k in by_key:
            prev_bad = (by_key[k].get("note") or "").startswith(("crash:", "dl_err", "score_err"))
            if bad and not prev_bad:
                continue
        by_key[k] = r
    close_rows = [r for r in by_key.values() if not (r.get("note") or "").startswith(
        ("crash:", "dl_err", "score_err", "skip_too_big"))]

    by_permit = defaultdict(list)
    for r in close_rows:
        if r["permit"] in set(fp_permits):
            by_permit[r["permit"]].append(r)

    # group (doc_id -> pages needed) across all FP permits
    by_doc = defaultdict(set)
    for permit, rows in by_permit.items():
        for r in rows:
            by_doc[int(r["doc_id"])].add(int(r["page"]))

    print(f"{sum(len(v) for v in by_doc.values())} page-title recomputes "
          f"across {len(by_doc)} docs", flush=True)

    new_bad = {}  # (doc_id, page) -> bool or "CRASH"/"ERR..."
    n = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_doc, doc_id, sorted(pages)): doc_id
                for doc_id, pages in by_doc.items()}
        for fut in as_completed(futs):
            doc_id = futs[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {}
                print(f"ERROR doc {doc_id}: {e}", flush=True)
            for pg, val in res.items():
                new_bad[(doc_id, pg)] = val
            n += 1
            if n % 20 == 0 or n == len(by_doc):
                print(f"[{n}/{len(by_doc)} docs]", flush=True)

    out_rows = []
    for permit, rows in by_permit.items():
        old_pass = [r for r in rows if passes(r, r["bad_title"] == "True")]
        # old_best: max by (n_mid, cov_mid) among rows whose STORED bad_title
        # is False (the gate as it originally ran)
        old_candidates = [r for r in rows if r["bad_title"] == "False"
                          and r["rep_flag"] == "False"
                          and fnum(r["n_mid"]) >= GATE["n_mid"]
                          and fnum(r["cov_mid"]) >= GATE["cov_mid"]
                          and fnum(r["largest_frac"]) <= GATE["largest_frac"]]
        old_best = max(old_candidates, key=lambda r: (fnum(r["n_mid"]), fnum(r["cov_mid"]))) \
            if old_candidates else None

        new_candidates = []
        for r in rows:
            key = (int(r["doc_id"]), int(r["page"]))
            nb = new_bad.get(key, "MISSING")  # string "True"/"False"/"CRASH"/"ERR:..."
            if nb in ("True", "False"):
                nb_bool = (nb == "True")
                r = dict(r, new_bad_title=nb)
                if (r["rep_flag"] == "False" and nb_bool is False
                        and fnum(r["n_mid"]) >= GATE["n_mid"]
                        and fnum(r["cov_mid"]) >= GATE["cov_mid"]
                        and fnum(r["largest_frac"]) <= GATE["largest_frac"]):
                    new_candidates.append(r)
        new_best = max(new_candidates, key=lambda r: (fnum(r["n_mid"]), fnum(r["cov_mid"]))) \
            if new_candidates else None

        old_key = (old_best["doc_id"], old_best["page"]) if old_best else None
        new_key = (new_best["doc_id"], new_best["page"]) if new_best else None
        if new_key is not None and new_key != old_key:
            status = "RECOVERED"
        elif new_key is None:
            status = "LOST_NO_REPLACEMENT"
        else:
            status = "UNCHANGED"

        for r in rows:
            key = (int(r["doc_id"]), int(r["page"]))
            nb = new_bad.get(key, "MISSING")
            out_rows.append(dict(
                permit=permit, doc_id=r["doc_id"], page=r["page"],
                old_bad_title=r["bad_title"], new_bad_title=nb,
                rep_flag=r["rep_flag"], n_mid=r["n_mid"], cov_mid=r["cov_mid"],
                largest_frac=r["largest_frac"], best_fpp=r["best_fpp"],
                old_best=f"{old_key[0]}:{old_key[1]}" if old_key else "",
                new_best=f"{new_key[0]}:{new_key[1]}" if new_key else "",
                status=status))

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["permit", "doc_id", "page", "old_bad_title",
                                          "new_bad_title", "rep_flag", "n_mid", "cov_mid",
                                          "largest_frac", "best_fpp", "old_best", "new_best",
                                          "status"])
        w.writeheader()
        w.writerows(out_rows)

    by_status = defaultdict(set)
    for r in out_rows:
        by_status[r["status"]].add(r["permit"])
    print(f"\nwrote {OUT}")
    for s, permits in by_status.items():
        print(f"  {s}: {len(permits)} permits")
    print("\nRECOVERED permits (existing top-8 candidate, different page now best):")
    for r in out_rows:
        if r["status"] == "RECOVERED" and f"{r['doc_id']}:{r['page']}" == r["new_best"]:
            print(f"  {r['permit']}  old={r['old_best']}  new={r['new_best']}")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--one":
        one_doc_mode(int(sys.argv[2]), sys.argv[3])
    else:
        main()
