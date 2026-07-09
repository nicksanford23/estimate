#!/usr/bin/env python3
"""Area-column hunt — find a TRUTH_AREA permit.

None of our worked buildings (bank, 26-10321, 25-33341) has a per-room AREA
column to grade geometry against. This scans every labeled finish_schedule /
schedule_other page's extracted text for the signature of a room schedule that
carries an AREA column (room rows + an AREA/SF header + many SF-range numbers),
and ranks candidates. The top ones then go to the schedule-reader vision agent
to confirm it is a real room_area_schedule (not occupant-load / gross-area noise).

Pure read over data/pagetext + Neon labels; writes only our CSV.
"""
import os, sys, csv, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import ROOT

PT = os.path.join(ROOT, "data", "pagetext")
OUT = os.path.join(ROOT, "data", "triage", "area_schedule_candidates.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

AREA_HDR = re.compile(r"\b(AREA|SQ\.?\s*FT|SQ\.?\s*FEET|S\.?\s*F\.?|SQUARE\s+F)\b", re.I)
ROOM_HDR = re.compile(r"\bROOM\b|\bRM\b|\bROOM\s*(NO|NAME|#)\b", re.I)
# a plausible room area, e.g. 120  1,240  340.5  (20..50000 sf)
AREA_NUM = re.compile(r"\b(\d{1,2},\d{3}|\d{2,5})(?:\.\d+)?\b")
# occupant-load / gross-area false-positive giveaways
NEG = re.compile(r"OCCUPANT\s+LOAD|GROSS\s+AREA|LEAS(E|ING)|EGRESS|OCCUPANCY\s+LOAD", re.I)


def env():
    e = {}
    for l in open(os.path.join(ROOT, ".env")):
        l = l.strip()
        if l and not l.startswith("#") and "=" in l:
            k, v = l.split("=", 1); e[k] = v
    return e


def cur():
    import psycopg2, psycopg2.extras
    return psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def score(txt):
    up = txt.upper()
    has_area = bool(AREA_HDR.search(up))
    has_room = bool(ROOM_HDR.search(up))
    nums = [n.replace(",", "") for n in AREA_NUM.findall(txt)]
    area_like = [int(float(n)) for n in nums if 20 <= float(n) <= 50000]
    neg = bool(NEG.search(up))
    # crude row count: lines that start with a room-number-ish token
    rows = sum(1 for ln in txt.splitlines() if re.match(r"^\s*\d{2,4}\b", ln))
    s = 0
    if has_area: s += 3
    if has_room: s += 1
    s += min(len(area_like), 20) * 0.3
    s += min(rows, 20) * 0.2
    if neg: s -= 2
    return dict(score=round(s, 1), has_area=has_area, has_room=has_room,
                n_area_like=len(area_like), n_rows=rows, neg=neg)


def main():
    c = cur()
    c.execute("""SELECT DISTINCT d.permit_num pn, d.onestop_doc_id od, p.page_index pi, pl.category cat,
                        pl.sheet_title st
                 FROM estimate.page_label pl
                 JOIN estimate.page p ON p.id=pl.page_id
                 JOIN estimate.document d ON p.document_id=d.id
                 WHERE pl.category IN ('finish_schedule','schedule_other')""")
    rows = c.fetchall()
    out = []
    for r in rows:
        f = os.path.join(PT, str(r["od"]), f"page_{r['pi']:04d}.txt")
        if not os.path.exists(f):
            out.append(dict(permit=r["pn"], doc_id=r["od"], page=r["pi"], cat=r["cat"],
                            sheet=r["st"] or "", score=-1, has_area=False, has_room=False,
                            n_area_like=0, n_rows=0, neg=False, note="no_text"))
            continue
        sc = score(open(f, errors="replace").read())
        out.append(dict(permit=r["pn"], doc_id=r["od"], page=r["pi"], cat=r["cat"],
                        sheet=r["st"] or "", note="", **sc))
    out.sort(key=lambda x: -x["score"])
    fields = ["score", "permit", "doc_id", "page", "cat", "sheet", "has_area", "has_room",
              "n_area_like", "n_rows", "neg", "note"]
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
        for r in out:
            w.writerow({k: r.get(k) for k in fields})
    print(f"scored {len(out)} schedule pages -> {OUT}\n")
    print(f"{'score':>5} {'permit':<16}{'pg':>4} {'area':>5}{'rows':>5}{'#sf':>5}  sheet")
    for r in out[:20]:
        print(f"{r['score']:>5} {r['permit']:<16}{r['page']:>4} "
              f"{('Y' if r['has_area'] else '.'):>5}{r['n_rows']:>5}{r['n_area_like']:>5}  {r['sheet'][:34]}")


if __name__ == "__main__":
    main()
