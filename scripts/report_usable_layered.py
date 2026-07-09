#!/usr/bin/env python3
"""Generate data/triage/usable_layered_report.md from closeability_full.csv.

Applies the calibrated USABLE gate (see scan_closeability_full.py for the
calibration story against the ground-truth cases):

  page USABLE  = not rep_flag and not bad_title
                 and n_mid >= 8 and cov_mid >= 0.2 and largest_frac <= 0.7
  permit USABLE = any candidate page passes

  page BORDERLINE (worth an eyeball) = relaxed gate
                 (n_mid >= 5, cov_mid >= 0.1, largest_frac <= 0.8) but not
                 USABLE. Also surfaced: permits whose only passing pages are
                 rep_flagged with strong metrics (a mis-flag would hide a
                 usable permit).

KNOWN LIMIT (documented, not hidden): 19-00670-RNVS passes the mechanical
gate but probe25's eyeball verdict is that its A-Wall layer SHREDS (15k raw
segments -> ~7k fragments, largest real room 67 SF on a ~7,100 SF building).
Its poly-explosion signature (n_polys ~49x n_wall_segs) does NOT separate it
from true-usable pages (the bank explodes to 36x at fpp=0.05 from CMU hatch
dust), and tuning yet another cut on a single case would be overfitting. So
the gate's output is CANDIDATE-usable; the report marks eyeball-verified vs
pending, and lists 19-00670 as the measured false-positive rate's floor.

Splits the usable list by evidence-doc provenance: docs downloaded in the
2026-07-09 go-wider batch (data/triage/download_batch_2026-07-09.csv,
status=ok) vs the pre-existing corpus — the go-wider hit rate.

Reads only our own CSVs; writes only the report file. Rerunnable.
"""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import ROOT

CLOSE = os.path.join(ROOT, "data", "triage", "closeability_full.csv")
LAYERED = os.path.join(ROOT, "data", "triage", "layered_plans.csv")
SEEN = LAYERED + ".seen"
CRASHED = LAYERED + ".crashed"
BATCH = os.path.join(ROOT, "data", "triage", "download_batch_2026-07-09.csv")
OUT = os.path.join(ROOT, "data", "triage", "usable_layered_report.md")

GATE = dict(n_mid=8, cov_mid=0.2, largest_frac=0.7)
RELAXED = dict(n_mid=5, cov_mid=0.1, largest_frac=0.8)

# ground truth / eyeball verdicts from probes 7/24/25 (doc-level)
VERIFIED_USABLE = {"14-11290-NEWC", "26-10321-RNVN"}
KNOWN_FALSE_PASS = {"19-00670-RNVS"}   # probe25 eyeball: shreds
KNOWN_NOT_USABLE = {"25-33341-NEWC", "24-22310-RNVN", "20-21673-RNVS"}


def fnum(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def passes(r, cut):
    return (r["rep_flag"] == "False" and r["bad_title"] == "False"
            and fnum(r["n_mid"]) >= cut["n_mid"]
            and fnum(r["cov_mid"]) >= cut["cov_mid"]
            and fnum(r["largest_frac"]) <= cut["largest_frac"])


def new_batch_docs():
    """doc_ids newly downloaded in the 2026-07-09 go-wider batch."""
    s = set()
    if os.path.exists(BATCH):
        for r in csv.DictReader(open(BATCH)):
            if r.get("status") == "ok":
                s.add(r["doc_id"])
    return s


def main():
    rows = list(csv.DictReader(open(CLOSE)))
    # de-dupe retried keys: prefer the clean (scored) row
    by_key = {}
    for r in rows:
        k = (r["permit"], r["doc_id"], r["page"])
        note = r.get("note") or ""
        bad = note.startswith(("crash:", "dl_err", "score_err"))
        if k in by_key:
            prev_bad = (by_key[k].get("note") or "").startswith(("crash:", "dl_err", "score_err"))
            if bad and not prev_bad:
                continue
        by_key[k] = r
    rows = list(by_key.values())
    n_unresolved = sum(1 for r in rows
                       if (r.get("note") or "").startswith(("crash:", "dl_err", "score_err")))

    by_permit = defaultdict(list)
    for r in rows:
        by_permit[r["permit"]].append(r)

    layered_permits = set()
    layered_docs = set()
    for r in csv.DictReader(open(LAYERED)):
        layered_permits.add(r["permit"])
        layered_docs.add(r["doc_id"])
    n_seen = len(set(open(SEEN).read().split())) if os.path.exists(SEEN) else 0
    n_crashed = (len({l.split()[0] for l in open(CRASHED) if l.strip()})
                 if os.path.exists(CRASHED) else 0)
    new_docs = new_batch_docs()

    usable = {}      # permit -> best passing row
    borderline = {}  # permit -> best relaxed-pass row (not usable)
    flag_watch = {}  # permit -> best rep_flagged row w/ strong metrics
    for permit, rs in by_permit.items():
        ps = [r for r in rs if passes(r, GATE)]
        if ps:
            usable[permit] = max(ps, key=lambda r: (fnum(r["n_mid"]), fnum(r["cov_mid"])))
            continue
        bs = [r for r in rs if passes(r, RELAXED)]
        if bs:
            borderline[permit] = max(bs, key=lambda r: (fnum(r["n_mid"]), fnum(r["cov_mid"])))
            continue
        fs = [r for r in rs if r["rep_flag"] == "True" and r["bad_title"] == "False"
              and fnum(r["n_mid"]) >= GATE["n_mid"] and fnum(r["cov_mid"]) >= GATE["cov_mid"]
              and fnum(r["largest_frac"]) <= GATE["largest_frac"]]
        if fs:
            flag_watch[permit] = max(fs, key=lambda r: (fnum(r["n_mid"]), fnum(r["cov_mid"])))

    def status_of(p):
        if p in VERIFIED_USABLE:
            return "VERIFIED (takeoff done)"
        if p in KNOWN_FALSE_PASS:
            return "FALSE-PASS (probe25 eyeball: shreds)"
        if p in KNOWN_NOT_USABLE:
            return "known NOT usable"
        return "eyeball pending"

    def table(d, with_status=False):
        hdr = "| permit | doc | page | n_mid | cov_mid | largest | core segs | fpp | new? | layers |"
        div = "|---|---|---|---|---|---|---|---|---|---|"
        if with_status:
            hdr = hdr[:-1] + " status |"
            div += "---|"
        lines = [hdr, div]
        for p in sorted(d):
            r = d[p]
            lay = (r["layers"] or "").replace("|", ", ")
            if len(lay) > 60:
                lay = lay[:57] + "..."
            newf = "NEW" if r["doc_id"] in new_docs else "old"
            row = (f"| {p} | {r['doc_id']} | {r['page']} | {r['n_mid']} | "
                   f"{r['cov_mid']} | {r['largest_frac']} | {r['n_core_segs']} | "
                   f"{r['best_fpp']} | {newf} | {lay} |")
            if with_status:
                row = row[:-1] + f" {status_of(p)} |"
            lines.append(row)
        return "\n".join(lines)

    usable_new = {p for p, r in usable.items() if r["doc_id"] in new_docs}
    usable_old = set(usable) - usable_new

    # Multi-building developments file near-identical plan sets under many
    # permit numbers (e.g. the 16-030xx cluster: 11 permits, same page +
    # near-identical metrics under sibling doc_ids). Permits are the real
    # unit for billing/takeoffs, but for "how many DISTINCT plan sets" count
    # unique metric fingerprints too.
    fingerprints = {(r["page"], r["n_wall_segs"], r["n_mid"], r["cov_mid"],
                     r["largest_frac"]) for r in usable.values()}
    n_plan_sets = len(fingerprints)

    md = f"""# Geometry-USABLE wall-layer permits — full-corpus scan

Generated by scripts/report_usable_layered.py from
data/triage/closeability_full.csv (candidates: data/triage/layered_plans.csv).

## Headline

- **Permits with named wall layers anywhere in the downloaded corpus:
  {len(layered_permits)}** (from {len(layered_docs)} layered docs).
- **Permits with >=1 page passing the calibrated USABLE gate:
  {len(usable)}** — of which {len(VERIFIED_USABLE & set(usable))} takeoff-verified,
  {len(KNOWN_FALSE_PASS & set(usable))} known false-pass (19-00670), rest eyeball-pending.
  (~{n_plan_sets} DISTINCT plan sets by metric fingerprint — multi-building
  developments share one plan set across sibling permits.)
- Gate-pass split by provenance: {len(usable_old)} from the pre-existing corpus,
  {len(usable_new)} from the 2026-07-09 go-wider batch (962 new docs).
- Borderline permits worth a human/agent eyeball: {len(borderline)}
  (+ {len(flag_watch)} rep-flagged permits whose metrics would otherwise pass).

## Coverage

- R2 corpus at scan time: 3,412 PDFs under docs/ (grew from 2,747 during the
  session as the go-wider download batch landed).
- Layer harvest: **gap = 0** — every R2 doc is covered by
  layered_plans.csv ∪ .seen ∪ .crashed (verified by set difference against a
  fresh R2 listing; 13 crashed/skipped docs of which 5 are >300MB skips).
- Closeability: top-8 candidate pages per permit scored; {n_unresolved}
  page-keys still unresolved (crash/dl_err after retries) — see CSV notes.

## The calibrated gate

Page is USABLE iff ALL of:
- `rep_flag = False` — >=60 long wall segments on clean wall-core layers
  (wall-named, not /3D|HATCH/i). Load-bearing: metric cuts alone cannot
  reject 25-33341's `.3D` solid export.
- `bad_title = False` — title-block line is not SECTION/ELEVATION/etc.
- `n_mid >= {GATE['n_mid']}` — room-band polygons (0.2%-8% of wall bbox).
- `cov_mid >= {GATE['cov_mid']}` — room-band area share (plain coverage is
  fragment-inflatable; cov_mid is not).
- `largest_frac <= {GATE['largest_frac']}` — not one giant unsubdivided blob.
Metrics = best over fpp sweep {{0.05, 0.1, 0.2}} (door-gap closing is
scale-dependent; fixed fpp=0.1 under-closes small-scale drawings — the
original closeability.csv scored the bank's ground-truth page at
n_mid=4/cov=0.086, one reason the old "only 2 usable" number was wrong).

### Calibration table (ground-truth cases)

| case | truth | gate says | key metrics |
|---|---|---|---|
| 14-11290-NEWC d1494156 p3 | USABLE (probe7: 12 rooms close) | PASS | mid=15 cov_mid=0.253 largest=0.192 @fpp0.05 |
| 26-10321-RNVN d9058456 p18 | USABLE (probe24: 15-room takeoff) | PASS | mid=46 cov_mid=0.391 largest=0.063 @fpp0.05 |
| 25-33341-NEWC d8640130 p11/12 | NOT (.3D solid, labs never close) | REJECT | rep_flag (`A - Walls - Exterior.3D`) |
| 24-22310-RNVN d7671011 p2 | NOT (hatch, no centerlines) | REJECT | rep_flag (`8_Wall_Hatch`, 0 clean core) |
| 19-00670-RNVS d5101148 p8 | NOT (probe25 eyeball: shreds, max room 67 SF) | **PASS = FALSE-POSITIVE** | mid=41 cov_mid=0.566 — indistinguishable mechanically |

The 19-00670 row is the honest limit of the mechanical gate: its shredded
linework closes fragment-clusters that are statistically identical to rooms
(poly-explosion ratio doesn't separate it either — the bank explodes to 36x
at fpp 0.05 from CMU hatch dust). 1 known false-pass among the 5
ground-truth cases means the usable list below is CANDIDATE-usable pending
a per-permit eyeball; expect roughly 1-in-5 to shake out.

## USABLE-gate permits ({len(usable)})

{table(usable, with_status=True)}

## Borderline — eyeball these ({len(borderline)})

Pass a relaxed gate (mid>={RELAXED['n_mid']}, cov_mid>={RELAXED['cov_mid']},
largest<={RELAXED['largest_frac']}) but not the main one:

{table(borderline)}

## Rep-flagged but metrics pass ({len(flag_watch)})

Wall layers are 3D/hatch-named (or no clean core layer) yet closure metrics
look good — a mis-flag here would hide a usable permit; worth a spot check:

{table(flag_watch)}

## Verdict on "only 2 of ~150 usable"

**The claim was an artifact of the labeled-slice scan.** The old number came
from data/triage/closeability.csv, which (a) only scanned permits that had a
LABELED floor_plan page (~75 of ~150 then-downloaded permits), (b) scored
one page per permit, picked by a heuristic that favored section sheets, and
(c) used a fixed fpp=0.1 that mis-scored even the bank's known-good page.
Against the full corpus ({len(layered_permits)} wall-layered permits across
3,412 docs), **{len(usable)} permits pass the calibrated geometry gate**
({len(usable_old)} were already downloaded before today; the rest arrived in
the go-wider batch). Even discounting the expected ~20% false-pass rate,
the geometry-usable supply is roughly an order of magnitude larger than
"2".

## Caveats

- Candidate pages capped at top-8 per permit by harvested wall_segs
  (verified on 25-33341 that top-5 misses floor plans behind section sheets;
  top-8 has headroom but the tail is unaudited).
- Harvest scans only the first 60 pages of each doc (harvest_layered.py) and
  requires >=120 long wall-layer segments per page.
- Docs >300MB skipped (5). {n_unresolved} page-keys unresolved after retries.
- "USABLE" = rooms polygonize structurally. Scale parse, room anchoring and
  finish assignment can still fail downstream (probe24 method), and the
  19-00670 case proves the gate over-admits shredded linework ~1-in-5.
- Gate calibrated on 5 ground-truth cases total; treat the pass list as a
  prioritized work-queue for eyeball confirmation, not a settled census.
"""
    open(OUT, "w").write(md)
    print(f"wrote {OUT}")
    print(f"named-wall-layer permits: {len(layered_permits)}")
    print(f"USABLE-gate permits: {len(usable)} (old-corpus {len(usable_old)}, new-batch {len(usable_new)})")
    for p in sorted(usable):
        r = usable[p]
        print(f"  {p}  doc {r['doc_id']} p{r['page']}  mid={r['n_mid']} "
              f"cov_mid={r['cov_mid']} largest={r['largest_frac']}  [{status_of(p)}]")
    print(f"borderline: {len(borderline)}  flag-watch: {len(flag_watch)}")


if __name__ == "__main__":
    main()
