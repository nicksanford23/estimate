#!/usr/bin/env python3
"""Closeability scan — FULL CORPUS pass, calibrated + subprocess-isolated.

scan_closeability.py only scored the ~75 permits with a labeled floor_plan
page (the biased slice behind the "only 2 usable" claim). This script scores
every candidate page in data/triage/layered_plans.csv (built by
harvest_layered.py + harvest_layered_full.py over the whole R2 corpus).

DIFFERENCES vs scan_closeability.score_page — all forced by calibrating
against the four ground-truth cases (see usable_layered_report.md):

1. fpp SWEEP. score_page hardcoded feet_per_pt=0.1 "irrelevant to structure"
   — but fpp sets snap_and_close's door-gap-closing distance in POINTS, so it
   is scale-DEPENDENT: the bank (14-11290 p3, drawn small at 1/4"=1'-0")
   scores n_mid=4/cov=0.086 at fpp=0.1 but n_mid=15/cov_mid=0.253 at
   fpp=0.05 (probe7 with the true scale closed 12 rooms — 0.05 is right).
   We polygonize at fpp in {0.05, 0.1, 0.2} and keep the best result by
   (n_mid, cov_mid).

2. cov_mid. Fragment tilings ('.3D' solid exports) inflate plain coverage to
   0.9+ while closing almost no real rooms; cov_mid counts only room-band
   polygon area, which is what usability actually needs.

3. rep_flag — wall-REPRESENTATION red flag: the page has no real clean
   wall-core supply. Clean core = long segments on layers whose name is
   wall-like (WALL/CMU/STUD/GYP/STUCCO/PARTITION/MASON) and NOT /3D|HATCH/i,
   summed across layers; flag if that total is < 60. 25-33341 ('A - Walls - Exterior.3D', 3D solid
   edges: its ONLY wall layer) and 24-22310 ('8_Wall_Hatch' + a door/window
   symbol layer: no clean core at all) are the two ground-truth NOT-usable
   cases; probes 19/24/25 showed these fail for representation reasons no
   tolerance fixes; 20-21673 (*_HATCH*) was excluded from probe25 likewise.
   NOTE it must be no-clean-layer, not any-flagged-layer: usable 26-10321
   carries 'NEW WALL HATCH' poché ALONGSIDE clean 'NEW WALL' centerlines.
   Metric cuts alone can NOT separate 25-33341 (its p12 closes 19 small core
   rooms and looks statistically like a usable page while the actual labs —
   most of the building — never close), so the flag is load-bearing.

4. bad_title — pages whose title-block line reads SECTION/ELEVATION/etc.
   A building section polygonizes beautifully (closed profile shapes in the
   room band) but is not a floor plan. Verified on 25-33341 p17/p18.

Per permit: its top 8 candidate pages by harvested wall_segs (widened from 3
so real floor plans can surface past section sheets). One row per page (not
best-of-permit) so calibration can see per-page variance. Each doc is scored
in an isolated subprocess (fitz segfaults / OOM kills observed on this
corpus; a crash costs one doc). Append-only, resumable on
(permit, doc_id, page). Output: data/triage/closeability_full.csv.
"""
import os
import re
import sys
import csv
import subprocess
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz
from shapely.ops import unary_union, polygonize
from probe2_sf import (ROOT, r2_client, download_pdf, ENV, PDF_TMP_DIR,
                       snap_and_close, seg_len)
from probe7_layer_walls import WALL_RE

IN = os.path.join(ROOT, "data", "triage", "layered_plans.csv")
OUT = os.path.join(ROOT, "data", "triage", "closeability_full.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
FIELDS = ["permit", "doc_id", "page", "wall_segs_reported", "n_raw_segs",
          "n_wall_segs", "n_core_segs", "n_polys", "n_mid", "coverage",
          "cov_mid", "largest_frac", "best_fpp", "rep_flag", "bad_title",
          "layers", "note"]
SIZE_SKIP = 300 * 1024 * 1024
PER_DOC_TIMEOUT = 900
WORKERS = 2
FPP_SWEEP = (0.05, 0.1, 0.2)
REP_RE = re.compile(r"3D|HATCH", re.I)
CORE_RE = re.compile(r"WALL|CMU|STUD|GYP|STUCCO|PARTITION|MASON", re.I)
CORE_MIN = 60  # a usable page needs at least this many clean core segments
_wlock = threading.Lock()

BAD_TITLE_LINE = re.compile(
    # substring (not anchored ^...$) so trailing/leading qualifiers like
    # "PART A", street names, or a "2ND FLOOR" prefix don't hide a match
    # (probe: "ROOF FRAMING PLAN PART A", "Fifth Floor RCP Plan",
    # "RIGHT SIDE ELEVATION", "2ND FLOOR REFLECTED CEILING PLAN" all missed
    # the old ^...$ anchors)
    r"ELEVATIONS?\b|"
    r"(BUILDING\s+|WALL\s+)?SECTIONS?\b|"
    r"ROOF\s+(PLAN|FRAMING)|"
    r"(REFLECTED\s+)?CEILING\s+PLAN|\bRCP\b|"
    r"DEMOLITION\s+PLAN|"
    r"^(DETAIL|SCHEDULE|LEGEND)S?$|"  # kept anchored: bare single words, too
                                      # generic to safely substring-match
    r"SITE\s+PLAN|PLOT\s+PLAN|GRADING\s+PLAN|"
    r"(FOUNDATION|FRAMING)\s+PLAN|"
    # MEP/civil disciplines: reliably NOT a floor plan in this corpus (pipe/
    # duct/joist/plant-bed linework, not room-wall geometry) -- unlike
    # ELECTRICAL/POWER/LIGHTING/LIFE-SAFETY sheets (see below), these almost
    # never carry a real reused architectural wall xref (verdict slice
    # audit: PLUMBING/MECHANICAL/HVAC/SPRINKLER/FIRE/SEWER/LANDSCAPE/FRAMING
    # false-pass rate ~85-100%, 0-1 counterexample each)
    r"\bPLUMBING\b|\bMECHANICAL\b|\bHVAC\b|\bSPRINKLER\b|"
    r"FIRE\s+(PROTECTION|ALARM)|\bSEWER\b|\bSANITARY\b|"
    r"\bLANDSCAPE\b|\bPLANTING\b|"
    # ELECTRICAL/POWER/LIGHTING/LIFE SAFETY are a WEAKER signal here (verdict
    # audit: ~13 CONFIRMED vs 20 FALSE_PASS electrical, ~6 vs 4 power, ~3 vs 4
    # life-safety -- these disciplines commonly overlay the SAME real
    # architectural wall xref, so roughly a coin flip). Included per the
    # calibration brief anyway: this only affects re-ranking a permit that
    # is ALREADY in the false-pass set (frozen CONFIRMED rows are never
    # re-scored), so the cost of a miss is "no recovery found", not a
    # regression -- but it means some real MEP-titled recoveries will be
    # left on the table; flagged in the report, not silently eaten.
    r"\bELECTRICAL\b|\bPOWER\b|\bLIGHTING\b|LIFE\s+SAFETY",
    re.I)
GOOD_TITLE_LINE = re.compile(
    r"FLOOR\s+PLAN|^LEVEL\s+\d|UNIT\s+PLAN|TENANT\s+(LAYOUT|PLAN)|ENLARGED.*PLAN",
    re.I)
# Narrow sub-check used only to veto the whitelist below: an *actual*
# roof-framing/reflected-ceiling/foundation-framing TITLE, not just the
# bare word "CEILING"/"FRAMING" appearing in an ordinary partition-detail
# note (e.g. "...WITH SOUND BATTS FROM FLOOR SLAB TO 6\" ABOVE CEILING" is a
# routine wall-assembly callout on the bank's real floor-plan page, not a
# reflected-ceiling-plan title -- must not disable the whitelist).
FRAMING_ISH_TITLE = re.compile(
    r"ROOF\s+(PLAN|FRAMING)|(REFLECTED\s+)?CEILING\s+PLAN|(FOUNDATION|FRAMING)\s+PLAN",
    re.I)


def title_flag(pdf, page_index):
    """True if the page's own title-block LINE (not a keynote substring)
    reads as a non-floor-plan sheet type (section/elevation/roof/etc)."""
    try:
        doc = fitz.open(pdf)
        lines = [l.strip() for l in doc[page_index].get_text().splitlines() if l.strip()]
        doc.close()
    except Exception:
        return False
    # Only consider short, title-block-like lines for BOTH checks -- "SEE
    # FLOOR PLAN(S)..."/"SEE ELECTRICAL"/"SEE PLUMBING DRAWINGS" keynote
    # lines are cross-references, not the page's own title, and long note
    # sentences that happen to contain a discipline word are not titles.
    titly = [l for l in lines if len(l) < 60 and not re.search(r"\bSEE\b", l, re.I)]
    # Whitelist override: if the page reads as a genuine floor plan (FLOOR
    # PLAN / LEVEL N / UNIT PLAN / TENANT LAYOUT / ENLARGED...PLAN) it's
    # never bad -- protects real architectural floor-plan sheets (bank's
    # "PARTIAL FLOOR PLAN - BRANCH", 25-33341's "FIRST/SECOND FLOOR PLAN")
    # from any incidental MEP/civil keyword found elsewhere on the same page
    # (e.g. "ELECTRICAL SERVICE", "LANDSCAPE AREA" callouts on the bank page).
    # EXCEPT: checked page-level, not line-level -- a bare "LEVEL 2" facility
    # label (common on structural/MEP sheets too, not just floor plans) must
    # not rescue a page that ALSO carries a real REFLECTED/CEILING/FRAMING
    # title elsewhere (probe: 19-36884-RNVS "2ND LEVEL FRAMING PLAN" sheet
    # also prints a bare "LEVEL 2" field -- that alone must not whitelist it).
    saw_good = any(GOOD_TITLE_LINE.search(l) for l in titly)
    framing_ish = any(FRAMING_ISH_TITLE.search(l) for l in titly)
    if saw_good and not framing_ish:
        return False
    return any(BAD_TITLE_LINE.search(l) for l in titly)


def extract_by_layer(pdf, page_index):
    """probe7's extract_wall_layer_segments logic, but keeping each segment's
    layer so rep_flag can be computed per layer (probe7's version discards the
    per-segment attribution). Same WALL_RE, same line/fill-rect rules."""
    doc = fitz.open(pdf)
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    segs = []  # (p0, p1, width, layer)
    for d in page.get_drawings():
        lay = d.get("layer") or ""
        if not WALL_RE.search(lay):
            continue
        width = d.get("width") or 0.0
        is_fill = d.get("fill") is not None and d.get("type") in ("f", "fs")
        for item in d.get("items", []):
            if item[0] == "l":
                p0, p1 = (item[1].x, item[1].y), (item[2].x, item[2].y)
                segs.append((p0, p1, width if width else 1.0, lay))
            elif item[0] == "re":
                r = item[1]
                rw, rh = r.width, r.height
                short, long_ = min(rw, rh), max(rw, rh)
                if is_fill and long_ > 0 and short / pw < 0.02 and long_ / max(pw, ph) > 0.01:
                    cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
                    if rw >= rh:
                        segs.append(((r.x0, cy), (r.x1, cy), short, lay))
                    else:
                        segs.append(((cx, r.y0), (cx, r.y1), short, lay))
    doc.close()
    return segs, pw, ph


def score_page_v2(pdf, pi):
    """Calibrated page metrics (see module docstring for the why of each)."""
    segs, pw, ph = extract_by_layer(pdf, pi)
    walls = [(p0, p1, w, lay) for p0, p1, w, lay in segs
             if seg_len(p0, p1) > 0.008 * pw]
    used = sorted({lay for _, _, _, lay in walls})
    # clean wall-core supply: long segments on wall-named, non-3D/HATCH layers
    # (summed across layers — walls legitimately split across CMU/stud/gyp)
    n_core = sum(1 for _, _, _, lay in walls
                 if CORE_RE.search(lay) and not REP_RE.search(lay))
    base = dict(n_raw_segs=len(segs), n_wall_segs=len(walls), n_core_segs=n_core,
                rep_flag=n_core < CORE_MIN,
                layers=used[:4])
    if not walls:
        return dict(base, n_polys=0, n_mid=0, coverage=0.0, cov_mid=0.0,
                    largest_frac=0.0, best_fpp=0)
    xs = [c for p0, p1, w, lay in walls for c in (p0[0], p1[0])]
    ys = [c for p0, p1, w, lay in walls for c in (p0[1], p1[1])]
    bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    best = None
    for fpp in FPP_SWEEP:
        lines, _ = snap_and_close(
            [(p0, p1, seg_len(p0, p1), w) for p0, p1, w, lay in walls], [], pw,
            feet_per_pt=fpp)
        polys = list(polygonize(unary_union(lines)))
        areas = [p.area for p in polys if p.area < 0.9 * bbox]
        mid_areas = [a for a in areas if 0.002 * bbox <= a <= 0.08 * bbox]
        m = dict(n_polys=len(polys), n_mid=len(mid_areas),
                 coverage=round(sum(areas) / bbox, 3) if areas else 0.0,
                 cov_mid=round(sum(mid_areas) / bbox, 3),
                 largest_frac=round(max(areas) / bbox, 3) if areas else 0.0,
                 best_fpp=fpp)
        key = (m["n_mid"], m["cov_mid"])
        if best is None or key > best[0]:
            best = (key, m)
    return dict(base, **best[1])


def top_candidates(n=8):
    """Top-N candidate pages per permit by harvested wall_segs. n=8 (was 5,
    mission suggested 3): verified on 25-33341 that a permit's real floor
    plans (p11/p12) can rank 6th-7th behind section/elevation sheets that
    carry more raw wall-layer segments. De-dupes (doc,page) repeats (the
    merged layered_plans.csv contains duplicate rows from multi-source runs)."""
    by_permit = defaultdict(dict)
    with open(IN) as f:
        for r in csv.DictReader(f):
            key = (int(r["doc_id"]), int(r["page"]))
            row = (int(r["doc_id"]), int(r["page"]), int(r["wall_segs"]), r["layers"])
            prev = by_permit[r["permit"]].get(key)
            if prev is None or row[2] > prev[2]:
                by_permit[r["permit"]][key] = row
    out = {}
    for permit, rowmap in by_permit.items():
        rows = sorted(rowmap.values(), key=lambda x: -x[2])
        out[permit] = rows[:n]
    return out


def done_keys():
    """Rows already scored. Transient failures (subprocess crash, download
    error, score_err) are NOT done — a rerun retries them; scored rows and
    skip_too_big stick. score_err proved transient in practice: concurrent
    jobs share PDF_TMP_DIR/{doc_id}.pdf and race on its deletion
    (FileNotFoundError mid-parse — this cost the bank's ground-truth page in
    the first pass), so it retries too. The CSV stays append-only; a retried
    key can have 2+ rows: analysis must prefer the clean row."""
    d = set()
    if os.path.exists(OUT):
        with open(OUT) as f:
            for r in csv.DictReader(f):
                note = (r.get("note") or "")
                if (note.startswith("crash:") or note.startswith("dl_err")
                        or note.startswith("score_err")):
                    continue
                d.add((r["permit"], r["doc_id"], r["page"]))
    return d


def r2_sizes():
    s3 = r2_client()
    paginator = s3.get_paginator("list_objects_v2")
    sizes = {}
    for page in paginator.paginate(Bucket=ENV["R2_BUCKET"], Prefix="docs/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".pdf"):
                stem = key[len("docs/"):-len(".pdf")]
                if stem.isdigit():
                    sizes[int(stem)] = obj["Size"]
    return sizes


def err_row(permit, doc_id, pi, wsr, lyr, note):
    return dict(permit=permit, doc_id=doc_id, page=pi, wall_segs_reported=wsr,
                n_raw_segs=0, n_wall_segs=0, n_polys=0, n_mid=0, coverage=0,
                cov_mid=0, largest_frac=0, best_fpp=0, rep_flag="",
                bad_title="", layers=lyr, note=note)


# ---------------------------------------------------------------- one-doc mode
def one_doc_mode(doc_id, tasks_csv):
    """Child: score this doc's candidate pages; emit CSV rows to stdout.
    tasks_csv: 'permit:page:wsr' triples joined by ';' (layers re-derived)."""
    s3 = r2_client()
    w = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
    tasks = []
    for part in tasks_csv.split(";"):
        permit, pi, wsr = part.rsplit(":", 2)
        tasks.append((permit, int(pi), int(wsr)))
    print("<<ROWS>>")
    try:
        pdf = download_pdf(s3, doc_id)
    except Exception as e:
        for permit, pi, wsr in tasks:
            w.writerow(err_row(permit, doc_id, pi, wsr, "", f"dl_err:{type(e).__name__}"))
        print("<<END>>")
        return
    try:
        for permit, pi, wsr in tasks:
            try:
                m = score_page_v2(pdf, pi)
                bt = title_flag(pdf, pi)
                w.writerow(dict(permit=permit, doc_id=doc_id, page=pi,
                                wall_segs_reported=wsr, bad_title=bt,
                                layers="|".join(m.pop("layers")), note="", **m))
            except Exception as e:
                w.writerow(err_row(permit, doc_id, pi, wsr, "",
                                   f"score_err:{type(e).__name__}"))
    finally:
        try:
            os.remove(pdf)
        except OSError:
            pass
    print("<<END>>")


# ------------------------------------------------------------------- driver
def run_doc(doc_id, tasks):
    arg = ";".join(f"{p}:{pi}:{wsr}" for p, pi, wsr, _ in tasks)
    cmd = [sys.executable, os.path.abspath(__file__), "--one", str(doc_id), arg]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=PER_DOC_TIMEOUT)
    except subprocess.TimeoutExpired:
        p = None
    try:
        os.remove(os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf"))  # crash orphan
    except OSError:
        pass
    if p is None or p.returncode != 0 or "<<ROWS>>" not in p.stdout or "<<END>>" not in p.stdout:
        why = "timeout" if p is None else f"rc={p.returncode}"
        return [err_row(permit, doc_id, pi, wsr, lyr, f"crash:{why}")
                for permit, pi, wsr, lyr in tasks]
    body = p.stdout.split("<<ROWS>>", 1)[1].split("<<END>>", 1)[0].strip()
    rows = []
    if body:
        for r in csv.DictReader(body.splitlines(), fieldnames=FIELDS):
            rows.append(r)
    return rows


def main():
    by_permit = top_candidates(n=8)
    print(f"{len(by_permit)} permits with named-wall-layer candidate pages "
          f"(data/triage/layered_plans.csv)", flush=True)

    done = done_keys()
    sizes = r2_sizes()

    by_doc = defaultdict(list)
    n_pages = n_big = 0
    for permit, rows in by_permit.items():
        for doc_id, page, wsr, lyr in rows:
            if (permit, str(doc_id), str(page)) in done:
                continue
            if sizes.get(doc_id, 0) > SIZE_SKIP:
                n_big += 1
                with _wlock:
                    write_row(err_row(permit, doc_id, page, wsr, lyr, "skip_too_big"))
                continue
            by_doc[doc_id].append((permit, page, wsr, lyr))
            n_pages += 1
    print(f"{n_pages} candidate pages across {len(by_doc)} docs "
          f"({n_big} skipped >300MB)", flush=True)

    n = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_doc, doc_id, tasks): doc_id for doc_id, tasks in by_doc.items()}
        for fut in as_completed(futs):
            doc_id = futs[fut]
            try:
                rows = fut.result()
            except Exception as e:
                print(f"ERROR doc {doc_id}: {type(e).__name__}: {e}", flush=True)
                rows = []
            with _wlock:
                for r in rows:
                    write_row(r)
            n += 1
            if n % 20 == 0 or n == len(by_doc):
                print(f"[{n}/{len(by_doc)} docs]", flush=True)
    print("DONE ->", OUT, flush=True)


_out_f = None
_out_w = None


def write_row(row):
    global _out_f, _out_w
    if _out_f is None:
        write_header = not os.path.exists(OUT) or os.path.getsize(OUT) == 0
        _out_f = open(OUT, "a", newline="")
        _out_w = csv.DictWriter(_out_f, fieldnames=FIELDS)
        if write_header:
            _out_w.writeheader()
            _out_f.flush()
    _out_w.writerow(row)
    _out_f.flush()


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--one":
        one_doc_mode(int(sys.argv[2]), sys.argv[3])
    else:
        main()
