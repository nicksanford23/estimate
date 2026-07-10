#!/usr/bin/env python3
"""Probe 30b -- extract firm-identity signals from each roster page's text:
phone numbers (normalized), and candidate firm-name lines (architect/AIA/
design/LLC lines). Writes data/probe30b/firm_signals.csv for eyeball review."""
import csv, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "probe30b", "pagetext_cache")
ROSTER = os.path.join(ROOT, "data", "probe30", "roster.csv")
OUT = os.path.join(ROOT, "data", "probe30b", "firm_signals.csv")

PHONE = re.compile(r"\(?\b(\d{3})\)?[\s.\-/]{0,2}(\d{3})[\s.\-]{0,2}(\d{4})\b")
NAME_HINT = re.compile(r"architect|A\.?I\.?A|design\b|studio|associates|\bLLC\b|\bInc\b|engineer", re.I)

rows = list(csv.DictReader(open(ROSTER)))
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["permit", "doc_id", "page", "split", "phones", "name_lines"])
    for r in rows:
        p = os.path.join(CACHE, f"{r['doc_id']}_p{int(r['page'])}.txt")
        txt = open(p, errors="replace").read() if os.path.exists(p) else ""
        phones = sorted({"".join(m.groups()) for m in PHONE.finditer(txt)})
        lines = []
        for ln in txt.splitlines():
            ln = ln.strip()
            if 3 < len(ln) < 90 and NAME_HINT.search(ln):
                if ln not in lines:
                    lines.append(ln)
        w.writerow([r["permit"], r["doc_id"], r["page"], r["split"],
                    "|".join(phones), " ~~ ".join(lines[:8])])
print("wrote", OUT)
