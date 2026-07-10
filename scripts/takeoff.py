#!/usr/bin/env python3
"""takeoff.py -- the standing takeoff runner.

Composes already-proven probe modules (imported, not copy-pasted) into one
repeatable command:

  python3 scripts/takeoff.py run PERMIT [--doc D] [--pages P1,P2]
  python3 scripts/takeoff.py grade PERMIT
  python3 scripts/takeoff.py scoreboard

Pipeline per resolved page (see .claude/skills/sf-extraction/SKILL.md and
experiments/probe22_bank_validated.md / probe23_bank_product_states.py /
probe24_two_permit_takeoff.md for the proven lineage this reuses):

  1. RESOLVE   labeled floor_plan pages from Neon (read-only), or
               page_select.py's title+label-density pick if none labeled yet.
  2. SCALE     probe2_sf.find_scale() (pagetext regex) -> live-page regex ->
               vision_cache/scale/<doc>_<page>.json -> needs_vision_scale flag
               + a saved title-block crop (never guessed).
  3. GEOMETRY  layer-aware routing: probe7_layer_walls extraction + a
               scan_closeability-style polygonize sanity picks the LAYER path
               when named wall layers close >=5 room-band polygons; otherwise
               the RULES path (probe2b two-tier walls, unchanged).
  4. ANCHOR    label-anchored acceptance (exp_p0 idea): a polygon containing
               exactly one room-number text = named room; a note/legend
               region = artifact; a polygon containing >1 room label = an
               open_zone group. Sparse real text -> needs_vision_anchor flag
               + an outline-only crop montage (probe24's anchor_montage
               pattern) + vision_cache/anchor/<doc>_<page>.json lookup.
  5. MATERIAL  join data/triage/truth_area/ or data/triage/materials/ by room
               number if present; else flag material_todo if a finish plan
               page is labeled for the permit.
  6. OUTPUT    data/takeoff/<permit>/run.json + overlay.jpg + takeoff.md;
               append data/takeoff/scoreboard.csv.

Never writes to Neon. Deletes fetched PDFs after use.
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from shapely.ops import polygonize, unary_union  # noqa: E402

from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, seg_len, extract_drawings, snap_and_close,
    polygonize_rooms, find_scale, SCALE_RE, extract_dim_words, parse_ft_in,
)
from probe2b_sf import two_tier_wall_candidates, find_parallel_pairs, admit_minor  # noqa: E402
from probe7_layer_walls import extract_wall_layer_segments  # noqa: E402
from page_select import select_floor_plan_page  # noqa: E402
from exp_p0 import note_regions  # noqa: E402
from geometry_v2 import run_geometry_engine_v2  # noqa: E402
from geometry_v3 import run_geometry_engine_v3  # noqa: E402
from geometry_v4 import run_geometry_engine_v4  # noqa: E402
from geometry_model import (  # noqa: E402
    run_geometry_engine_model, load_wall_model_v2, DEFAULT_THRESHOLD as MODEL_ENGINE_THRESHOLD,
)

# rules-path ENGINE LADDER (probe29 Task B, then probe30/CONDITIONAL PROMOTE
# Task): "v1" is this file's own original two-tier + admit_minor +
# snap_and_close(feet_per_pt=None) composition, unchanged. v2/v3/v4 delegate
# to the geometry_vN modules' own self-contained engines (each imports/
# extends the previous one; none of them re-derive wall candidates
# independently -- see scripts/geometry_v2.py / geometry_v3.py /
# geometry_v4.py). "model" delegates to geometry_model.run_geometry_engine_model
# (wall_model_v2, the trained segment classifier, feeding the SAME v2 gap-
# closer/cavity-filter + v4 anchor-cluster proximity reconnection downstream
# -- only wall-candidate SELECTION differs from v4). "dual" (new, probe30
# CONDITIONAL PROMOTE decision) runs v4 AND model on the same page and
# reconciles them per page via `reconcile_dual_engines()` below -- see that
# function's docstring and experiments/probe30_wall_model_v2.md for why this
# ships as an additional candidate, never a silent replacement. The LAYER
# path never consults this flag -- it is a rules-path-only choice, and
# "model"/"dual" never load the model or touch a layer-routed page.
RULES_ENGINES = ("v1", "v2", "v3", "v4", "model", "dual")
# Flipped v1 -> v4 (probe29 Task B): the 3 acceptance tests in
# experiments/takeoff_harness.md show zero regression on the two layer-path
# permits (identical output, engine choice never reaches the layer path) and
# a material improvement on the rules-path permit (24-06748: 0/36 -> 5/36
# truth rooms matched, 0 -> 480 SF, 0% -> 14% coverage). See the harness doc
# for the full before/after and how to roll back (--engine v1 still works).
#
# "dual" is SHIPPED BUT NOT DEFAULT (probe30 CONDITIONAL PROMOTE task +
# quality-gate amendment): the acceptance battery in
# experiments/takeoff_harness.md ("Probe 30 follow-up" section) shows dual
# never loses winner-engine geometry and cuts confident-wrong roughly in
# half vs either single engine, BUT it fails two of the promotion bars as
# literally specced (24-06748 auto-matched 3/36 vs v4's 5/36; TRUTH_AREA
# matched<=30%err 14 vs model's 29) -- in both cases the shortfall is the
# amendment's own 40 SF plausibility floor demoting sub-40sf TRUTH rooms
# (16-39sf closets/bathrooms are real and common in these permits) to
# geometry_review. Until that floor is re-tuned against the truth room-size
# distribution, v4 stays the default and dual is opt-in via --engine dual.
DEFAULT_RULES_ENGINE = "v4"

_WALL_MODEL_CACHE = None


def get_wall_model():
    """Lazy singleton -- only loaded the first time engine="model"/"dual"
    actually reaches the rules path (never for layer-routed permits, never
    for v1-v4)."""
    global _WALL_MODEL_CACHE
    if _WALL_MODEL_CACHE is None:
        _WALL_MODEL_CACHE = load_wall_model_v2()
    return _WALL_MODEL_CACHE


def match_anchors_to_polys(rooms, anchor_dict):
    """anchor_dict: {token: (x, y)} OR {token: [(x, y), ...]} (the probe26
    grader's find_room_anchors returns multiple placements per token; the
    first placement that lands in a polygon wins). Returns {token: poly_idx}
    for tokens whose anchor point lands inside one of `rooms`. Used by
    reconcile_dual_engines to measure "how many rooms did this engine
    anchor" per page -- the mission's own promotion criterion."""
    out = {}
    for token, pts in anchor_dict.items():
        if pts and isinstance(pts[0], (int, float)):
            pts = [pts]
        for (x, y) in pts:
            pt = Point(x, y)
            hit = next((i for i, poly in enumerate(rooms) if poly.contains(pt)), None)
            if hit is not None:
                out[token] = hit
                break
    return out


DUAL_DISAGREE_FRAC = 0.15  # mission spec: >15% area disagreement on a room
                            # both engines independently anchor -> demote to
                            # geometry_review; neither engine is trusted
                            # blind on a disagreement

# --- dual-arbitration QUALITY GATES (coordinator amendment, external review):
# "prefer the engine that anchors more rooms" is gameable by an over-detecting
# engine producing confident garbage, so an anchored room only COUNTS toward
# the winner-election score if its polygon passes all of these; failing rooms
# are demoted to geometry_review (never auto), and if BOTH engines fail >50%
# of their anchored rooms the whole page demotes to review.
QUALITY_MIN_SF, QUALITY_MAX_SF = 40, 5000   # plausible-room size band
QUALITY_MAX_ASPECT = 12.0                    # bbox aspect ratio ceiling
QUALITY_DIM_CONTRADICT_FRAC = 0.30           # printed-dimension contradiction bar
QUALITY_REGION_PAD_FRAC = 0.15               # principal-region bbox padding
PAGE_DEMOTE_FAIL_FRAC = 0.50                 # both engines worse than this -> page review


def principal_region_from_labels(anchor_dict):
    """Approximate the page's principal drawing region as the (padded) bbox
    of the room-label text cluster (the amendment's own definition: room
    labels live inside the plan viewport, not in margins/title block/
    legends). Needs >=3 labels to be a meaningful cluster; returns None
    (check skipped) below that."""
    pts = []
    for v in anchor_dict.values():
        if v and isinstance(v[0], (int, float)):
            pts.append(v)
        else:
            pts.extend(v)
    if len(pts) < 3:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    padx = max((maxx - minx) * QUALITY_REGION_PAD_FRAC, 36.0)
    pady = max((maxy - miny) * QUALITY_REGION_PAD_FRAC, 36.0)
    return (minx - padx, miny - pady, maxx + padx, maxy + pady)


def poly_quality_failures(poly, feet_per_pt, region, dim_words):
    """Returns a list of human-readable quality-gate failure strings for one
    anchored polygon (empty list = passes all gates). Gates per the
    coordinator amendment: size band, principal drawing region, aspect
    ratio, printed-dimension contradiction.

    Dimension check: a printed dimension string is "matched" to this room
    iff its text bbox center falls INSIDE the polygon (dimension callouts
    for a room are drawn in/on it); the room fails only if at least one
    dimension is matched and NONE of the matched dimensions agrees with
    either bbox side within QUALITY_DIM_CONTRADICT_FRAC -- one agreeing
    dimension is enough to pass (adjacent-feature dims routinely land
    inside a room's polygon too)."""
    fails = []
    sf = poly.area * feet_per_pt ** 2 if feet_per_pt else None
    if sf is not None and not (QUALITY_MIN_SF <= sf <= QUALITY_MAX_SF):
        fails.append(f"size {sf:.0f}sf outside plausible band [{QUALITY_MIN_SF},{QUALITY_MAX_SF}]")
    minx, miny, maxx, maxy = poly.bounds
    w, h = maxx - minx, maxy - miny
    if min(w, h) > 0 and max(w, h) / min(w, h) >= QUALITY_MAX_ASPECT:
        fails.append(f"aspect ratio {max(w, h) / min(w, h):.1f}:1 >= {QUALITY_MAX_ASPECT:.0f}:1")
    if region is not None:
        c = poly.centroid
        rx0, ry0, rx1, ry1 = region
        if not (rx0 <= c.x <= rx1 and ry0 <= c.y <= ry1):
            fails.append("centroid outside principal drawing region (room-label bbox cluster)")
    if dim_words and feet_per_pt:
        w_ft, h_ft = w * feet_per_pt, h * feet_per_pt
        matched, agreed = 0, 0
        for d in dim_words:
            bx0, by0, bx1, by1 = d["bbox"]
            if not poly.contains(Point((bx0 + bx1) / 2, (by0 + by1) / 2)):
                continue
            val = parse_ft_in(d["text"])
            if not val or val < 2:
                continue
            matched += 1
            if (abs(val - w_ft) / val <= QUALITY_DIM_CONTRADICT_FRAC or
                    abs(val - h_ft) / val <= QUALITY_DIM_CONTRADICT_FRAC):
                agreed += 1
        if matched and not agreed:
            fails.append(f"contradicts all {matched} printed dimension(s) inside it by >"
                          f"{QUALITY_DIM_CONTRADICT_FRAC:.0%}")
    return fails


def quality_gate_anchor_map(rooms, anchor_map, feet_per_pt, region, dim_words):
    """Splits an engine's {token: poly_idx} anchor map into quality-PASSING
    tokens (count toward the winner-election score) and FAILING tokens
    (token -> (poly_idx, reasons); the polygon is demoted to geometry_review
    downstream). A polygon is checked once and its verdict shared by every
    token it anchors."""
    verdicts = {}
    for token, idx in anchor_map.items():
        if idx not in verdicts:
            verdicts[idx] = poly_quality_failures(rooms[idx], feet_per_pt, region, dim_words)
    passing = {t: i for t, i in anchor_map.items() if not verdicts[i]}
    failing = {t: (i, verdicts[i]) for t, i in anchor_map.items() if verdicts[i]}
    return passing, failing


def reconcile_dual_engines(name_a, rooms_a, name_b, rooms_b, anchor_dict, feet_per_pt,
                            dim_words=None, disagree_frac=DUAL_DISAGREE_FRAC):
    """Per-PAGE reconciliation of two independently-run geometry engines
    (probe30 CONDITIONAL PROMOTE decision, experiments/probe30_wall_model_v2.md
    "Promote/park reasoning", plus the external-review quality-gate
    amendment): prefer whichever engine anchors more rooms, BUT an anchored
    room only counts toward that score if its polygon passes the quality
    gates above (size band / principal region / aspect ratio / printed-
    dimension agreement) -- an over-detecting engine producing confident
    garbage can't win on raw anchor count. Then:
      - the winner's quality-FAILING anchored rooms -> geometry_review
        (noted with the failed gate(s));
      - a room the LOSING engine anchored that the winner missed ENTIRELY
        is added back as a geometry_review candidate (rescued polygons are
        DEDUPED by loser poly index -- one merged blob anchoring several
        loser-only tokens is appended once, its note lists all its tokens);
      - a room BOTH engines anchor -- each via a UNIQUELY-anchored polygon;
        a multi-token merged blob is not a per-room measurement and is
        judged by the open-zone/merge machinery instead, never used to veto
        the other engine's clean single room -- whose areas disagree by
        more than `disagree_frac` is demoted to geometry_review with an
        "engines disagree" note;
      - if BOTH engines fail quality on >PAGE_DEMOTE_FAIL_FRAC of their
        anchored rooms, the whole page demotes: every polygon gets a
        review note.

    Ties (equal quality-passing anchor counts) favor `name_a` -- callers
    pass the more mature/trusted engine (v4) as `name_a`.

    Returns (final_polys, poly_engine, poly_notes, diag):
      final_polys -- winner's full room-polygon list, PLUS loser-only
                     rescued polygons appended at the end (winner's original
                     indices unchanged, so poly_idx-keyed data lines up).
      poly_engine -- parallel list, one of name_a / name_b / "both" per index.
      poly_notes  -- parallel list of str lists; NON-EMPTY means "force
                     geometry_review, never auto_quantity".
      diag        -- counts for run.json / scoreboard provenance.
    """
    dim_words = dim_words or []
    region = principal_region_from_labels(anchor_dict)
    map_a = match_anchors_to_polys(rooms_a, anchor_dict)
    map_b = match_anchors_to_polys(rooms_b, anchor_dict)
    qual_a, fail_a = quality_gate_anchor_map(rooms_a, map_a, feet_per_pt, region, dim_words)
    qual_b, fail_b = quality_gate_anchor_map(rooms_b, map_b, feet_per_pt, region, dim_words)

    if len(qual_a) >= len(qual_b):
        winner, loser = name_a, name_b
        winner_rooms, loser_rooms = rooms_a, rooms_b
        winner_map, loser_map = map_a, map_b
        winner_qual, winner_fail, loser_qual = qual_a, fail_a, qual_b
    else:
        winner, loser = name_b, name_a
        winner_rooms, loser_rooms = rooms_b, rooms_a
        winner_map, loser_map = map_b, map_a
        winner_qual, winner_fail, loser_qual = qual_b, fail_b, qual_a

    final_polys = list(winner_rooms)
    poly_engine = [winner] * len(final_polys)
    poly_notes = [[] for _ in final_polys]

    # amendment: the winner's quality-failing anchored rooms don't ride
    # through as auto -- demote with the reason(s)
    n_quality_demoted = 0
    for token, (w_idx, reasons) in sorted(winner_fail.items()):
        note = (f"room {token!r} failed dual quality gate(s): {'; '.join(reasons)}"
                " -- geometry_review")
        if note not in poly_notes[w_idx]:
            poly_notes[w_idx].append(note)
            n_quality_demoted += 1

    # rescue loser-only rooms, deduped by loser polygon (a merged blob that
    # anchors several loser-only tokens is appended ONCE)
    rescue_by_poly = defaultdict(list)
    for token, l_idx in loser_map.items():
        if token not in winner_map:
            rescue_by_poly[l_idx].append(token)
    n_rescued = 0
    for l_idx in sorted(rescue_by_poly):
        tokens = sorted(rescue_by_poly[l_idx])
        final_polys.append(loser_rooms[l_idx])
        poly_engine.append(loser)
        poly_notes.append([f"anchored only by {loser} engine ({winner} missed room(s) "
                            f"{','.join(tokens)} entirely) -- geometry_review, never auto"])
        n_rescued += 1

    # "engines disagree" demotion: only between polygons that are each
    # UNIQUELY anchored by the token in their own engine (see docstring),
    # and only where both sides passed quality (a quality-failed room is
    # already demoted with a more specific reason)
    w_tokens_per_poly = defaultdict(int)
    for _t, i in winner_map.items():
        w_tokens_per_poly[i] += 1
    l_tokens_per_poly = defaultdict(int)
    for _t, i in loser_map.items():
        l_tokens_per_poly[i] += 1

    common = sorted(set(winner_map) & set(loser_map))
    n_disagree = 0
    for token in common:
        w_idx, l_idx = winner_map[token], loser_map[token]
        poly_engine[w_idx] = "both"
        if token not in winner_qual or token not in loser_qual:
            continue
        if w_tokens_per_poly[w_idx] != 1 or l_tokens_per_poly[l_idx] != 1:
            continue  # merged blob on either side: not a per-room measurement
        w_sf = winner_rooms[w_idx].area * feet_per_pt ** 2 if feet_per_pt else winner_rooms[w_idx].area
        l_sf = loser_rooms[l_idx].area * feet_per_pt ** 2 if feet_per_pt else loser_rooms[l_idx].area
        denom = max(w_sf, l_sf)
        pct = abs(w_sf - l_sf) / denom if denom else 0.0
        if pct > disagree_frac:
            poly_notes[w_idx].append(
                f"engines disagree on room {token!r}: {winner}={w_sf:.0f}sf vs "
                f"{loser}={l_sf:.0f}sf ({pct:.0%} apart) -- geometry_review")
            n_disagree += 1

    # amendment: both engines mostly producing quality-failing anchored
    # rooms -> don't trust the page at all, demote everything to review
    frac_fail_a = len(fail_a) / len(map_a) if map_a else 0.0
    frac_fail_b = len(fail_b) / len(map_b) if map_b else 0.0
    page_demoted = bool(map_a) and bool(map_b) and \
        frac_fail_a > PAGE_DEMOTE_FAIL_FRAC and frac_fail_b > PAGE_DEMOTE_FAIL_FRAC
    if page_demoted:
        note = (f"page demoted to review: both engines failed dual quality gates on >"
                f"{PAGE_DEMOTE_FAIL_FRAC:.0%} of their anchored rooms "
                f"({name_a} {frac_fail_a:.0%}, {name_b} {frac_fail_b:.0%})")
        for notes in poly_notes:
            if note not in notes:
                notes.append(note)

    diag = dict(winner=winner, loser=loser,
                n_anchored_a=len(map_a), n_anchored_b=len(map_b),
                n_quality_pass_a=len(qual_a), n_quality_pass_b=len(qual_b),
                quality_failures_a={t: v[1] for t, v in sorted(fail_a.items())},
                quality_failures_b={t: v[1] for t, v in sorted(fail_b.items())},
                n_winner_quality_demoted=n_quality_demoted,
                n_common_anchored=len(common), n_rescued_from_loser=n_rescued,
                n_disagree_demoted=n_disagree,
                page_demoted=page_demoted,
                principal_region=[round(v, 1) for v in region] if region else None)
    return final_polys, poly_engine, poly_notes, diag

# exp_p0/page_select's ROOM_NUM (`^\d{2,4}[A-Za-z]?$`) is too permissive on
# dense architectural sheets: 1-2 digit tokens are almost always door/
# keynote/partition-type tags sharing the same small-ellipse-callout
# convention as room numbers, not room numbers themselves (verified on the
# bank page: tokens "10", "71", "35", "75" all false-positive-anchored
# polygons that are not real rooms). Real commercial room numbering is
# consistently 3-4 digits. Tightened here rather than mutating the shared
# import.
ROOM_NUM = re.compile(r"^\d{3,4}[A-Za-z]?$")

import probe2_sf  # noqa: E402

OUT_ROOT = os.path.join(ROOT, "data", "takeoff")
# probe2_sf.download_pdf() writes into a GLOBAL tmp dir keyed only by doc_id;
# other concurrent scripts on this shared box (harvest_layered_full.py,
# scan_closeability_full.py, ...) import the same module and can delete a
# same-doc_id PDF out from under us mid-run. Retarget to our own dir, same
# fix probe3_sf.py already uses for the identical reason.
PDF_TMP_DIR = os.path.join(OUT_ROOT, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR
CACHE_SCALE = os.path.join(OUT_ROOT, "vision_cache", "scale")
CACHE_ANCHOR = os.path.join(OUT_ROOT, "vision_cache", "anchor")
SCOREBOARD = os.path.join(OUT_ROOT, "scoreboard.csv")
TRUTH_AREA_DIR = os.path.join(ROOT, "data", "triage", "truth_area")
MATERIALS_DIR = os.path.join(ROOT, "data", "triage", "materials")
for d in (OUT_ROOT, CACHE_SCALE, CACHE_ANCHOR):
    os.makedirs(d, exist_ok=True)

# green_precision (coordinator amendment): of rooms a run marked
# auto_quantity, what fraction match truth within 15% -- computable only on
# graded permits (grade rows), blank otherwise.
SB_FIELDS = ["permit", "ts", "path", "n_auto", "n_review", "n_open", "n_artifact",
             "total_sf", "graded_median_err", "graded_coverage", "green_precision", "flags"]

MIN_SQFT, MAX_SQFT = 15, 8000
ROOM_BAND_MIN_FRAC, ROOM_BAND_MAX_FRAC = 0.002, 0.08  # scan_closeability's band


# --------------------------------------------------------------- Neon (RO) --

def env():
    e = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            e[k] = v
    return e


def cur():
    import psycopg2, psycopg2.extras
    return psycopg2.connect(env()["NEON_DATABASE_URL"]).cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ------------------------------------------------------------ vision cache --

def cache_path(kind, doc_id, page_index):
    d = CACHE_SCALE if kind == "scale" else CACHE_ANCHOR
    return os.path.join(d, f"{doc_id}_{page_index}.json")


def cache_get(kind, doc_id, page_index):
    p = cache_path(kind, doc_id, page_index)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return None


# ------------------------------------------------------------------- 1. RESOLVE

def labeled_floor_plan_pages(permit, doc_arg=None):
    c = cur()
    q = """SELECT d.onestop_doc_id od, p.page_index pi, pl.sheet_title st
           FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
           JOIN estimate.page_label pl ON pl.page_id=p.id
           WHERE d.permit_num=%s AND pl.category='floor_plan'"""
    args = [permit]
    if doc_arg:
        q += " AND d.onestop_doc_id=%s"
        args.append(doc_arg)
    q += " GROUP BY d.onestop_doc_id, p.page_index, pl.sheet_title ORDER BY d.onestop_doc_id, p.page_index"
    c.execute(q, args)
    return c.fetchall()


def has_finish_labeled(permit):
    c = cur()
    c.execute("""SELECT d.onestop_doc_id od, p.page_index pi, pl.category cat, pl.sheet_title st
                 FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
                 JOIN estimate.page_label pl ON pl.page_id=p.id
                 WHERE d.permit_num=%s AND pl.category IN ('finish_plan','finish_schedule')
                 ORDER BY p.page_index""", (permit,))
    return c.fetchall()


def doc_all_pages(doc_id):
    """Fallback candidate list when nothing is labeled yet: every rendered
    page of the doc, with whatever sheet_title a label happens to carry."""
    c = cur()
    c.execute("""SELECT p.page_index pi, pl.sheet_title st
                 FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
                 LEFT JOIN estimate.page_label pl ON pl.page_id=p.id
                 WHERE d.onestop_doc_id=%s ORDER BY p.page_index""", (doc_id,))
    seen, out = set(), []
    for r in c.fetchall():
        if r["pi"] in seen:
            continue
        seen.add(r["pi"])
        out.append(r)
    return out


def permit_primary_doc(permit):
    c = cur()
    c.execute("""SELECT d.onestop_doc_id od, count(p.id) n
                 FROM estimate.document d JOIN estimate.page p ON p.document_id=d.id
                 WHERE d.permit_num=%s GROUP BY d.onestop_doc_id ORDER BY n DESC""", (permit,))
    rows = c.fetchall()
    return rows[0]["od"] if rows else None


def wall_seg_count(pdf, page_index, pw):
    """Layer-path richness: length-filtered named-layer wall segments."""
    segs, _, _, used = extract_wall_layer_segments(pdf, page_index)
    walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
    return len(walls), used


def rules_seg_count(pdf, page_index, fpp):
    """Rules-path richness: probe2b two-tier wall candidate count."""
    ex = extract_drawings(pdf, page_index)
    tiers = two_tier_wall_candidates(ex, fpp or 0.0556)
    return len(tiers["major"]) + len(tiers["minor"])


def resolve_pages(permit, doc_arg=None, pages_arg=None):
    """Returns list of dicts: {doc_id, page_index, sheet_title, resolution}."""
    if pages_arg:
        doc_id = doc_arg or permit_primary_doc(permit)
        if doc_id is None:
            raise SystemExit(f"no document found for {permit} and no --doc given")
        return [dict(doc_id=doc_id, page_index=p, sheet_title=None, resolution="explicit --pages")
                for p in pages_arg]

    rows = labeled_floor_plan_pages(permit, doc_arg)
    if rows:
        # group by doc, pick the doc with the most labeled floor_plan candidates
        by_doc = defaultdict(list)
        for r in rows:
            by_doc[r["od"]].append(r)
        doc_id = max(by_doc, key=lambda k: len(by_doc[k]))
        cands = by_doc[doc_id]
        if len(cands) == 1:
            best = cands[0]
            return [dict(doc_id=doc_id, page_index=best["pi"], sheet_title=best["st"],
                         resolution="only labeled floor_plan page")]
        # multiple candidate pages for one doc (often multiple floors/tenants
        # of the SAME building): pick the single richest one by wall-segment
        # count -- this is exactly probe24_takeoff.py's own selection method
        # ("pick the floor plan page with the most wall segs"), reproduced
        # here as the default so `run` needs no page hint on permits like the
        # bank / 26-10321. Known gap: on a genuinely multi-story permit this
        # picks ONE floor; pass --pages to target other floors explicitly.
        s3 = r2_client()
        pdf = download_pdf(s3, doc_id)
        try:
            scored = []
            for r in cands:
                pi = r["pi"]
                pg = fitz.open(pdf)[pi]
                pw = pg.rect.width
                n_layer, _ = wall_seg_count(pdf, pi, pw)
                scored.append((n_layer, r))
            scored.sort(key=lambda x: -x[0])
            if scored[0][0] > 0:
                best = scored[0][1]
                return [dict(doc_id=doc_id, page_index=best["pi"], sheet_title=best["st"],
                             resolution=f"most named-wall-layer segments ({scored[0][0]}) among "
                                        f"{len(cands)} labeled floor_plan pages")]
            # nobody has named wall layers -- rank by rules-path candidate count instead
            rscored = []
            for r in cands:
                pi = r["pi"]
                fpp, _ = find_scale(doc_id, pi)
                rscored.append((rules_seg_count(pdf, pi, fpp), r))
            rscored.sort(key=lambda x: -x[0])
            best = rscored[0][1]
            return [dict(doc_id=doc_id, page_index=best["pi"], sheet_title=best["st"],
                         resolution=f"most rules-path wall candidates ({rscored[0][0]}) among "
                                    f"{len(cands)} labeled floor_plan pages (no named layers)")]
        finally:
            os.remove(pdf)

    # nothing labeled yet -- page_select.py fallback on the permit's primary doc
    doc_id = doc_arg or permit_primary_doc(permit)
    if doc_id is None:
        raise SystemExit(f"no documents found for permit {permit}")
    pages = doc_all_pages(doc_id)
    if not pages:
        raise SystemExit(f"doc {doc_id} has no rendered pages")
    s3 = r2_client()
    pdf = download_pdf(s3, doc_id)
    try:
        doc = fitz.open(pdf)
        best = select_floor_plan_page(doc, [(r["pi"], r["st"]) for r in pages])
        doc.close()
    finally:
        os.remove(pdf)
    if best is None:
        raise SystemExit(f"page_select found nothing usable in doc {doc_id}")
    return [dict(doc_id=doc_id, page_index=best, sheet_title=None,
                 resolution="no labeled floor_plan pages -- page_select.py fallback")]


# --------------------------------------------------------------------- 2. SCALE

def resolve_scale(pdf, doc_id, page_index, run_dir):
    fpp, txt = find_scale(doc_id, page_index)
    if fpp:
        return fpp, txt, "pagetext regex", None
    page = fitz.open(pdf)[page_index]
    m = SCALE_RE.findall(page.get_text())
    if m:
        num, den = int(m[0][0]), int(m[0][1])
        return (den / num) / 72.0, f'{num}/{den}" = 1\'-0" (live page-text regex)', "live regex", None
    hit = cache_get("scale", doc_id, page_index)
    if hit:
        return hit["feet_per_pt"], hit["scale_text"], "vision-cache", None
    # no scale anywhere -- flag, save a title-block crop, do NOT guess
    pw, ph = page.rect.width, page.rect.height
    clip = fitz.Rect(pw * 0.62, ph * 0.80, pw, ph)
    zoom = 4.0
    pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    crop_path = os.path.join(run_dir, f"needs_vision_scale_{doc_id}_p{page_index}.png")
    pm.save(crop_path)
    return None, None, "unresolved", crop_path


# ------------------------------------------------------------------ 3. GEOMETRY

def layer_path_geometry(pdf, page_index, pw, ph, fpp):
    segs, _, _, used = extract_wall_layer_segments(pdf, page_index)
    walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
    lines, gap_info = snap_and_close(
        [(p0, p1, seg_len(p0, p1), w) for p0, p1, w in walls], [], pw, feet_per_pt=fpp)
    polys, n_faces = polygonize_rooms(lines, pw, ph, MIN_SQFT, MAX_SQFT, fpp)
    return polys, dict(path="layer", used_layers=used, n_wall_segs=len(walls),
                        n_polygon_faces_total=n_faces, gap_closing=gap_info)


def rules_path_geometry(pdf, page_index, pw, ph, fpp, engine=DEFAULT_RULES_ENGINE, page=None, truth=None):
    """RULES-path geometry. `engine="v1"` is this function's own original
    composition (two-tier wall candidates + admit_minor + snap_and_close
    with the generic gap closer OFF, arcs-only -- unchanged from every prior
    takeoff.py run). `engine` in ("v2","v3","v4") delegates entirely to the
    corresponding geometry_vN module's own self-contained engine (density-
    gated gap closer + cavity/hatch filter for v2; + anchor-cluster
    membership filter for v3; + directional proximity reconnection for v4
    -- see scripts/geometry_v2.py / geometry_v3.py / geometry_v4.py /
    experiments/probe27_closure_fix.md / probe28_anchor_filters.md /
    probe29_continuity_fix.md for what each adds and why).

    v3/v4 need `anchor_points` (room-code text-anchor locations) computed
    BEFORE geometry runs (the anchor-cluster filter judges "zero anchors =
    off-scope" as part of building the room set) -- this reuses the SAME
    `real_text_anchors()` step ANCHOR (step 4) would do anyway, just called
    one step earlier; `page` (the already-open fitz page) must be passed in
    for this. `truth`, if given, whitelists the anchor search to the
    schedule's own room-number list (cuts door/keynote false-positive
    anchors), same as step 4 already does.

    `engine="model"` and `engine="dual"` need the actual PDF path + page
    index too (`geometry_model.run_geometry_engine_model` does its own
    segment extraction/feature computation, a different code path from
    `extract_drawings` -- probe30's wall_model_v2, see geometry_model.py and
    experiments/probe30_wall_model_v2.md). `dual` runs v4 AND model on the
    SAME page and reconciles them via `reconcile_dual_engines()` -- see that
    function's docstring for the per-page reconciliation rule. Every branch
    returns a `poly_engine` / `poly_notes` list (parallel to the returned
    polygons) in `diag`, consumed downstream by `build_rooms()` to record
    provenance and to force-demote reconciliation-flagged polygons to
    geometry_review regardless of anchor count."""
    if engine == "v1":
        ex = extract_drawings(pdf, page_index)
        tiers = two_tier_wall_candidates(ex, fpp)
        combined = tiers["major"] + tiers["minor"]
        pairs = find_parallel_pairs(combined, fpp)
        pair_members = set()
        centerlines, seen = [], set()
        for a, b, horiz, lo, hi, c in pairs:
            pair_members.add(a); pair_members.add(b)
            key = (horiz, round(c / 2.0), round(lo / 3.0), round(hi / 3.0))
            if key in seen:
                continue
            seen.add(key)
            p0, p1 = ((lo, c), (hi, c)) if horiz else ((c, lo), (c, hi))
            centerlines.append((p0, p1, hi - lo, 0.3))
        minor_unpaired = [s for s in tiers["minor"] if s not in pair_members]
        seed = tiers["major"] + centerlines
        walls_final, n_added, n_left = admit_minor(seed, minor_unpaired, pw)
        lines, gap_info = snap_and_close(walls_final, ex["arcs"], pw, feet_per_pt=None)
        polys, n_faces = polygonize_rooms(lines, pw, ph, MIN_SQFT, MAX_SQFT, fpp)
        return polys, dict(path="rules", engine="v1", n_major=len(tiers["major"]), n_minor=len(tiers["minor"]),
                            n_parallel_pairs=len(pairs), n_minor_admitted=n_added,
                            n_polygon_faces_total=n_faces, gap_closing=gap_info,
                            poly_engine=["v1"] * len(polys), poly_notes=[[] for _ in polys])

    if engine == "model":
        whitelist = set(truth["by_room"].keys()) if truth else None
        anchor_dict = real_text_anchors(page, whitelist) if page is not None else {}
        anchor_points = list(anchor_dict.values())
        clf = get_wall_model()
        out, diag = run_geometry_engine_model(pdf, page_index, clf, fpp, anchor_points,
                                               min_sqft=MIN_SQFT, max_sqft=MAX_SQFT,
                                               threshold=MODEL_ENGINE_THRESHOLD)
        diag["path"] = "rules"
        diag["engine"] = "model"
        if out is None:
            diag["poly_engine"], diag["poly_notes"] = [], []
            return [], diag
        rooms_all = out["rooms_all"]
        diag["poly_engine"] = ["model"] * len(rooms_all)
        diag["poly_notes"] = [[] for _ in rooms_all]
        return rooms_all, diag

    if engine == "dual":
        ex = extract_drawings(pdf, page_index)
        whitelist = set(truth["by_room"].keys()) if truth else None
        anchor_dict = real_text_anchors(page, whitelist) if page is not None else {}
        anchor_points = list(anchor_dict.values())
        out4, diag4 = run_geometry_engine_v4(ex, fpp, anchor_points, MIN_SQFT, MAX_SQFT)
        clf = get_wall_model()
        outm, diagm = run_geometry_engine_model(pdf, page_index, clf, fpp, anchor_points,
                                                 min_sqft=MIN_SQFT, max_sqft=MAX_SQFT,
                                                 threshold=MODEL_ENGINE_THRESHOLD)
        rooms4 = out4["rooms_all"] if out4 else []
        roomsm = outm["rooms_all"] if outm else []
        dim_words = extract_dim_words(pdf, page_index)
        final_polys, poly_engine, poly_notes, recon_diag = reconcile_dual_engines(
            "v4", rooms4, "model", roomsm, anchor_dict, fpp, dim_words=dim_words)
        drop = ("anchor_cluster_false_positive_suspects", "cavity_hatch_killed_detail")
        diag = dict(path="rules", engine="dual",
                     v4_diag={k: v for k, v in diag4.items() if k not in drop},
                     model_diag={k: v for k, v in diagm.items() if k not in drop},
                     reconcile=recon_diag,
                     n_polys_v4=len(rooms4), n_polys_model=len(roomsm), n_polys_final=len(final_polys),
                     poly_engine=poly_engine, poly_notes=poly_notes)
        return final_polys, diag

    ex = extract_drawings(pdf, page_index)
    if engine == "v2":
        out, diag = run_geometry_engine_v2(ex, fpp, MIN_SQFT, MAX_SQFT)
    elif engine in ("v3", "v4"):
        whitelist = set(truth["by_room"].keys()) if truth else None
        anchor_dict = real_text_anchors(page, whitelist) if page is not None else {}
        anchor_points = list(anchor_dict.values())
        if engine == "v3":
            out, diag = run_geometry_engine_v3(ex, fpp, anchor_points, MIN_SQFT, MAX_SQFT)
        else:
            out, diag = run_geometry_engine_v4(ex, fpp, anchor_points, MIN_SQFT, MAX_SQFT)
    else:
        raise ValueError(f"unknown rules engine {engine!r}, expected one of {RULES_ENGINES}")

    diag["path"] = "rules"
    diag["engine"] = engine
    if out is None:
        diag["poly_engine"], diag["poly_notes"] = [], []
        return [], diag
    rooms_all = out["rooms_all"]
    diag["poly_engine"] = [engine] * len(rooms_all)
    diag["poly_notes"] = [[] for _ in rooms_all]
    return rooms_all, diag


def routing_gate_real_scale(pdf, page_index, pw, fpp):
    """scan_closeability.score_page's own gate (has_named_layer / n_mid room-
    band-polygon count / coverage), but using the PAGE'S REAL feet_per_pt
    instead of that function's fixed fpp=0.1 placeholder.

    Not a call to scan_closeability.score_page(): that placeholder is fine
    for its own use case (triage-scanning ~75 permits before any per-page
    scale is resolved -- it only needs a SCALE-FREE relative ranking), but
    it feeds feet_per_pt into snap_and_close()'s door-gap-closing radius
    (door_pt = door_ft / feet_per_pt), so a wrong placeholder measurably
    changes topology, not just units. Demonstrated on 14-11290 p3: the real
    scale is 1/4"=1'-0" (fpp=0.0556); scan_closeability's fpp=0.1 placeholder
    makes the door-closing radius ~45% too small, leaves the wall graph
    under-closed, and reports n_mid=4 (misroutes a clean, layer-usable page
    to the rules path). The same extraction with the page's real fpp closes
    cleanly (n_mid well above the gate). Once takeoff.py has actually
    resolved scale for this page (step 2 runs before step 3), reusing the
    correct value here is strictly more faithful to the mission's own
    "quick polygonize sanity" gate than the scale-free approximation."""
    segs, _, _, used = extract_wall_layer_segments(pdf, page_index)
    walls = [(p0, p1, w) for p0, p1, w in segs if seg_len(p0, p1) > 0.008 * pw]
    has_named = len(used) > 0 and len(walls) > 0
    if not walls:
        return dict(has_named_layer=has_named, n_mid=0, coverage=0.0, layers=used[:4])
    lines, _ = snap_and_close(
        [(p0, p1, seg_len(p0, p1), w) for p0, p1, w in walls], [], pw, feet_per_pt=fpp)
    polys = list(polygonize(unary_union(lines)))
    xs = [c for p0, p1, w in walls for c in (p0[0], p1[0])]
    ys = [c for p0, p1, w in walls for c in (p0[1], p1[1])]
    bbox = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    areas = [p.area for p in polys if p.area < 0.9 * bbox]
    n_mid = sum(1 for a in areas if ROOM_BAND_MIN_FRAC * bbox <= a <= ROOM_BAND_MAX_FRAC * bbox)
    coverage = sum(areas) / bbox if areas else 0.0
    return dict(has_named_layer=has_named, n_mid=n_mid, coverage=round(coverage, 3), layers=used[:4])


def route_and_extract(pdf, page_index, fpp, engine=DEFAULT_RULES_ENGINE, truth=None):
    """Layer-aware routing per the mission spec: named wall layers passing a
    quick polygonize sanity (>=5 room-band polygons, scan_closeability's own
    band) -> layer path; else the rules path. `engine` selects the rules-path
    geometry engine (v1-v4, see rules_path_geometry) -- it never affects the
    layer path, which has no engine ladder of its own."""
    doc = fitz.open(pdf)
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    gate = routing_gate_real_scale(pdf, page_index, pw, fpp)
    if gate["has_named_layer"] and gate["n_mid"] >= 5:
        polys, meta = layer_path_geometry(pdf, page_index, pw, ph, fpp)
        meta["routing_gate"] = gate
        doc.close()
        return polys, meta, pw, ph
    polys, meta = rules_path_geometry(pdf, page_index, pw, ph, fpp, engine=engine, page=page, truth=truth)
    meta["routing_gate"] = gate
    doc.close()
    return polys, meta, pw, ph


# -------------------------------------------------------------------- 4. ANCHOR

def real_text_anchors(page, whitelist=None):
    """whitelist, when given (a truth_area/materials room-number set), cuts
    false-positive anchors sharply -- door/keynote/partition tags share the
    same 2-4-digit-callout convention as room numbers and the regex alone
    can't tell them apart; a schedule's own room list can."""
    anchors = {}
    for w in page.get_text("words"):
        t = w[4].strip()
        if not ROOM_NUM.match(t):
            continue
        if whitelist is not None and t.upper() not in whitelist:
            continue
        if t not in anchors:
            anchors[t] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
    return anchors


def render_anchor_montage(pdf, page_index, polys, out_path, cols=6):
    """Outline-only crop montage, probe24's anchor_montage pattern: one tile
    per room-band polygon, background linework visible, ONLY the polygon
    outline drawn (no fill -- fill hides the room-number bubble), captioned
    with its index and SF so a later vision pass can map idx -> room number
    (cached to vision_cache/anchor/<doc>_<page>.json for reuse)."""
    doc = fitz.open(pdf)
    page = doc[page_index]
    zoom = 3.0
    pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    full = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
    doc.close()
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    order = sorted(range(len(polys)), key=lambda i: -polys[i].area)
    tiles = []
    pad_frac = 0.15
    tile_w = 320
    for i in order:
        poly = polys[i]
        minx, miny, maxx, maxy = poly.bounds
        minx, miny, maxx, maxy = minx * zoom, miny * zoom, maxx * zoom, maxy * zoom
        w, h = maxx - minx, maxy - miny
        padx, pady = w * pad_frac + 20, h * pad_frac + 20
        box = (max(0, minx - padx), max(0, miny - pady),
               min(full.width, maxx + padx), min(full.height, maxy + pady))
        crop = full.crop(tuple(map(int, box))).convert("RGB")
        scale = tile_w / max(1, crop.width)
        crop = crop.resize((tile_w, max(1, int(crop.height * scale))))
        dd = ImageDraw.Draw(crop)
        pts = [((x * zoom - box[0]) * scale, (y * zoom - box[1]) * scale)
               for x, y in poly.exterior.coords]
        dd.line(pts, fill=(220, 0, 200), width=3)
        header_h = 26
        tile = Image.new("RGB", (tile_w, crop.height + header_h), (20, 30, 90))
        tile.paste(crop, (0, header_h))
        ddh = ImageDraw.Draw(tile)
        ddh.text((4, 4), f"#{i}  {round(poly.area * 0):d}", fill=(255, 255, 255), font=font)
        tiles.append(tile)

    if not tiles:
        return None
    rows = (len(tiles) + cols - 1) // cols
    row_h = max(t.height for t in tiles)
    montage = Image.new("RGB", (tile_w * cols, row_h * rows), (255, 255, 255))
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        montage.paste(t, (c * tile_w, r * row_h))
    montage.save(out_path, quality=85)
    return order  # order[k] = original poly index shown as tile k / caption "#k"


def anchor_rooms(page, polys, pdf, page_index, doc_id, run_dir, truth=None):
    notes = note_regions(page)
    whitelist = set(truth["by_room"].keys()) if truth else None
    anchors = real_text_anchors(page, whitelist)
    poly_rooms = defaultdict(list)
    poly_artifact = set()
    for i, poly in enumerate(polys):
        c = poly.centroid
        if any(nr.contains(c) for nr in notes):
            poly_artifact.add(i)
            continue
        for t, (x, y) in anchors.items():
            if poly.contains(Point(x, y)):
                poly_rooms[i].append(t)

    n_candidates = len(polys) - len(poly_artifact)
    n_named = sum(1 for i in poly_rooms if i not in poly_artifact)
    flags = []
    montage_path = None
    if n_candidates >= 5 and n_named < max(3, int(0.3 * n_candidates)):
        flags.append("needs_vision_anchor")
        montage_path = os.path.join(run_dir, f"anchor_montage_{doc_id}_p{page_index}.jpg")
        order = render_anchor_montage(pdf, page_index, polys, montage_path)
        cache = cache_get("anchor", doc_id, page_index)
        if cache and order is not None:
            hits = 0
            for k, poly_idx in enumerate(order):
                entry = cache.get(str(poly_idx))
                if entry and poly_idx not in poly_artifact:
                    poly_rooms[poly_idx] = entry["rooms"]
                    hits += 1
            if hits:
                flags.append(f"vision-cache hit ({hits} polygons from "
                              f"vision_cache/anchor/{doc_id}_{page_index}.json)")
    return poly_rooms, poly_artifact, anchors, flags, montage_path


# ------------------------------------------------------------------- 5. MATERIAL

def load_truth(permit):
    for d, key in ((TRUTH_AREA_DIR, "truth_area"), (MATERIALS_DIR, "materials")):
        p = os.path.join(d, f"{permit}.json")
        if os.path.exists(p):
            with open(p) as f:
                data = json.load(f)
            by_room = {}
            for r in data.get("rooms", []):
                rn = str(r.get("room", "")).strip().upper()
                if rn:
                    by_room[rn] = r
            return dict(kind=key, path=p, data=data, by_room=by_room)
    return None


def material_for_room(truth, room_num):
    if not truth:
        return None
    r = truth["by_room"].get(str(room_num).strip().upper())
    if not r:
        return None
    return (r.get("floor_material_bucket") or r.get("material") or
            r.get("floor_code") or None)


# -------------------------------------------------------------------- 6. OUTPUT

ANCHOR_NAMES_CACHE = {}


def anchor_display_name(doc_id, page_index, room):
    key = (doc_id, page_index)
    if key not in ANCHOR_NAMES_CACHE:
        c = cache_get("anchor", doc_id, page_index) or {}
        names = {}
        for v in c.values():
            if isinstance(v, dict):
                names.update(v.get("names", {}))
        ANCHOR_NAMES_CACHE[key] = names
    return ANCHOR_NAMES_CACHE[key].get(room)


def build_rooms(polys, poly_rooms, poly_artifact, fpp, truth, doc_id, page_index,
                 poly_engine=None, poly_notes=None):
    """`poly_engine`/`poly_notes` (parallel to `polys`, only set by the
    rules-path dual/model/vN engines -- see rules_path_geometry) carry per-
    polygon provenance; a non-empty `poly_notes[i]` (dual reconciliation's
    "loser-only rescue" or "engines disagree" flags) forces that polygon to
    geometry_review regardless of how many room labels it anchors -- never
    auto_quantity on an engine-disagreement or a rescue-only find. Leaving
    both args None (the layer path's call, and any pre-dual rules call)
    reproduces the exact prior room-dict shape byte-for-byte (no "engine"
    key added at all)."""
    rooms = []
    open_groups = []
    n_artifact = len(poly_artifact)
    for i, poly in enumerate(polys):
        if i in poly_artifact:
            continue
        rn_list = poly_rooms.get(i, [])
        sqft = round(poly.area * fpp ** 2, 1) if fpp else None
        notes = poly_notes[i] if poly_notes else []
        forced_review = bool(notes)
        if len(rn_list) == 1 and not forced_review:
            rn = rn_list[0]
            room = dict(
                poly_index=i, room=rn, name=anchor_display_name(doc_id, page_index, rn),
                area_sf=sqft, product_action="auto_quantity",
                material=material_for_room(truth, rn),
                confidence="high" if sqft else "low",
                flags=[],
            )
        elif len(rn_list) > 1 and not forced_review:
            gid = f"open_{i}"
            open_groups.append(dict(group_id=gid, members=rn_list, area_sf=sqft, poly_index=i))
            room = dict(
                poly_index=i, room=None, name=None, area_sf=sqft,
                product_action="open_zone_split", material="mixed/TBD",
                confidence="medium", flags=[f"open_group={gid}", f"members={','.join(rn_list)}"],
            )
        else:
            rn = rn_list[0] if rn_list else None
            room = dict(
                poly_index=i, room=rn,
                name=anchor_display_name(doc_id, page_index, rn) if rn else None,
                area_sf=sqft, product_action="geometry_review",
                material=material_for_room(truth, rn) if rn else None,
                confidence="very_low",
                flags=list(notes) if notes else ["unlabeled_polygon"],
            )
        if poly_engine is not None:
            room["engine"] = poly_engine[i]
        rooms.append(room)
    return rooms, open_groups, n_artifact


def render_overlay(pdf, page_index, polys, rooms, out_path):
    doc = fitz.open(pdf)
    page = doc[page_index]
    zoom = min(3.0, 1800 / page.rect.width)
    pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    im = Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("RGBA")
    doc.close()
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(overlay, "RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    by_idx = {r["poly_index"]: r for r in rooms}
    COLORS = dict(auto_quantity=(0, 160, 70, 110), open_zone_split=(230, 140, 20, 90),
                  geometry_review=(230, 210, 0, 100))
    for i, poly in enumerate(polys):
        r = by_idx.get(i)
        col = (140, 140, 140, 70) if r is None else COLORS.get(r["product_action"], (150, 0, 150, 70))
        pts = [(x * zoom, y * zoom) for x, y in poly.exterior.coords]
        dd.polygon(pts, fill=col, outline=(0, 0, 0, 200))
        c = poly.centroid
        label = ""
        if r:
            if r.get("room"):
                label = f"{r['room']} {r['area_sf']:.0f}sf" if r["area_sf"] else r["room"]
            elif r["area_sf"]:
                label = f"{r['area_sf']:.0f}sf"
        if label:
            dd.text((c.x * zoom, c.y * zoom), label, fill=(0, 0, 0, 255), font=font)
    out = Image.alpha_composite(im, overlay).convert("RGB")
    out.save(out_path, "JPEG", quality=85)


def write_markdown(md_path, permit, doc_id, page_index, sheet_title, meta, scale_text,
                    rooms, open_groups, n_artifact, material_note, flags):
    n_auto = sum(1 for r in rooms if r["product_action"] == "auto_quantity")
    n_review = sum(1 for r in rooms if r["product_action"] == "geometry_review")
    n_open = sum(1 for r in rooms if r["product_action"] == "open_zone_split")
    total_sf = sum(r["area_sf"] for r in rooms if r["product_action"] == "auto_quantity" and r["area_sf"])
    with open(md_path, "w") as f:
        f.write(f"# Takeoff -- {permit}\n\n")
        f.write(f"doc {doc_id}  page {page_index}  ({sheet_title or 'untitled'})\n\n")
        f.write(f"- geometry path: **{meta['path']}**\n")
        f.write(f"- scale: {scale_text}\n")
        f.write(f"- auto_quantity rooms: {n_auto} ({total_sf:.0f} SF)  |  "
                f"geometry_review: {n_review}  |  open_zone_split: {n_open}  |  artifact: {n_artifact}\n")
        if flags:
            f.write(f"- flags: {', '.join(flags)}\n")
        f.write(f"- material: {material_note}\n\n")
        # "engine" column only appears when the run actually carries per-room
        # provenance (rules path with v1-v4/model/dual) -- a layer-path run's
        # markdown keeps its exact prior shape (no column added) for the
        # byte-identical acceptance check.
        show_engine = any(r.get("engine") for r in rooms)
        header = "| room | name | area_sf | product_action | material | confidence |"
        sep = "|---|---|---:|---|---|---|"
        if show_engine:
            header += " engine |"
            sep += "---|"
        f.write(header + "\n")
        f.write(sep + "\n")
        for r in sorted(rooms, key=lambda x: (x["product_action"] != "auto_quantity", -(x["area_sf"] or 0))):
            line = (f"| {r['room'] or ''} | {r['name'] or ''} | "
                    f"{r['area_sf'] if r['area_sf'] is not None else ''} | {r['product_action']} | "
                    f"{r['material'] or ''} | {r['confidence']} |")
            if show_engine:
                line += f" {r.get('engine') or ''} |"
            f.write(line + "\n")
        if open_groups:
            f.write("\n## open-zone groups\n\n")
            for g in open_groups:
                f.write(f"- {g['group_id']}: members {', '.join(g['members'])}, {g['area_sf']} SF\n")


def append_scoreboard(row):
    """Append-only in CONTENT; the header/schema migrates in place when
    SB_FIELDS gains a column (green_precision, coordinator amendment):
    existing rows are preserved verbatim, new columns backfill as blank.
    Without this, DictWriter would append rows misaligned with the old
    on-disk header."""
    row = dict(row)
    row.setdefault("green_precision", "")
    exists = os.path.exists(SCOREBOARD) and os.path.getsize(SCOREBOARD) > 0
    if exists:
        with open(SCOREBOARD, newline="") as f:
            rdr = csv.reader(f)
            header = next(rdr, None)
        if header != SB_FIELDS:
            with open(SCOREBOARD, newline="") as f:
                old_rows = list(csv.DictReader(f))
            with open(SCOREBOARD, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=SB_FIELDS, restval="")
                w.writeheader()
                for r in old_rows:
                    r.pop(None, None)
                    w.writerow({k: r.get(k, "") for k in SB_FIELDS})
    with open(SCOREBOARD, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SB_FIELDS, restval="")
        if not exists:
            w.writeheader()
        w.writerow(row)


# ------------------------------------------------------------------------ run

def run_permit(permit, doc_arg=None, pages_arg=None, engine=DEFAULT_RULES_ENGINE):
    run_dir = os.path.join(OUT_ROOT, permit)
    os.makedirs(run_dir, exist_ok=True)
    resolved = resolve_pages(permit, doc_arg, pages_arg)
    truth = load_truth(permit)
    finish_pages = has_finish_labeled(permit)

    page_results = []
    s3 = r2_client()
    for target in resolved:
        doc_id, page_index = target["doc_id"], target["page_index"]
        print(f"=== {permit}: doc {doc_id} page {page_index} "
              f"({target.get('sheet_title') or 'untitled'}) -- {target['resolution']} ===")
        pdf = download_pdf(s3, doc_id)
        try:
            flags = []
            fpp, scale_text, scale_source, crop_path = resolve_scale(pdf, doc_id, page_index, run_dir)
            if fpp is None:
                flags.append("needs_vision_scale")
                page_results.append(dict(
                    doc_id=doc_id, page_index=page_index, sheet_title=target.get("sheet_title"),
                    scale_text=None, geometry_path="none", routing_meta={}, rooms=[],
                    open_groups=[], n_artifact=0, flags=flags,
                    needs_vision_scale_crop=os.path.relpath(crop_path, ROOT) if crop_path else None,
                ))
                continue
            flags.append(f"scale_source={scale_source}")

            polys, meta, pw, ph = route_and_extract(pdf, page_index, fpp, engine=engine, truth=truth)
            if len(polys) < 3:
                # neither path produced enough to call a takeoff -- page-level
                # 'redraw' verdict per the mission's product_action enum,
                # mirrors probe3's BLOB verdict.
                page_results.append(dict(
                    doc_id=doc_id, page_index=page_index, sheet_title=target.get("sheet_title"),
                    scale_text=scale_text, geometry_path=meta["path"], routing_meta=meta,
                    rooms=[dict(poly_index=None, room=None, name=None, area_sf=None,
                                product_action="redraw", material=None, confidence="very_low",
                                flags=["fewer than 3 room-sized polygons closed"])],
                    open_groups=[], n_artifact=0, flags=flags + ["redraw"],
                    needs_vision_scale_crop=None,
                ))
                continue

            doc = fitz.open(pdf)
            page = doc[page_index]
            poly_rooms, poly_artifact, anchors, anchor_flags, montage_path = anchor_rooms(
                page, polys, pdf, page_index, doc_id, run_dir, truth)
            flags.extend(anchor_flags)
            rooms, open_groups, n_artifact = build_rooms(
                polys, poly_rooms, poly_artifact, fpp, truth, doc_id, page_index,
                poly_engine=meta.get("poly_engine"), poly_notes=meta.get("poly_notes"))

            if truth is None and finish_pages:
                flags.append(f"material_todo: finish plan labeled at doc {finish_pages[0]['od']} "
                              f"p{finish_pages[0]['pi']} ({finish_pages[0]['st']}) -- material extraction "
                              f"not automated, needs a schedule/finish-plan read")
            elif truth is None:
                flags.append("material_unknown: no truth_area/materials JSON, no finish plan labeled")

            overlay_path = os.path.join(run_dir, f"overlay_{doc_id}_p{page_index}.jpg")
            render_overlay(pdf, page_index, polys, rooms, overlay_path)
            doc.close()

            page_results.append(dict(
                doc_id=doc_id, page_index=page_index, sheet_title=target.get("sheet_title"),
                scale_text=scale_text, geometry_path=meta["path"], routing_meta=meta,
                rooms=rooms, open_groups=open_groups, n_artifact=n_artifact, flags=flags,
                overlay_path=os.path.relpath(overlay_path, ROOT),
                anchor_montage_path=os.path.relpath(montage_path, ROOT) if montage_path else None,
                n_room_label_texts_on_page=len(anchors),
            ))
        finally:
            os.remove(pdf)

    all_rooms = [r for pr in page_results for r in pr["rooms"]]
    n_auto = sum(1 for r in all_rooms if r["product_action"] == "auto_quantity")
    n_review = sum(1 for r in all_rooms if r["product_action"] == "geometry_review")
    n_open = sum(1 for r in all_rooms if r["product_action"] == "open_zone_split")
    n_artifact = sum(pr.get("n_artifact", 0) for pr in page_results)
    total_sf = sum(r["area_sf"] for r in all_rooms
                   if r["product_action"] == "auto_quantity" and r["area_sf"])
    # dual/model engine provenance (probe30 CONDITIONAL PROMOTE task): only
    # ever populated on the rules path when engine in (v1..v4, model, dual)
    # -- layer-path rooms never carry an "engine" key (build_rooms leaves the
    # dict shape untouched when poly_engine is None), so this is empty and
    # adds no flag for layer-routed permits.
    engine_counts = defaultdict(int)
    for r in all_rooms:
        if r.get("engine"):
            engine_counts[r["engine"]] += 1
    engine_flags = {"engine_provenance=" + ",".join(f"{k}:{v}" for k, v in sorted(engine_counts.items()))} \
        if engine_counts else set()
    all_flags = sorted({f for pr in page_results for f in pr["flags"]} |
                        {f"rules_engine={engine}"} | engine_flags)

    summary = dict(n_auto=n_auto, n_review=n_review, n_open=n_open, n_artifact=n_artifact,
                   total_sf=round(total_sf, 1), flags=all_flags)
    if engine_counts:
        # only added when the rules path actually recorded provenance (v1-v4/
        # model/dual) -- a layer-path run's summary dict keeps its exact prior
        # shape, no new key, for the byte-identical acceptance check.
        summary["engine_provenance"] = dict(engine_counts)

    run_json = dict(
        permit=permit, generated_at=datetime.now(timezone.utc).isoformat(),
        pages=page_results, rules_engine=engine,
        summary=summary,
        truth_source=truth["path"] if truth else None,
    )
    with open(os.path.join(run_dir, "run.json"), "w") as f:
        json.dump(run_json, f, indent=2, default=str)

    for pr in page_results:
        if pr["rooms"] and pr["geometry_path"] != "none":
            md_path = os.path.join(run_dir, f"takeoff_{pr['doc_id']}_p{pr['page_index']}.md")
            material_note = ("joined from " + os.path.basename(truth["path"]) if truth
                              else ("todo (finish plan labeled, not yet extracted)" if finish_pages
                                    else "unknown"))
            write_markdown(md_path, permit, pr["doc_id"], pr["page_index"], pr["sheet_title"],
                            pr["routing_meta"], pr["scale_text"], pr["rooms"], pr["open_groups"],
                            pr["n_artifact"], material_note, pr["flags"])

    append_scoreboard(dict(
        permit=permit, ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        path="+".join(sorted({pr["geometry_path"] for pr in page_results})),
        n_auto=n_auto, n_review=n_review, n_open=n_open, n_artifact=n_artifact,
        total_sf=round(total_sf, 1), graded_median_err="", graded_coverage="",
        flags="|".join(all_flags),
    ))

    print(f"\n=== {permit} DONE ===")
    print(f"auto={n_auto} review={n_review} open={n_open} artifact={n_artifact} "
          f"total_sf={total_sf:.0f}")
    if all_flags:
        print("flags:", "; ".join(all_flags))
    print(f"-> {os.path.relpath(run_dir, ROOT)}/run.json")
    return run_json


# ---------------------------------------------------------------------- grade

def grade_permit(permit):
    run_path = os.path.join(OUT_ROOT, permit, "run.json")
    if not os.path.exists(run_path):
        raise SystemExit(f"no run.json for {permit} -- run `takeoff.py run {permit}` first")
    with open(run_path) as f:
        run_json = json.load(f)

    truth_path = os.path.join(TRUTH_AREA_DIR, f"{permit}.json")
    if not os.path.exists(truth_path):
        print(f"{permit}: no truth_area JSON -- nothing to grade against. "
              f"(summary: auto={run_json['summary']['n_auto']} "
              f"total_sf={run_json['summary']['total_sf']})")
        append_scoreboard(dict(
            permit=permit, ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
            path="grade-no-truth", n_auto=run_json["summary"]["n_auto"],
            n_review=run_json["summary"]["n_review"], n_open=run_json["summary"]["n_open"],
            n_artifact=run_json["summary"]["n_artifact"], total_sf=run_json["summary"]["total_sf"],
            graded_median_err="", graded_coverage="", flags="no_truth_area",
        ))
        return

    with open(truth_path) as f:
        truth = json.load(f)
    truth_rooms = {str(r["room"]).strip().upper(): r for r in truth.get("rooms", [])
                   if r.get("area_sf") is not None}

    run_rooms = {}
    open_groups = []
    for pr in run_json["pages"]:
        for r in pr["rooms"]:
            if r["product_action"] == "auto_quantity" and r.get("room") and r.get("area_sf"):
                run_rooms[str(r["room"]).strip().upper()] = r["area_sf"]
        for g in pr.get("open_groups", []):
            open_groups.append(g)

    rows = []
    errs = []
    for room, truth_r in sorted(truth_rooms.items()):
        t_sf = truth_r["area_sf"]
        g_sf = run_rooms.get(room)
        if g_sf is None:
            rows.append((room, t_sf, None, None))
            continue
        err = 100 * (g_sf - t_sf) / t_sf if t_sf else None
        rows.append((room, t_sf, g_sf, err))
        if err is not None:
            errs.append(abs(err))

    # open-zone group scoring (probe23 idea): a merged blob whose member
    # rooms' truth areas sum within 10% of the group's geom SF = correct
    # grouping, not error.
    group_verdicts = []
    for g in open_groups:
        member_truth = [truth_rooms[m.upper()]["area_sf"] for m in g["members"]
                         if m.upper() in truth_rooms]
        if member_truth and g.get("area_sf"):
            t_sum = sum(member_truth)
            ok = abs(g["area_sf"] - t_sum) / t_sum <= 0.10 if t_sum else False
            group_verdicts.append(dict(group_id=g["group_id"], members=g["members"],
                                        geom_sf=g["area_sf"], truth_sum_sf=t_sum,
                                        correct_grouping=ok))

    n_matched = sum(1 for _, _, g_sf, _ in rows if g_sf is not None)
    coverage = n_matched / len(rows) if rows else 0.0
    median_err = sorted(errs)[len(errs) // 2] if errs else None

    # green_precision (coordinator amendment): of ALL rooms the run marked
    # auto_quantity (with a room number + area -- i.e. everything the product
    # would show green), the fraction whose area matches truth within 15%.
    # An auto room whose number isn't in the truth key at all counts against
    # (it is a confident claim we cannot verify as right).
    n_green_denom = len(run_rooms)
    n_green = 0
    for room, g_sf in run_rooms.items():
        t = truth_rooms.get(room)
        if t and t["area_sf"] and abs(g_sf - t["area_sf"]) / t["area_sf"] <= 0.15:
            n_green += 1
    green_precision = round(n_green / n_green_denom, 3) if n_green_denom else None

    print(f"{'room':<8}{'truth_sf':>9}{'geom_sf':>9}{'err%':>8}")
    for room, t_sf, g_sf, err in rows:
        print(f"{room:<8}{t_sf:>9}{(f'{g_sf:.0f}' if g_sf is not None else '--'):>9}"
              f"{(f'{err:+.1f}' if err is not None else '--'):>8}")
    print(f"\ncoverage: {n_matched}/{len(rows)} truth rooms matched ({coverage:.0%})")
    print(f"median |err|: {median_err:.1f}%" if median_err is not None else "median |err|: n/a (no matches)")
    print(f"green_precision: {n_green}/{n_green_denom} auto rooms within 15% of truth "
          f"({green_precision:.0%})" if green_precision is not None else
          "green_precision: n/a (no auto rooms)")
    if group_verdicts:
        print("\nopen-zone groups:")
        for gv in group_verdicts:
            verdict = "CORRECT GROUPING" if gv["correct_grouping"] else "check"
            print(f"  {gv['group_id']} members={gv['members']} geom={gv['geom_sf']:.0f} "
                  f"truth_sum={gv['truth_sum_sf']:.0f}  {verdict}")

    append_scoreboard(dict(
        permit=permit, ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        path="grade", n_auto=run_json["summary"]["n_auto"], n_review=run_json["summary"]["n_review"],
        n_open=run_json["summary"]["n_open"], n_artifact=run_json["summary"]["n_artifact"],
        total_sf=run_json["summary"]["total_sf"],
        graded_median_err=round(median_err, 1) if median_err is not None else "",
        graded_coverage=round(coverage, 3),
        green_precision=green_precision if green_precision is not None else "",
        flags=f"matched={n_matched}/{len(rows)}",
    ))


# ------------------------------------------------------------------ scoreboard

def scoreboard():
    if not os.path.exists(SCOREBOARD):
        print("no runs yet")
        return
    with open(SCOREBOARD) as f:
        rows = list(csv.DictReader(f))
    hdr = (f"{'permit':<18}{'ts':<21}{'path':<14}{'auto':>5}{'rev':>5}{'open':>5}{'art':>5}"
           f"{'total_sf':>10}{'med_err%':>9}{'cov':>6}{'green':>7}")
    print(hdr)
    for r in rows:
        print(f"{r['permit']:<18}{r['ts']:<21}{r['path']:<14}{r['n_auto']:>5}{r['n_review']:>5}"
              f"{r['n_open']:>5}{r['n_artifact']:>5}{r['total_sf']:>10}"
              f"{r['graded_median_err']:>9}{r['graded_coverage']:>6}{r.get('green_precision', ''):>7}")


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run")
    r.add_argument("permit")
    r.add_argument("--doc", type=int, default=None)
    r.add_argument("--pages", default=None, help="comma-separated page indices")
    r.add_argument("--engine", choices=RULES_ENGINES, default=DEFAULT_RULES_ENGINE,
                    help=f"rules-path geometry engine (default {DEFAULT_RULES_ENGINE}); "
                         "never affects the layer path")
    g = sub.add_parser("grade")
    g.add_argument("permit")
    sub.add_parser("scoreboard")
    a = ap.parse_args()

    if a.cmd == "run":
        pages_arg = [int(p) for p in a.pages.split(",")] if a.pages else None
        run_permit(a.permit, a.doc, pages_arg, engine=a.engine)
    elif a.cmd == "grade":
        grade_permit(a.permit)
    elif a.cmd == "scoreboard":
        scoreboard()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
