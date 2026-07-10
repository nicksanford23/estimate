#!/usr/bin/env python3
"""Test harness for the BAD_TITLE_LINE patch: calibration + spot-check.
Downloads each doc once, calls title_flag(), deletes the PDF. Not part of
the pipeline -- a throwaway verification script."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from probe2_sf import r2_client, download_pdf  # noqa: E402
from scan_closeability_full import title_flag  # noqa: E402

CALIBRATION = [
    # permit, doc_id, page, expect_bad_title, note
    ("14-11290-NEWC", 1494156, 3, False, "bank branch, PASS-eligible"),
    ("26-10321-RNVN", 9058456, 18, False, "VA building, PASS-eligible"),
    ("25-33341-NEWC", 8640130, 11, None, "REJECT via rep_flag (3D), title irrelevant"),
    ("24-22310-RNVN", 7671011, 2, None, "REJECT via rep_flag (hatch), title irrelevant"),
]

SPOT_CHECK = [
    ("14-14229-NEWC", 1878269, 49, True, "ROOF FRAMING PLAN PART A"),
    ("15-19033-NEWC", 1928146, 21, True, "SECOND FLOOR PLUMBING PLAN"),
    ("16-03045-NEWC", 2285638, 36, True, "ELECTRICAL PLAN - BLDG TYPE II"),
    ("17-13962-NEWC", 2790768, 28, True, "SANITARY WASTE/VENT PLAN"),
    ("21-10119-NEWC", 5985160, 10, True, "Fifth Floor RCP Plan"),
    ("21-18881-NEWC", 5041419, 19, True, "2ND FLOOR ELECTRICAL LIGHTING PLAN"),
    ("22-06090-NEWC", 5413829, 25, True, "PART HVAC PLAN"),
    ("22-07567-NEWC", 5411538, 1, True, "RIGHT SIDE ELEVATION"),
    ("23-12122-NEWC", 6182089, 1, True, "SCHEMATIC/PROPOSED PLOT PLAN"),
    ("26-08030-NEWC", 8998094, 27, True, "LANDSCAPE PLAN"),
    ("19-36884-RNVS", 4417431, 22, True, "2ND LEVEL FRAMING PLAN"),
    ("24-19337-NEWC", 7356476, 15, True, "2ND FLOOR REFLECTED CEILING PLAN"),
]

s3 = r2_client()
results = []
for permit, doc_id, page, expect, note in CALIBRATION + SPOT_CHECK:
    try:
        pdf = download_pdf(s3, doc_id)
        bad = title_flag(pdf, page)
    except Exception as e:
        bad = f"ERR:{type(e).__name__}"
    finally:
        try:
            os.remove(pdf)
        except Exception:
            pass
    if expect is None:
        status = "n/a (rep_flag-driven)"
    else:
        status = "OK" if bad == expect else "**MISMATCH**"
    results.append((permit, doc_id, page, expect, bad, status, note))

print(f"{'permit':18} {'doc':9} {'pg':4} {'expect':7} {'got':7} {'status':22} note")
for permit, doc_id, page, expect, bad, status, note in results:
    print(f"{permit:18} {doc_id:<9} {page:<4} {str(expect):7} {str(bad):7} {status:22} {note}")
