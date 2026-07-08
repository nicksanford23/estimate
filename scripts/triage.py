#!/usr/bin/env python3
"""Mechanical backbone of the triage-permits process. Per permit: scan signals
(wall-centerline layers, floor-plan density, finish-schedule TEXT, CANDIDATE
per-room SF), emit a PROVISIONAL tier + candidate schedule pages (rendered for the
schedule-reader vision agent) + best wall page. Nothing here is final — TRUTH/GOLD
are provisional until schedule-reader confirms; TRAIN until layers confirmed on a
floor plan. Writes data/triage/results.jsonl. See skills/triage-permits.
Usage: python3 triage.py [PERMIT ...]
"""
import os, re, sys, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from probe2_sf import ROOT, r2_client, download_pdf, seg_len
from probe8_layer_classes import classify_layer

OUT = os.path.join(ROOT, "data", "triage"); os.makedirs(OUT, exist_ok=True)
ROOMTOK = re.compile(r'^[A-Z]{0,2}-?\d{2,4}[A-Z]?$')
SCHED_RE = re.compile(r"FINISH\s+SCHEDULE|ROOM\s+FINISH|ROOM\s+SCHEDULE", re.I)
WALL_MIN = 200


def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); e[k] = v
    return e


def sf_candidates(words):
    """CANDIDATE per-room SF count (regex, over-fires — vision confirms)."""
    rooms = [((w[1]+w[3])/2, w[4]) for w in words if ROOMTOK.match(w[4])]
    sf = []
    for w in words:
        if w[4].upper() in ("SF", "S.F."):
            yc, x = (w[1]+w[3])/2, w[0]
            c = [(x-vw[2], int(vw[4])) for vw in words
                 if vw[4].isdigit() and abs((vw[1]+vw[3])/2-yc) < 3 and vw[2] <= x and 0 <= x-vw[2] < 70]
            if c: sf.append((yc, min(c)[1]))
    gt = {}
    for yc, code in rooms:
        b = [(abs(yc-sy), a) for sy, a in sf if abs(yc-sy) < 4]
        if b and 5 <= min(b)[1] <= 5000 and code not in gt: gt[code] = min(b)[1]
    return len(gt)


def wall_segs(pg):
    pw = pg.rect.width; n = 0; lays = set()
    for d in pg.get_drawings():
        if classify_layer(d.get("layer")) != "wall": continue
        for it in d.get("items", []):
            if it[0] == "l" and seg_len((it[1].x, it[1].y), (it[2].x, it[2].y)) > 0.008*pw:
                n += 1; lays.add(d.get("layer"))
    return n, sorted(lays)


def triage(cur, s3, permit):
    cur.execute("""SELECT d.onestop_doc_id od, p.page_index pi, pl.category
        FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
        LEFT JOIN estimate.page_label pl ON pl.page_id=p.id
        WHERE d.permit_num=%s ORDER BY d.onestop_doc_id, p.page_index""", (permit,))
    rows = cur.fetchall()
    if not rows:
        return dict(permit=permit, tier="NOT_INGESTED")
    docs = defaultdict(list)
    for r in rows: docs[r["od"]].append((r["pi"], r["category"]))
    fp_pages = [(r["od"], r["pi"]) for r in rows if r["category"] == "floor_plan"]

    best_wall = dict(segs=0, page=None, doc=None, layers=[])
    sched_cands = []       # (doc, page) candidate finish-schedule pages
    for od, pages in docs.items():
        try:
            pdf = download_pdf(s3, od); doc = fitz.open(pdf)
        except Exception:
            continue
        wall_check = [pi for pi, c in pages if c == "floor_plan"] or [pi for pi, _ in pages if pi < 40]
        for pi in wall_check[:15]:
            if pi >= doc.page_count: continue
            n, lays = wall_segs(doc[pi])
            if n > best_wall["segs"]: best_wall = dict(segs=n, page=pi, doc=od, layers=lays[:3])
        for pi, c in pages:
            if pi >= doc.page_count: continue
            t = doc[pi].get_text()
            if SCHED_RE.search(t) or c == "finish_schedule" or sf_candidates(doc[pi].get_text("words")) >= 6:
                sched_cands.append((od, pi))
        doc.close(); os.remove(pdf)

    # render candidate schedule pages (dedup) for the schedule-reader vision agent
    rendered = []; seen = set()
    for od, pi in sched_cands:
        if (od, pi) in seen: continue
        seen.add((od, pi))
        try:
            pdf = download_pdf(s3, od); doc = fitz.open(pdf)
            path = os.path.join(OUT, f"{permit}_d{od}_p{pi}.png")
            doc[pi].get_pixmap(matrix=fitz.Matrix(2.3, 2.3), alpha=False).save(path)
            rendered.append(dict(doc=od, page=pi, image=path))
            doc.close(); os.remove(pdf)
        except Exception:
            pass

    has_layers = best_wall["segs"] >= WALL_MIN
    has_fp = bool(fp_pages)
    has_sched_cand = bool(sched_cands)
    if has_layers and has_sched_cand: prov = "GOLD?"
    elif has_layers:                  prov = "TRAIN"
    elif has_sched_cand:              prov = "TRUTH?"
    elif has_fp:                      prov = "FLATTENED"
    else:                             prov = "DISMISS"
    return dict(permit=permit, provisional_tier=prov, tier=None,
                floor_plan_pages=[p for _, p in fp_pages], wall_page=best_wall,
                schedule_candidates=rendered, confirmed_by=None,
                note="TRUTH/GOLD pending schedule-reader; TRAIN pending layer-on-floorplan confirm")


def main():
    import psycopg2, psycopg2.extras
    cur = psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    s3 = r2_client()
    permits = sys.argv[1:] or ['17-35150-NEWC', '26-05332-NEWC', '23-05848-RNVS']
    recs = []
    for pn in permits:
        r = triage(cur, s3, pn); recs.append(r)
        if r.get("tier") == "NOT_INGESTED":
            print(f"{pn:<16} NOT_INGESTED"); continue
        w = r["wall_page"]
        print(f"{pn:<16} {r['provisional_tier']:<11} fp={len(r['floor_plan_pages'])} "
              f"walls={w['segs']}(p{w['page']} {w['layers']}) sched_cands={len(r['schedule_candidates'])}")
    with open(os.path.join(OUT, "results.jsonl"), "w") as f:
        for r in recs: f.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(recs)} records -> data/triage/results.jsonl "
          f"(+ candidate schedule PNGs for schedule-reader)")


if __name__ == "__main__":
    main()
