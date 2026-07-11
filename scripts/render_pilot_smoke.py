#!/usr/bin/env python3
"""Render an inclusive zero-based page range for isolated pilot labeling."""

import argparse
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
LONG_EDGE = 2200


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("output_dir")
    parser.add_argument("--first", type=int, default=0)
    parser.add_argument("--last", type=int, required=True)
    args = parser.parse_args()
    pdf_path = (ROOT / args.pdf).resolve()
    output_dir = (ROOT / args.output_dir).resolve()
    if ROOT not in pdf_path.parents or ROOT not in output_dir.parents:
        raise SystemExit("paths must stay inside the repository")
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    if args.first < 0 or args.last >= len(doc) or args.first > args.last:
        raise SystemExit("invalid page range")
    for index in range(args.first, args.last + 1):
        page = doc[index]
        zoom = LONG_EDGE / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        path = output_dir / f"page_{index:04d}.png"
        pix.save(path)
        print(f"{index}|{path.relative_to(ROOT)}|{pix.width}x{pix.height}")
    doc.close()


if __name__ == "__main__":
    main()
