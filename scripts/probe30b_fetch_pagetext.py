#!/usr/bin/env python3
"""Probe 30b -- fetch each roster doc's PDF from R2, extract text of the
roster page (title block lives there) + save first ~4000 chars, delete PDF.
2 workers, disk stays flat. Output: data/probe30b/pagetext_cache/<doc>_p<page>.txt
Read-only against R2 (GET only). Reuses probe30_extract_worker env loading.
"""
import csv, os, sys, concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from probe30_extract_worker import load_env, r2_client  # noqa

import fitz

ENV = load_env()
OUT = os.path.join(ROOT, "data", "probe30b", "pagetext_cache")
os.makedirs(OUT, exist_ok=True)
TMP = "/tmp/claude-1000/-workspaces-estimate/cfaebbe4-655a-4986-8607-25a6d76540e7/scratchpad/p30b_pdfs"
os.makedirs(TMP, exist_ok=True)


def one(row):
    doc, page = row["doc_id"], int(row["page"])
    out = os.path.join(OUT, f"{doc}_p{page}.txt")
    if os.path.exists(out):
        return doc, "cached"
    # local pagetext dir?
    lp = os.path.join(ROOT, "data", "pagetext", doc, f"page_{page:04d}.txt")
    if os.path.exists(lp):
        with open(lp) as f:
            txt = f.read()
        with open(out, "w") as f:
            f.write(txt)
        return doc, "local"
    pdf = os.path.join(TMP, f"{doc}_{os.getpid()}.pdf")
    try:
        s3 = r2_client()
        s3.download_file(ENV["R2_BUCKET"], f"docs/{doc}.pdf", pdf)
        with open(pdf, "rb") as f:
            assert f.read(4) == b"%PDF", f"not pdf {doc}"
        d = fitz.open(pdf)
        txt = d[page].get_text()
        d.close()
        with open(out, "w") as f:
            f.write(txt)
        return doc, "fetched"
    except Exception as e:
        return doc, f"ERR:{e}"
    finally:
        if os.path.exists(pdf):
            os.remove(pdf)


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "probe30", "roster.csv"))))
    with cf.ProcessPoolExecutor(max_workers=2) as ex:
        for doc, status in ex.map(one, rows):
            print(doc, status, flush=True)


if __name__ == "__main__":
    main()
