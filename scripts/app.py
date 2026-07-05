#!/usr/bin/env python3
"""Model-1 v1 demo service (FastAPI).

Endpoints
    GET  /health   -> JSON liveness + model metadata.
    GET  /         -> phone-friendly HTML upload form (pick a PDF, submit).
    POST /classify -> ONE endpoint, content-negotiated:
                      * multipart/form-data (a file field, i.e. the GET / form)
                        -> renders an HTML results table (KEEP green / HIDE),
                           per-page score + reason, and an "X of Y kept" line.
                      * application/json {"doc_id": N}  -> fetch R2 docs/N.pdf
                      * application/json {"pdf_b64": ".."} -> decode + classify
                        -> returns the JSON packet from model_v1_lib.

Same scoring as scripts/predict.py: both import model_v1_lib, so the CLI and
this endpoint agree byte-for-byte, including the conservative no-text rule.

Run:  uvicorn app:app --host 0.0.0.0 --port 8000
The model is loaded once at startup (local models/model_v1.joblib if present,
else pulled from R2 claude-repo/models/model_v1.joblib).
"""
import base64
import html
import os
import sys

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_v1_lib as lib  # noqa: E402

app = FastAPI(title="Commercial Flooring Estimator — Model-1 v1")
PKG = lib.load_model()  # load once at startup


# ---------------------------------------------------------------------------
# HTML rendering (no JS build; inline CSS; mobile viewport)
# ---------------------------------------------------------------------------
PAGE_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: -apple-system, system-ui, Segoe UI, Roboto, sans-serif;
       margin: 0; padding: 1rem; max-width: 820px; margin-inline: auto;
       line-height: 1.45; }
h1 { font-size: 1.35rem; margin: 0 0 .25rem; }
.sub { opacity: .7; font-size: .9rem; margin-bottom: 1.25rem; }
.card { border: 1px solid rgba(128,128,128,.35); border-radius: 12px;
        padding: 1rem; margin-bottom: 1rem; }
input[type=file] { width: 100%; padding: .6rem 0; font-size: 1rem; }
button { width: 100%; padding: .85rem 1rem; font-size: 1.05rem; border: 0;
         border-radius: 10px; background: #2563eb; color: #fff; font-weight: 600; }
button:active { transform: translateY(1px); }
.summary { font-size: 1.1rem; font-weight: 700; margin: .25rem 0 1rem; }
table { width: 100%; border-collapse: collapse; font-size: .95rem; }
th, td { text-align: left; padding: .5rem .5rem; border-bottom: 1px solid rgba(128,128,128,.25); }
th { font-size: .8rem; text-transform: uppercase; letter-spacing: .03em; opacity: .7; }
.tag { display: inline-block; padding: .15rem .55rem; border-radius: 999px;
       font-weight: 700; font-size: .82rem; }
.keep { background: #16a34a; color: #fff; }
.hide { background: rgba(128,128,128,.22); }
.reason { opacity: .65; font-size: .82rem; }
.score { font-variant-numeric: tabular-nums; }
a.back { display: inline-block; margin-top: 1rem; color: #2563eb; }
.mono { font-variant-numeric: tabular-nums; }
"""


def render_upload_form(msg=""):
    m = PKG.get("metrics", {}).get("at_thr_v1", {})
    thr = PKG.get("threshold")
    info = (f"Keeps every finish page (finish_recall=1.0 on the held-out eval "
            f"split) at threshold {thr:.4f}; ~{m.get('frac_kept', 0)*100:.0f}% "
            f"of pages surface for takeoff.")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flooring plan-page classifier — v1 demo</title><style>{PAGE_CSS}</style></head>
<body>
<h1>Commercial Flooring — plan-page classifier</h1>
<div class="sub">Model-1 v1 · upload a plan-set PDF, get the pages that matter for a flooring takeoff.</div>
<div class="card">
  <form action="/classify" method="post" enctype="multipart/form-data">
    <label for="file"><b>Choose a plan-set PDF</b></label><br>
    <input id="file" type="file" name="file" accept="application/pdf" required><br><br>
    <button type="submit">Classify pages</button>
  </form>
  {('<p style="color:#dc2626">'+html.escape(msg)+'</p>') if msg else ''}
</div>
<div class="sub">{html.escape(info)}</div>
</body></html>"""


def render_results_html(result, filename=""):
    s = result["summary"]
    rows = []
    for p in result["pages"]:
        keep = p["keep"]
        tag = ('<span class="tag keep">KEEP</span>' if keep
               else '<span class="tag hide">HIDE</span>')
        rows.append(
            f"<tr><td class='mono'>{p['page_index']+1}</td>"
            f"<td>{tag}</td>"
            f"<td class='score'>{p['score']:.3f}</td>"
            f"<td class='reason'>{html.escape(p['reason'])}</td></tr>")
    fname = html.escape(filename or "uploaded.pdf")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Results — {fname}</title><style>{PAGE_CSS}</style></head>
<body>
<h1>Results</h1>
<div class="sub">{fname} · {s['elapsed_ms']} ms · threshold {s['threshold']:.4f} · model {html.escape(str(s['model_version']))}</div>
<div class="summary">{s['n_keep']} of {s['n_pages']} pages kept for takeoff</div>
<table>
  <thead><tr><th>Page</th><th>Decision</th><th>Score</th><th>Reason</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>
<a class="back" href="/">&larr; classify another PDF</a>
</body></html>"""


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_version": PKG.get("split_version", "v1"),
        "threshold": PKG.get("threshold"),
        "keep_rule": PKG.get("keep_rule", {}).get("keep_categories"),
        "metrics_at_threshold": PKG.get("metrics", {}).get("at_thr_v1"),
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(render_upload_form())


@app.post("/classify")
async def classify(request: Request):
    ct = request.headers.get("content-type", "")
    # --- browser upload form -> HTML results table ---
    if ct.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            return HTMLResponse(render_upload_form("No file was submitted."),
                                status_code=400)
        data = await upload.read()
        try:
            if not data[:5].startswith(b"%PDF"):
                raise ValueError("That file is not a PDF.")
            result = lib.classify_pdf_bytes(PKG, data)
        except Exception as e:  # noqa: BLE001  (surface a friendly message)
            return HTMLResponse(render_upload_form(f"Could not process: {e}"),
                                status_code=400)
        return HTMLResponse(
            render_results_html(result, getattr(upload, "filename", "")))
    # --- JSON API -> JSON packet ---
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "send multipart file or JSON body"},
                            status_code=400)
    try:
        if "pdf_b64" in body:
            data = base64.b64decode(body["pdf_b64"])
            result = lib.classify_pdf_bytes(PKG, data)
        elif "doc_id" in body:
            result = lib.classify_input(PKG, str(body["doc_id"]))
        else:
            return JSONResponse(
                {"error": "provide 'doc_id' (int) or 'pdf_b64' (base64 PDF)"},
                status_code=400)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse(result)
