#!/usr/bin/env python3
"""EXPERIMENT (isolated — does NOT modify main engine). My own P0 solution,
built from the Claude+Codex reconciliation:

  1. PAGE/SCOPE SELECTION — replace "pick the floor-plan page with the most
     polygons" with a score: penalize phasing/demolition/overall/context/detail/
     schedule sheet titles, prefer floor/enlarged/tenant, and add room-label
     text density inside the drawing.
  2. LABEL-ANCHORED ACCEPTANCE — a polygon is an ACCEPTED room only if it
     contains a real room label (number). Polygons inside a notes/schedule/title
     text block are ARTIFACT_REJECT. Everything else is UNLABELED (review).
     This also replaces the broken `rooms_counted` with a label hit rate.

NOT merged. Prints a before/after table vs the answer keys so we can judge it.
Honest limit: label anchoring needs real text; on vectorized-text sheets it will
accept few (those need vision/OCR later) — reported, not hidden.
"""
import os, sys, re, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.ops import unary_union, polygonize
from shapely.geometry import Point, box
from probe2_sf import (ROOT, r2_client, download_pdf, extract_drawings,
    wall_candidates, suppress_hatches, snap_and_close, seg_len)

AK = os.path.join(ROOT, "data", "triage", "debug_25", "answer_keys")
TITLE_BAD = re.compile(r"phas|demo|overall|context|partition type|\bdetail|schedul|legend|"
                       r"\bnotes?\b|cover|index|\bsite\b|roof|ceiling|elevation|section", re.I)
TITLE_GOOD = re.compile(r"floor plan|enlarged|tenant|1st|2nd|3rd|first floor|second floor|"
                        r"level|unit|\bplan\b", re.I)
NOTE_KW = re.compile(r"GENERAL NOTES|REVISION|SCHEDULE|LEGEND|\bDETAIL|PARTITION|DOOR SCHEDULE|"
                     r"KEYNOTE|FINISH SCHEDULE|ABBREVIATION|SYMBOL", re.I)
ROOM_NUM = re.compile(r"^\d{2,4}[A-Za-z]?$")
PI2 = 3.14159


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


def title_score(t):
    t = t or ""
    return (2 if TITLE_GOOD.search(t) else 0) - (3 if TITLE_BAD.search(t) else 0)


def room_labels(pg):
    """word centers whose text is a room-number token."""
    out = []
    for w in pg.get_text("words"):
        if ROOM_NUM.match(w[4].strip()):
            out.append(((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
    return out


def note_regions(pg):
    """bboxes of text blocks that are notes/schedules/legends/title."""
    regions = []
    for b in pg.get_text("blocks"):
        if len(b) >= 5 and NOTE_KW.search(b[4] or ""):
            regions.append(box(b[0], b[1], b[2], b[3]))
    return regions


def analyze_page(pdf, pi, pg):
    ex = extract_drawings(pdf, pi); pw, ph = ex["pw"], ex["ph"]
    walls, dom, thick = wall_candidates(ex); wc, _ = suppress_hatches(walls, pw)
    if not wc:
        return dict(polys=0, accepted=0, artifact=0, unlabeled=0, labels=len(room_labels(pg)))
    lines, _ = snap_and_close(wc, ex["arcs"], pw, feet_per_pt=0.1)
    polys = list(polygonize(unary_union(lines)))
    xs = [c for a, b, L, w in wc for c in (a[0], b[0])]
    ys = [c for a, b, L, w in wc for c in (a[1], b[1])]
    bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    rooms = [p for p in polys if 0.004 * bbox <= p.area <= 0.25 * bbox
             and p.length and 4 * PI2 * p.area / p.length ** 2 >= 0.25]
    labels = room_labels(pg); notes = note_regions(pg)
    accepted = artifact = unlabeled = 0
    for p in rooms:
        c = p.centroid
        if any(nr.contains(c) for nr in notes):
            artifact += 1
        elif any(p.contains(Point(x, y)) for x, y in labels):
            accepted += 1
        else:
            unlabeled += 1
    return dict(polys=len(rooms), accepted=accepted, artifact=artifact,
                unlabeled=unlabeled, labels=len(labels))


def run(permit, real_rooms):
    c = cur()
    c.execute("""SELECT d.onestop_doc_id od, p.page_index pi, pl.sheet_title st
                 FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
                 JOIN estimate.page_label pl ON pl.page_id=p.id
                 WHERE d.permit_num=%s AND pl.category='floor_plan'
                 GROUP BY d.onestop_doc_id, p.page_index, pl.sheet_title""", (permit,))
    cand = c.fetchall()
    if not cand:
        return None
    od = cand[0]["od"]
    s3 = r2_client(); pdf = download_pdf(s3, od); doc = fitz.open(pdf)
    # OLD selection: page with most compact polygons (what breakdown_25 did)
    # NEW selection: title_score, tie-break by room-label density then poly count
    scored = []
    for r in cand[:6]:
        pi = r["pi"]
        try:
            m = analyze_page(pdf, pi, doc[pi])
        except Exception:
            continue
        old_key = m["polys"]
        new_key = (title_score(r["st"]), m["labels"], m["accepted"])
        scored.append((pi, r["st"], m, old_key, new_key))
    doc.close(); os.remove(pdf)
    if not scored:
        return None
    old_pick = max(scored, key=lambda s: s[3])
    new_pick = max(scored, key=lambda s: s[4])
    return dict(permit=permit, real=real_rooms,
                old_page=old_pick[0], old_polys=old_pick[2]["polys"],
                new_page=new_pick[0], new_title=(new_pick[1] or "")[:22],
                accepted=new_pick[2]["accepted"], artifact=new_pick[2]["artifact"],
                unlabeled=new_pick[2]["unlabeled"], labels=new_pick[2]["labels"])


def main():
    keys = {}
    for f in glob.glob(os.path.join(AK, "*.json")):
        d = json.load(open(f))
        if d.get("real_room_count"):
            keys[d["permit"]] = d["real_room_count"]
    print(f"comparable answer keys: {len(keys)}\n")
    print(f"{'permit':<16}{'real':>5}{'oldPoly':>8}{'newAcc':>7}{'artifact':>9}{'unlab':>6}{'labels':>7}  new sheet")
    rows = []
    for pn, rr in sorted(keys.items()):
        r = run(pn, rr)
        if not r:
            print(f"{pn:<16}  (no data)"); continue
        rows.append(r)
        print(f"{pn:<16}{r['real']:>5}{r['old_polys']:>8}{r['accepted']:>7}"
              f"{r['artifact']:>9}{r['unlabeled']:>6}{r['labels']:>7}  {r['new_title']}"
              + ("  [page changed]" if r['old_page'] != r['new_page'] else ""))
    # honest summary
    withlabels = [r for r in rows if r["labels"] > 0]
    print(f"\npermits with usable room-label text: {len(withlabels)}/{len(rows)} "
          f"(rest are vectorized-text → need vision)")
    if withlabels:
        import statistics
        hit = [min(r["accepted"], r["real"]) / r["real"] for r in withlabels]
        print(f"label-hit-rate (accepted/real) on those: "
              f"median {statistics.median(hit):.2f}, values {[round(h,2) for h in sorted(hit)]}")


if __name__ == "__main__":
    main()
