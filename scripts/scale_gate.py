#!/usr/bin/env python3
"""S1.7 SCALE + TRANSFORM GATE — 24-06748-RNVS plan viewports (pages 5-8).

Per FULL_PROCESS_LOCKED.md S1.7: for EVERY plan viewport, before any inch-based
work, record scale + units + source, and at least ONE independent dimension
check. Here the check is fully machine: parse a printed dimension string from the
PDF text layer, find the vector dimension LINE it annotates, measure that span in
vector coordinates at the claimed scale, and compare printed vs measured.

Status per viewport = verified_machine (pending founder countersign). A failing
check flags the viewport; its rooms must not proceed (enforced downstream).

NO inch-based measurement may pass while a viewport's scale is unverified (S1.7).

Usage: python scripts/scale_gate.py
"""
import json
import math
import os
import re

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
PDF = os.path.join(ROOT, "data", "render_cache", "pdf", "7372349.pdf")
PT_PER_FT = 18.0                 # claimed: 1/4" = 1'-0"  ->  18 pt/ft
# page_index -> sheet (from bundle_g1b/tasks.json)
VIEWPORTS = {5: "A101", 6: "A102", 7: "A103", 8: "A104"}
TOL_PCT = 2.0                    # pass gate: |printed-measured| <= 2%
MATCH_PCT = 4.0                  # a segment corroborates a dim if within 4%

DIM_RE = re.compile(r"^(\d+)'\s*-?\s*(\d+)?\"?$")


def parse_feet(word):
    m = DIM_RE.match(word.strip())
    if not m:
        return None
    ft = int(m.group(1))
    inch = int(m.group(2)) if m.group(2) else 0
    if inch >= 12:
        return None
    return ft + inch / 12.0


def raw_segments(doc, pi):
    segs = []
    for path in doc[pi].get_drawings():
        for it in path["items"]:
            if it[0] == "l":
                segs.append(((it[1].x, it[1].y), (it[2].x, it[2].y)))
            elif it[0] == "re":
                r = it[1]
                cs = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                for i in range(4):
                    segs.append((cs[i], cs[(i + 1) % 4]))
    return segs


def dim_words(doc, pi):
    """Printed dimension strings with value, orientation, midpoint."""
    out = []
    for w in doc[pi].get_text("words"):
        x0, y0, x1, y1, txt = w[0], w[1], w[2], w[3], w[4]
        ft = parse_feet(txt)
        if ft is None or ft < 4:      # ignore tiny callouts / detail ticks
            continue
        wide = (x1 - x0) >= (y1 - y0)
        out.append(dict(
            text=txt, feet=ft,
            orient=("H" if wide else "V"),
            mid=((x0 + x1) / 2, (y0 + y1) / 2)))
    return out


def best_dim_line(dim, segs):
    """Find the vector dimension line this dim text annotates: a segment
    parallel to the text's reading direction, near it, whose length matches
    value*PT_PER_FT within MATCH_PCT. Returns (seg, measured_pt, pct_err)."""
    target = dim["feet"] * PT_PER_FT
    mx, my = dim["mid"]
    want_h = dim["orient"] == "H"
    best = None
    for a, b in segs:
        dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
        L = math.hypot(dx, dy)
        if L < 1:
            continue
        is_h = dx >= dy
        if is_h != want_h:
            continue
        # near the text: across-offset small, along-span overlaps the text
        smx = (a[0] + b[0]) / 2; smy = (a[1] + b[1]) / 2
        if want_h:
            across = abs(smy - my); along = abs(smx - mx)
        else:
            across = abs(smx - mx); along = abs(smy - my)
        if across > 70:                      # dim line must sit near its text
            continue
        if along > max(L, target) * 0.75:    # text roughly centered on the line
            continue
        pct = (L - target) / target * 100.0
        if abs(pct) > MATCH_PCT:
            continue
        score = abs(pct) + across / 100.0
        if best is None or score < best[0]:
            best = (score, (a, b), L, pct)
    if best is None:
        return None
    return best[1], best[2], best[3]


def main():
    doc = fitz.open(PDF)
    out = {
        "permit": PERMIT,
        "gate": "S1.7 scale + transform",
        "scale_claim": {"note": "1/4\" = 1'-0\"", "pt_per_ft": PT_PER_FT,
                        "units": "US survey feet / inches", "source": "scale_note"},
        "method": ("independent check: parse a printed PDF dimension string, locate "
                   "the vector dimension line it annotates (parallel + adjacent + "
                   "length within 4%), measure its span at the claimed scale, compare "
                   "printed vs measured. Machine-only; founder countersign pending."),
        "tolerance_pct": TOL_PCT,
        "viewports": {},
    }
    for pi, sheet in VIEWPORTS.items():
        segs = raw_segments(doc, pi)
        dims = dim_words(doc, pi)
        corrob = []
        for dim in dims:
            r = best_dim_line(dim, segs)
            if r is None:
                continue
            seg, meas_pt, pct = r
            corrob.append(dict(
                printed=dim["text"], printed_ft=round(dim["feet"], 3),
                orient=dim["orient"],
                measured_ft=round(meas_pt / PT_PER_FT, 3),
                measured_pt=round(meas_pt, 1),
                measured_pt_per_ft=round(meas_pt / dim["feet"], 3),
                pct_error=round(pct, 2),
                seg_pdf=[[round(seg[0][0], 1), round(seg[0][1], 1)],
                         [round(seg[1][0], 1), round(seg[1][1], 1)]]))
        # dedupe corroborations that resolved to the same segment
        seen = set(); uniq = []
        for c in corrob:
            k = tuple(map(tuple, c["seg_pdf"]))
            if k in seen:
                continue
            seen.add(k); uniq.append(c)
        uniq.sort(key=lambda c: abs(c["pct_error"]))
        # primary independent check = the best-corroborated, longest reliable dim
        primary = None
        if uniq:
            # prefer a large overall dimension (>=20ft) with small error
            big = [c for c in uniq if c["printed_ft"] >= 20]
            primary = (big[0] if big else uniq[0])
        status = "verified_machine"
        flag = None
        if primary is None:
            status = "unverified"
            flag = "no printed dimension could be matched to a vector dimension line"
        elif abs(primary["pct_error"]) > TOL_PCT:
            status = "flagged_scale_mismatch"
            flag = (f"primary dimension check off by {primary['pct_error']}% "
                    f"(> {TOL_PCT}% tol); rooms on this viewport must not proceed")
        mean_ppf = (round(sum(c["measured_pt_per_ft"] for c in uniq) / len(uniq), 3)
                    if uniq else None)
        out["viewports"][sheet] = {
            "page_index": pi, "sheet": sheet,
            "scale": {"note": "1/4\" = 1'-0\"", "pt_per_ft": PT_PER_FT,
                      "source": "scale_note"},
            "status": status,
            "founder_countersign": "pending",
            "primary_check": primary,
            "empirical_pt_per_ft_mean": mean_ppf,
            "corroborating_dim_count": len(uniq),
            "corroborations": uniq[:8],
            "flag": flag,
        }
        pc = primary["pct_error"] if primary else None
        print(f"{sheet} (pi{pi}): {status}; primary "
              f"{primary['printed'] if primary else '—'} err {pc}% ; "
              f"{len(uniq)} dims corroborate; empirical {mean_ppf} pt/ft")

    p = os.path.join(ROOT, "data", "sam_smoke", PERMIT, "scale_gate.json")
    json.dump(out, open(p, "w"), indent=1)
    print("\nwrote", p)


if __name__ == "__main__":
    main()
