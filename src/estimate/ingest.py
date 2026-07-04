"""Ingest plan set PDFs: render each page to a PNG and write a manifest.

Usage:
    python -m estimate.ingest data/raw/*.pdf --out data/pages

Produces:
    data/pages/<pdf-stem>/page_0001.png ...
    data/pages/manifest.jsonl   (one record per page, appended across runs)
"""

import argparse
import json
import pathlib

import fitz  # PyMuPDF
from tqdm import tqdm

LONG_EDGE_PX = 1568  # good balance of legibility vs. token cost for VLM labeling


def render_pdf(pdf_path: pathlib.Path, out_root: pathlib.Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    out_dir = out_root / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for i, page in enumerate(doc):
        zoom = LONG_EDGE_PX / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        png_path = out_dir / f"page_{i + 1:04d}.png"
        pix.save(png_path)
        # Vector text presence is a cheap signal: CAD-exported PDFs keep text
        # as text; scanned sets don't. Downstream stages branch on this.
        text = page.get_text().strip()
        drawings = page.get_drawings()
        records.append({
            "page_id": f"{pdf_path.stem}/page_{i + 1:04d}",
            "pdf": str(pdf_path),
            "page_index": i,
            "png": str(png_path),
            "width_pt": page.rect.width,
            "height_pt": page.rect.height,
            "has_vector_text": len(text) > 50,
            "vector_drawing_count": len(drawings),
            "text_preview": text[:300],
        })
    doc.close()
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdfs", nargs="+", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/pages"))
    args = ap.parse_args()

    manifest_path = args.out / "manifest.jsonl"
    args.out.mkdir(parents=True, exist_ok=True)

    seen = set()
    if manifest_path.exists():
        with open(manifest_path) as f:
            seen = {json.loads(line)["page_id"] for line in f}

    with open(manifest_path, "a") as mf:
        for pdf in args.pdfs:
            records = render_pdf(pdf, args.out)
            new = [r for r in records if r["page_id"] not in seen]
            for r in new:
                mf.write(json.dumps(r) + "\n")
            print(f"{pdf.name}: {len(records)} pages ({len(new)} new)")


if __name__ == "__main__":
    main()
