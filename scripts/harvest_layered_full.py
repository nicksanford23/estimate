#!/usr/bin/env python3
"""Harvest LAYERED plans — FULL R2 CORPUS pass, subprocess-isolated.

harvest_layered.py's targets() only iterates `estimate.document` (our small,
partially-populated ingestion-tracking table). The actual downloaded corpus
lives in R2 (`docs/{doc_id}.pdf`; per CLAUDE.md the R2 file existing IS the
"downloaded" flag). This script closes that gap: it lists R2 directly, maps
doc_id -> permit_num via estimate.documents (verified 1:1), and scans every
doc not yet covered by the SAME resumable data/triage/layered_plans.csv /
.csv.seen files harvest_layered.py uses — so output stays one unified,
resumable dataset.

Why subprocesses (not threads like harvest_layered.py): fitz/MuPDF segfaults
intermittently on this corpus and the box OOM-SIGTERMs multi-GB python
processes; in a threaded design one bad PDF kills the whole run (observed
repeatedly). Here each doc is scanned in its own short-lived
`python3 harvest_layered_full.py --one <doc_id> <permit>` subprocess: a
segfault/OOM/timeout costs that ONE doc, which is recorded in
layered_plans.csv.crashed (not .seen — .seen means "scanned clean, no wall
layers") and reported at the end.

Reuses harvest_layered.scan() unchanged for the actual per-doc work.
"""
import os
import sys
import csv
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harvest_layered import OUT, FIELDS, done_docs, mark_seen, scan, env
from probe2_sf import r2_client, ENV

CRASHED = OUT + ".crashed"
SIZE_SKIP = 300 * 1024 * 1024  # skip any single PDF >300MB (log it)
PER_DOC_TIMEOUT = 600          # seconds; a doc that can't scan in 10min is pathological
WORKERS = 6                    # fast-gate makes most docs I/O-bound; heavy docs still parse-bound
_lock = threading.Lock()


def r2_doc_listing():
    s3 = r2_client()
    paginator = s3.get_paginator("list_objects_v2")
    out = []
    for page in paginator.paginate(Bucket=ENV["R2_BUCKET"], Prefix="docs/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".pdf"):
                stem = key[len("docs/"):-len(".pdf")]
                if stem.isdigit():
                    out.append((int(stem), obj["Size"]))
    return out


def permit_map(doc_ids):
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(env()["NEON_DATABASE_URL"])
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    m = {}
    CHUNK = 5000
    for i in range(0, len(doc_ids), CHUNK):
        chunk = doc_ids[i:i + CHUNK]
        c.execute("SELECT doc_id, permit_num FROM estimate.documents WHERE doc_id = ANY(%s)", (chunk,))
        for r in c.fetchall():
            m[r["doc_id"]] = r["permit_num"]
    # fallback: our own ingestion table for anything estimate.documents misses
    c.execute("SELECT onestop_doc_id od, permit_num pn FROM estimate.document")
    for r in c.fetchall():
        m.setdefault(r["od"], r["pn"])
    conn.close()
    return m


def crashed_docs():
    if not os.path.exists(CRASHED):
        return set()
    return {l.split()[0] for l in open(CRASHED) if l.strip()}


def mark_crashed(doc_id, why):
    with _lock:
        open(CRASHED, "a").write(f"{doc_id} {why}\n")
    print(f"CRASH doc {doc_id}: {why}", flush=True)


# ---------------------------------------------------------------- one-doc mode
def one_doc_mode(doc_id, permit):
    """Child process: scan a single doc, print rows as CSV to stdout between
    sentinels. scan() already swallows download errors (returns []).

    FAST GATE (probe9's trick): a page's get_drawings() layer strings come
    from the PDF's OCG dictionary, so if get_ocgs() has no wall-named layer,
    no page can carry wall-layer linework — skip the expensive 60-page
    get_drawings() walk entirely. ~85% of docs exit here in ~2s instead of
    ~13s: the difference between a ~10h and a ~2-3h full-corpus pass."""
    import fitz
    from probe2_sf import r2_client, download_pdf
    from probe7_layer_walls import WALL_RE

    w = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
    s3 = r2_client()
    try:
        pdf = download_pdf(s3, doc_id)
    except Exception:
        print("<<ROWS>>")   # missing/unreadable: empty result, parent marks seen
        print("<<END>>")
        return
    try:
        try:
            doc = fitz.open(pdf)
            has_wall_ocg = any(WALL_RE.search(v.get("name") or "")
                               for v in doc.get_ocgs().values())
            doc.close()
        except Exception:
            has_wall_ocg = True   # can't read OCGs -> fall through to full scan
        # scan() re-uses the already-downloaded temp file (download_pdf caches
        # by path) and removes it in its finally block.
        rows = scan(dict(od=doc_id, pn=permit)) if has_wall_ocg else []
    finally:
        try:
            os.remove(pdf)   # belt-and-braces for the no-wall fast path
        except OSError:
            pass
    print("<<ROWS>>")
    for r in rows:
        w.writerow(r)
    print("<<END>>")


# ------------------------------------------------------------------- driver
def run_doc(doc_id, permit):
    """Parent side: run the one-doc scan in an isolated subprocess."""
    cmd = [sys.executable, os.path.abspath(__file__), "--one", str(doc_id), permit]

    def _rm_orphan():
        # a killed child can't run scan()'s finally-remove; disk is tight
        from probe2_sf import PDF_TMP_DIR
        try:
            os.remove(os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf"))
        except OSError:
            pass

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=PER_DOC_TIMEOUT)
    except subprocess.TimeoutExpired:
        _rm_orphan()
        return None, "timeout"
    if p.returncode != 0:
        _rm_orphan()
        return None, f"rc={p.returncode}"
    out = p.stdout
    if "<<ROWS>>" not in out or "<<END>>" not in out:
        return None, "no_sentinel"
    body = out.split("<<ROWS>>", 1)[1].split("<<END>>", 1)[0].strip()
    rows = []
    if body:
        for r in csv.DictReader(body.splitlines(), fieldnames=FIELDS):
            rows.append(r)
    return rows, None


def main():
    listing = r2_doc_listing()
    print(f"R2 corpus: {len(listing)} PDFs under docs/", flush=True)
    ids = [od for od, _ in listing]
    sizes = dict(listing)
    pmap = permit_map(ids)
    n_unmapped = sum(1 for od in ids if od not in pmap)
    print(f"permit_num mapped for {len(ids)-n_unmapped}/{len(ids)} doc_ids "
          f"({n_unmapped} unmapped -> UNKNOWN-<id>)", flush=True)

    done = done_docs() | crashed_docs()
    print(f"already covered (seen ∪ csv ∪ crashed): {len(done)}", flush=True)

    todo = []
    for od in ids:
        if str(od) in done:
            continue
        if sizes.get(od, 0) > SIZE_SKIP:
            mark_crashed(od, f"skip_too_big_{sizes[od]/1e6:.0f}MB")
            continue
        todo.append((od, pmap.get(od, f"UNKNOWN-{od}")))
    print(f"scanning {len(todo)} remaining docs, {WORKERS} isolated subprocesses", flush=True)

    write_header = not os.path.exists(OUT) or os.path.getsize(OUT) == 0
    f = open(OUT, "a", newline="")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if write_header:
        w.writeheader()
        f.flush()

    n_docs = n_layered = n_crashed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_doc, od, pn): (od, pn) for od, pn in todo}
        for fut in as_completed(futs):
            od, pn = futs[fut]
            rows, err = fut.result()
            n_docs += 1
            if err is not None:
                n_crashed += 1
                mark_crashed(od, err)
            elif rows:
                with _lock:
                    for r in rows:
                        w.writerow(r)
                    f.flush()
                n_layered += 1
            else:
                mark_seen(od)
            if n_docs % 50 == 0:
                print(f"[{n_docs}/{len(todo)}] layered={n_layered} crashed={n_crashed}", flush=True)
    f.close()
    print(f"DONE: {n_layered} layered / {n_crashed} crashed of {n_docs} scanned this run -> {OUT}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--one":
        one_doc_mode(int(sys.argv[2]), sys.argv[3])
    else:
        main()
