#!/usr/bin/env python3
"""Standalone inference library for Model-1 v1.

Deliberately dependency-light: joblib + numpy + PyMuPDF(fitz), plus boto3 only
if you actually fetch from R2. It does NOT import the training modules
(train_sweep_*), so it drops onto a bare pod with just:
    pip install fastapi uvicorn joblib scikit-learn scipy numpy pymupdf boto3

Shared by scripts/predict.py (CLI) and scripts/app.py (FastAPI demo) so the
CLI and the live endpoint run byte-for-byte the same scoring.

Serving contract
    - Per page: score = P(keep) from the packaged TF-IDF+logreg model;
      keep = score >= package['threshold'] (thr_v1).
    - CONSERVATIVE no-text rule: a page whose extracted text is shorter than
      MIN_TEXT_CHARS (50) is NOT trusted to the text model -- it is force-kept
      (keep=True, reason='no_text_conservative'). Scans / image-only sheets
      thus never get silently dropped; they surface for review.
"""
import io
import json
import os
import time

import numpy as np

MIN_TEXT_CHARS = 50
DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models",
    "model_v1.joblib")
R2_MODEL_KEY = "claude-repo/models/model_v1.joblib"


# ---------------------------------------------------------------------------
# env / R2
# ---------------------------------------------------------------------------
def load_env(env_path=None):
    """Parse .env into a dict; fall back to process env for missing keys."""
    env = {}
    if env_path is None:
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k] = v
    for k in ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
              "R2_BUCKET"):
        if k not in env and k in os.environ:
            env[k] = os.environ[k]
    return env


def _r2_client(env):
    import boto3
    return boto3.client(
        "s3", endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto")


# ---------------------------------------------------------------------------
# model loading
# ---------------------------------------------------------------------------
def load_model(path=None, env=None):
    """Load the v1 package. If `path` is missing locally, pull it from R2
    (claude-repo/models/model_v1.joblib) into that path first."""
    import joblib
    path = path or DEFAULT_MODEL_PATH
    if not os.path.exists(path):
        env = env or load_env()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        _r2_client(env).download_file(env["R2_BUCKET"], R2_MODEL_KEY, path)
    return joblib.load(path)


# ---------------------------------------------------------------------------
# PDF fetch
# ---------------------------------------------------------------------------
def fetch_pdf_bytes(arg, env=None):
    """Resolve `arg` to PDF bytes.

    - existing local file path        -> read it
    - otherwise, treated as a doc_id  -> R2 docs/<doc_id>.pdf
    Validates the %PDF magic before returning.
    """
    if isinstance(arg, (bytes, bytearray)):
        data = bytes(arg)
    elif os.path.exists(str(arg)):
        with open(arg, "rb") as f:
            data = f.read()
    else:
        env = env or load_env()
        doc_id = str(arg).strip()
        if not doc_id.isdigit():
            raise ValueError(
                f"'{arg}' is neither an existing file nor a numeric doc_id")
        buf = io.BytesIO()
        _r2_client(env).download_fileobj(
            env["R2_BUCKET"], f"docs/{doc_id}.pdf", buf)
        data = buf.getvalue()
    if not data[:5].startswith(b"%PDF"):
        raise ValueError("fetched bytes are not a PDF (missing %PDF header)")
    return data


# ---------------------------------------------------------------------------
# extraction + scoring
# ---------------------------------------------------------------------------
def extract_page_texts(pdf_bytes):
    """Per-page extracted text via PyMuPDF, list[str] in page order."""
    import fitz
    texts = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            texts.append(page.get_text("text") or "")
    return texts


def score_texts(package, texts):
    """Return (scores float[N], has_text bool[N]) for a list of page texts.

    Scores are P(keep) from the packaged model for every page (even short-text
    ones, for transparency); the keep decision applies the no-text override
    separately in classify_pdf_bytes.
    """
    vec = package["vectorizer"]
    model = package["model"]
    pos = package["positive_class_index"]
    texts = [t if isinstance(t, str) else "" for t in texts]
    has_text = np.array([len(t.strip()) >= MIN_TEXT_CHARS for t in texts])
    if not texts:
        return np.zeros(0), has_text
    X = vec.transform(texts)
    scores = model.predict_proba(X)[:, pos]
    return scores, has_text


def classify_pdf_bytes(package, pdf_bytes):
    """Full result packet: per-page decisions + summary."""
    t0 = time.time()
    threshold = float(package["threshold"])
    texts = extract_page_texts(pdf_bytes)
    scores, has_text = score_texts(package, texts)

    pages = []
    n_keep = 0
    for i, (s, ht) in enumerate(zip(scores.tolist(), has_text.tolist())):
        if not ht:
            keep, reason = True, "no_text_conservative"
        else:
            keep = bool(s >= threshold)
            reason = "score>=threshold" if keep else "score<threshold"
        n_keep += int(keep)
        pages.append({
            "page_index": i,
            "score": round(float(s), 6),
            "keep": bool(keep),
            "has_text": bool(ht),
            "reason": reason,
        })

    elapsed_ms = int(round((time.time() - t0) * 1000))
    return {
        "pages": pages,
        "summary": {
            "n_pages": len(pages),
            "n_keep": int(n_keep),
            "elapsed_ms": elapsed_ms,
            "threshold": threshold,
            "model_version": package.get("split_version", "v1"),
        },
    }


def classify_input(package, arg, env=None):
    """Convenience: resolve `arg` (path/doc_id/bytes) -> classify."""
    pdf_bytes = fetch_pdf_bytes(arg, env=env)
    return classify_pdf_bytes(package, pdf_bytes)


if __name__ == "__main__":  # tiny smoke test
    import sys
    pkg = load_model()
    print(json.dumps(classify_input(pkg, sys.argv[1]), indent=2))
