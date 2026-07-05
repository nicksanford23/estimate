#!/usr/bin/env python3
"""Model-1 v1 prediction CLI.

    python3 scripts/predict.py <pdf-path-or-doc_id>

Resolves the argument to a PDF (an existing local file path, OR a numeric
doc_id -> R2 docs/<doc_id>.pdf), extracts per-page text with PyMuPDF, scores
each page with the packaged v1 model (models/model_v1.joblib, auto-pulled from
R2 if absent), and prints JSON:

    {
      "pages":   [{"page_index", "score", "keep", "has_text", "reason"}, ...],
      "summary": {"n_pages", "n_keep", "elapsed_ms", "threshold", "model_version"}
    }

Pages with <50 chars of extracted text are force-kept (keep=true,
reason='no_text_conservative') rather than trusted to the text model.

All scoring logic lives in scripts/model_v1_lib.py, shared with the FastAPI
demo (scripts/app.py) so the CLI and the live endpoint agree exactly.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_v1_lib as lib  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description="Classify a plan-set PDF with Model-1 v1.")
    p.add_argument("target", help="a PDF file path OR a numeric doc_id (R2 docs/<id>.pdf)")
    p.add_argument("--model", default=None, help="path to model_v1.joblib (default: models/, else R2)")
    args = p.parse_args(argv)

    pkg = lib.load_model(args.model)
    result = lib.classify_input(pkg, args.target)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
