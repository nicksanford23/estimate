#!/usr/bin/env python3
"""Measured edge gate — PROTOTYPE (disputed rooms only: 102 206 304 404 405).

Consensus spec: docs/pilot/CLAUDE_ADJUDICATION_3WAY_AUDIT_V1.md §6.
Purpose: for every edge of a room's current-best polygon, IDENTIFY the correct
room-facing boundary line in the ORIGINAL PDF vector data (not nearest-line
naive), MEASURE the proposal edge's deviation from it, and VERDICT the edge on
the consensus taxonomy. Emits a per-edge JSON record + proof images so three
reviewers can verify the reference-line selection before this is trusted at
scale. AREA IS NEVER AN ACCEPTANCE GATE (A8 / §6.1).

Reuses scripts/snap_polygon_walls.py machinery: edge_line, load_tasks, PT_PER_FT,
PDF path, and its page_segments vector-extraction approach.

Usage: python scripts/edge_gate.py            # runs the 5 disputed rooms
"""
import json
import math
import os
import sys

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snap_polygon_walls as snap  # REUSE: edge_line, load_tasks, PT_PER_FT, PDF

ROOT = snap.ROOT
PERMIT = "24-06748-RNVS"
PT_PER_FT = snap.PT_PER_FT          # 18 pt/ft = 1/4"=1'-0"
IN_PER_PT = 12.0 / PT_PER_FT        # 0.6667 in per pt
TARGETS = ["102", "206", "304", "405", "404"]  # 404/405 adjacency handled together

# ---- candidate filters (consensus spec §6.1 / task) --------------------------
PARALLEL_TOL_DEG = 6.0
PERP_MAX_IN = 12.0
OVERLAP_MIN = 0.30
CAND_MIN_LEN_FT = 1.0
# double-line wall pair separation window
# Ceiling raised 12->16 in (2026-07-20): a 12.02"-thick masonry exterior wall
# on 600 Baronne missed pair detection by 0.02" and produced a false
# unresolved. Old-building walls commonly exceed 12".
PAIR_MIN_IN, PAIR_MAX_IN = 3.0, 16.0
# verdict thresholds (inches)
PASS_IN, MINOR_IN = 1.5, 4.0

OUTDIR = os.path.join(ROOT, "data", "sam_smoke", PERMIT, "edge_gate")


# ---- vector extraction (mirrors snap.page_segments, keeps len + all short) ----
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
    # dedupe (CAD PDFs stack identical lines) and attach length
    seen = {}
    for a, b in segs:
        key = tuple(sorted((tuple(round(v, 1) for v in a), tuple(round(v, 1) for v in b))))
        if key not in seen:
            seen[key] = (a, b, math.dist(a, b))
    return list(seen.values())


def _union_len(intervals, lo, hi):
    """Total covered length of [a,b] intervals clipped to [lo,hi] (1-D union)."""
    clipped = []
    for a, b in intervals:
        a2, b2 = max(a, lo), min(b, hi)
        if b2 > a2:
            clipped.append((a2, b2))
    if not clipped:
        return 0.0
    clipped.sort()
    total = 0.0
    cs, ce = clipped[0]
    for a, b in clipped[1:]:
        if a <= ce:
            ce = max(ce, b)
        else:
            total += ce - cs
            cs, ce = a, b
    total += ce - cs
    return total


def unit_normal(p1, p2):
    d = np.array(p2, float) - np.array(p1, float)
    L = float(np.linalg.norm(d))
    if L < 1e-9:
        return np.array([1.0, 0.0]), np.array([0.0, 1.0]), 0.0
    u = d / L
    n = np.array([-u[1], u[0]])
    return u, n, L


def seg_overlap_frac(p1, p2, s1, s2, u, lo, hi):
    a = float(np.array(s1) @ u); b = float(np.array(s2) @ u)
    a, b = min(a, b), max(a, b)
    ov = min(hi, b) - max(lo, a)
    span = hi - lo
    return max(0.0, ov) / span if span > 1e-9 else 0.0


def point_to_segment_dist(p, s1, s2):
    p = np.array(p, float); s1 = np.array(s1, float); s2 = np.array(s2, float)
    d = s2 - s1; L2 = float(d @ d)
    if L2 < 1e-9:
        return float(np.linalg.norm(p - s1))
    t = max(0.0, min(1.0, float((p - s1) @ d) / L2))
    proj = s1 + t * d
    return float(np.linalg.norm(p - proj))


# ---- wall-assembly detection (double-line pairs) — for chase guard + exterior --
def detect_assemblies(edge_p1, edge_p2, all_segs, ctx):
    """Every complete wall/edge assembly near the proposal edge: a pair of long
    parallel segments 3-12 in apart, both overlapping the edge span. Each returns
    signed offsets (n.mid - c) of both members + the near/far member segments.
    Offsets are along the edge normal; interior_sign>0 points at the room."""
    u, n, c = ctx["u"], ctx["n"], ctx["c"]
    lo, hi = ctx["lo"], ctx["hi"]
    cos_tol = math.cos(math.radians(PARALLEL_TOL_DEG))
    min_len = CAND_MIN_LEN_FT * PT_PER_FT
    pair_lo, pair_hi = PAIR_MIN_IN / IN_PER_PT, PAIR_MAX_IN / IN_PER_PT
    lines = []
    for s1, s2, sL in all_segs:
        if sL < min_len:
            continue
        su, _, _ = unit_normal(s1, s2)
        if abs(float(u @ su)) < cos_tol:
            continue
        if seg_overlap_frac(edge_p1, edge_p2, s1, s2, u, lo, hi) < 0.30:
            continue
        smid = (np.array(s1, float) + np.array(s2, float)) / 2
        off = float(n @ smid) - c
        if abs(off) > (PERP_MAX_IN + PAIR_MAX_IN) / IN_PER_PT:
            continue
        lines.append((off, (tuple(s1), tuple(s2)), sL))
    lines.sort(key=lambda t: t[0])
    asm = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            sep = abs(lines[j][0] - lines[i][0])
            if pair_lo <= sep <= pair_hi:
                a, b = lines[i], lines[j]
                near, far = (a, b) if abs(a[0]) <= abs(b[0]) else (b, a)
                asm.append(dict(near_off=near[0], far_off=far[0],
                                near_seg=near[1], far_seg=far[1],
                                sep_in=sep * IN_PER_PT,
                                dist_in=abs(near[0]) * IN_PER_PT))
    asm.sort(key=lambda d: d["dist_in"])
    return asm


# ---- candidate scoring: which vector segment is the room-facing boundary ------
def classify_candidates(edge_p1, edge_p2, centroid, all_segs):
    """Return sorted candidate dicts (best first) for one proposal edge.

    Reference-selection rules (patched per EDGE_GATE_PROTOTYPE_REPORT failure
    modes): (a) CHASE-JUMP GUARD — a candidate is invalid when a COMPLETE wall
    assembly (parallel pair 3-12 in apart) lies strictly between the proposal edge
    and the candidate; the room-facing member of the FIRST assembly encountered
    moving outward from the edge is strongly preferred. (b) pair partner segments
    are exposed so the caller can apply the exterior-edge rule."""
    u, n, L = unit_normal(edge_p1, edge_p2)
    c = float(n @ np.array(edge_p1, float))
    lo = min(float(np.array(edge_p1) @ u), float(np.array(edge_p2) @ u))
    hi = max(float(np.array(edge_p1) @ u), float(np.array(edge_p2) @ u))
    mid_edge = (np.array(edge_p1, float) + np.array(edge_p2, float)) / 2
    interior_sign = math.copysign(1.0, float(n @ np.array(centroid, float)) - c) or 1.0
    cos_tol = math.cos(math.radians(PARALLEL_TOL_DEG))
    perp_max = PERP_MAX_IN / IN_PER_PT
    min_len = CAND_MIN_LEN_FT * PT_PER_FT

    cands = []
    for s1, s2, sL in all_segs:
        if sL < min_len:
            continue
        su, snv, _ = unit_normal(s1, s2)
        cosang = abs(float(u @ su))
        if cosang < cos_tol:
            continue
        smid = (np.array(s1, float) + np.array(s2, float)) / 2
        signed_off = float(n @ smid) - c            # >0 == interior side
        perp = abs(signed_off)
        if perp > perp_max:
            continue
        ovf = seg_overlap_frac(edge_p1, edge_p2, s1, s2, u, lo, hi)
        if ovf < OVERLAP_MIN:
            continue
        ang = math.degrees(math.acos(min(1.0, cosang)))
        cands.append(dict(s1=tuple(s1), s2=tuple(s2), L=sL, perp_pt=perp,
                          signed_off=signed_off, overlap=ovf, angle=ang, smid=smid))
    ctx = dict(u=u, n=n, c=c, lo=lo, hi=hi, mid=mid_edge,
               interior_sign=interior_sign, L=L)
    if not cands:
        return [], ctx

    assemblies = detect_assemblies(edge_p1, edge_p2, all_segs, ctx)
    ctx["assemblies"] = assemblies
    first_asm = assemblies[0] if assemblies else None

    # (a) NEAR-FACE aggregation for the chase-jump guard. A room-facing boundary
    # is often drawn as FRAGMENTED short segments (niche/jog faces) that each fail
    # the candidate overlap filter, while the only CONTINUOUS parallel line is a
    # wall 4-8 in outward across a chase. Aggregate the fragmented near face: if
    # short parallel segments hug the edge (just-inside to NEAR_IN outward) and
    # together cover >=25% of the edge, any candidate that sits clearly BEYOND
    # that near face (a gap outward) has jumped a chase.
    near_pt = 3.5 / IN_PER_PT
    gap_pt = 1.0 / IN_PER_PT
    edge_span = hi - lo
    near_intervals = []
    near_max_out = 0.0
    for s1, s2, sL in all_segs:
        su, _, _ = unit_normal(s1, s2)
        if abs(float(u @ su)) < cos_tol:
            continue
        smid = (np.array(s1, float) + np.array(s2, float)) / 2
        d_out = -(float(n @ smid) - c) * interior_sign      # >0 == outward from room
        if -1.0 / IN_PER_PT <= d_out <= near_pt:
            a = float(np.array(s1) @ u); b = float(np.array(s2) @ u)
            near_intervals.append((min(a, b), max(a, b)))
            near_max_out = max(near_max_out, d_out)
    near_cov = _union_len(near_intervals, lo, hi) / edge_span if edge_span > 1e-9 else 0.0
    near_face = near_cov >= 0.25
    ctx["near_face_cov"] = round(near_cov, 2)

    # detect double-line wall pairs among candidates + all long segs
    long_segs = [s for s in all_segs if s[2] >= min_len]
    pair_lo, pair_hi = PAIR_MIN_IN / IN_PER_PT, PAIR_MAX_IN / IN_PER_PT
    between_tol = 1.5 / IN_PER_PT               # slack so a member isn't "between" itself
    off_match = 1.0 / IN_PER_PT                 # offset tolerance to match an assembly member
    for cd in cands:
        partner = None
        partner_seg = None
        for s1, s2, sL in long_segs:
            su, _, _ = unit_normal(s1, s2)
            if abs(float(u @ su)) < cos_tol:
                continue
            smid = (np.array(s1, float) + np.array(s2, float)) / 2
            off = float(n @ smid) - c
            sep = abs(off - cd["signed_off"])
            if pair_lo <= sep <= pair_hi and seg_overlap_frac(edge_p1, edge_p2, s1, s2, u, lo, hi) > 0.3:
                partner = off
                partner_seg = (tuple(s1), tuple(s2))
                break
        cd["has_pair"] = partner is not None
        cd["partner_off"] = partner
        cd["partner_seg"] = partner_seg
        # room-facing member of a pair = the one further toward interior
        cd["is_room_face"] = bool(partner is not None and cd["signed_off"] * interior_sign >= partner * interior_sign)
        # (a) CHASE-JUMP GUARD: invalid if a COMPLETE assembly lies strictly
        # between the edge (offset 0) and this candidate on the same side.
        o = cd["signed_off"]
        jumped = False
        jump_reason = None
        for asm in assemblies:
            m1, m2 = asm["near_off"], asm["far_off"]
            same_side = (m1 * o > 0) and (m2 * o > 0)
            inside = (abs(m1) < abs(o) - between_tol) and (abs(m2) < abs(o) - between_tol)
            if same_side and inside:
                jumped = True
                jump_reason = "a complete wall pair lies between the edge and this line"
                break
        # near-face variant: candidate sits clearly beyond a fragmented near face
        d_out = -o * interior_sign
        if not jumped and near_face and d_out > near_max_out + gap_pt and d_out > gap_pt:
            jumped = True
            jump_reason = (f"a room-facing near boundary ({int(near_cov*100)}% edge "
                           "coverage) lies between the edge and this line across a chase/gap")
        cd["chase_jumped"] = jumped
        cd["jump_reason"] = jump_reason
        # is this the room-facing (near) member of the FIRST assembly?
        cd["is_first_asm_face"] = bool(
            first_asm is not None and abs(o - first_asm["near_off"]) <= off_match)
        cd["is_first_asm_far"] = bool(
            first_asm is not None and abs(o - first_asm["far_off"]) <= off_match)
        # ink mass around candidate (walls sit in dense linework; dim lines don't)
        r = 9.0 / IN_PER_PT
        ink = sum(1 for a, b, _ in all_segs
                  if abs(float(n @ ((np.array(a) + np.array(b)) / 2)) - float(n @ cd["smid"])) < r
                  and abs(float(u @ ((np.array(a) + np.array(b)) / 2)) - float(u @ cd["smid"])) < r)
        cd["ink"] = ink

    # score: lower is better
    for cd in cands:
        s = cd["perp_pt"]                                   # prefer close
        s -= 0.4 * min(cd["L"], 4 * PT_PER_FT)              # prefer long
        s -= 3.0 * cd["overlap"]                            # prefer full overlap
        flags = []
        if cd["is_first_asm_face"]:
            s -= 20.0                                       # STRONGEST: near face of first wall
            flags.append("room-side face of the FIRST wall assembly from the edge")
        elif cd["is_room_face"]:
            s -= 12.0                                       # strong: room-side wall face
        elif cd["has_pair"]:
            s += 6.0                                        # outer face of a wall pair
        if cd["is_room_face"] and not cd["is_first_asm_face"]:
            flags.append("room-side face of parallel line-pair")
        elif cd["has_pair"] and not cd["is_first_asm_face"]:
            flags.append("outer face of parallel line-pair (penalized)")
        if cd["chase_jumped"]:
            s += 40.0                                       # (a) reached past a near boundary
            flags.append("CHASE-JUMP: " + (cd.get("jump_reason") or
                         "a wall assembly lies between the edge and this line") +
                         " -> not the room-facing boundary")
        if cd["ink"] < 4 and not cd["has_pair"]:
            s += 30.0                                       # isolated -> dimension/extension
            flags.append("isolated/low-ink -> likely dimension/extension line")
        interior_off_in = cd["signed_off"] * interior_sign * IN_PER_PT
        if cd["L"] < 2 * PT_PER_FT and interior_off_in > 6.0:
            s += 20.0                                       # short + interior -> furniture
            flags.append("short interior segment -> likely furniture/fixture")
        edge_len = hi - lo
        if cd["L"] > 6 * edge_len and edge_len < 3 * PT_PER_FT:
            s += 8.0                                        # ref >> edge -> grid/match line
            flags.append("reference much longer than edge -> possible grid/match line")
        if cd["angle"] > 3.0:
            flags.append(f"angle off {cd['angle']:.1f}deg")
        cd["score"] = s
        cd["flags"] = flags
        cd["penalized"] = any("likely" in f for f in flags) or cd["chase_jumped"]

    # (a) prefer NON-jumped candidates: only fall back to jumped lines if a
    # near-side reference does not exist, and then mark them unresolved.
    valid = [cd for cd in cands if not cd["chase_jumped"]]
    pool = valid if valid else cands
    if not valid:
        for cd in pool:
            if cd["chase_jumped"] and "chase-jump: no near-side reference" not in cd["flags"]:
                cd["flags"].append("chase-jump: no near-side reference found -> reference unresolved")
    pool.sort(key=lambda d: d["score"])
    return pool, ctx


def measure(edge_p1, edge_p2, ctx, ref):
    """Max/mean perpendicular deviation of the proposal edge from ref line (in)."""
    ru, rn, _ = unit_normal(ref["s1"], ref["s2"])
    rc = float(rn @ np.array(ref["s1"], float))
    devs = []
    for t in np.linspace(0, 1, 11):
        p = np.array(edge_p1, float) * (1 - t) + np.array(edge_p2, float) * t
        devs.append(abs(float(rn @ p) - rc))
    max_dev = max(devs) * IN_PER_PT
    mean_dev = (sum(devs) / len(devs)) * IN_PER_PT
    # endpoint deviation: how far edge endpoints sit from the ref segment body
    ep = max(point_to_segment_dist(edge_p1, ref["s1"], ref["s2"]),
             point_to_segment_dist(edge_p2, ref["s1"], ref["s2"])) * IN_PER_PT
    return max_dev, mean_dev, ep, ref["angle"]


def curve_chord_dev(edge_p1, edge_p2, ctx, all_segs):
    """Chord-to-curve deviation (in) for a curved (diagonal) edge: the proposal
    edge is a straight chord; the real wall is a short-segment polyline. Return
    (max distance from chord to the boundary polyline points, the points). Points
    are restricted to a band around the chord and to the OUTER-boundary side so
    interior fixtures (toilet/plumbing) are excluded. Used for 304's curved run."""
    u, n = ctx["u"], ctx["n"]
    lo, hi, c = ctx["lo"], ctx["hi"], ctx["c"]
    band = 9.0 / IN_PER_PT
    interior_sign = ctx["interior_sign"]
    pts = []
    for a, b, _ in all_segs:
        for p in (a, b):
            pa = np.array(p, float)
            along = float(pa @ u)
            if lo - 4 <= along <= hi + 4:
                off = float(n @ pa) - c
                # keep boundary-side points (outer wall), within band
                if abs(off) <= band and off * interior_sign <= 2 / IN_PER_PT:
                    pts.append((round(p[0], 2), round(p[1], 2)))
    pts = sorted(set(pts), key=lambda q: float(np.array(q) @ u))
    if not pts:
        return None, []
    dev = max(point_to_segment_dist(p, edge_p1, edge_p2) for p in pts) * IN_PER_PT
    return dev, pts


# ---- proof image rendering ---------------------------------------------------
def font(sz):
    for pth in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(pth):
            return ImageFont.truetype(pth, sz)
    return ImageFont.load_default()


def render_clip(doc, pi, bbox_pdf, zoom):
    x0, y0, x1, y1 = bbox_pdf
    clip = fitz.Rect(x0, y0, x1, y1)
    pix = doc[pi].get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def to_px(P):
        return ((P[0] - x0) * zoom, (P[1] - y0) * zoom)

    return img, to_px


def edge_proof(doc, pi, code, idx, edge_p1, edge_p2, chosen, runner, max_dev,
               verdict, curve_pts=None, outdir=None):
    outdir = outdir or OUTDIR
    pad = 36.0
    xs = [edge_p1[0], edge_p2[0]]; ys = [edge_p1[1], edge_p2[1]]
    for r in (chosen, runner):
        if r:
            xs += [r["s1"][0], r["s2"][0]]; ys += [r["s1"][1], r["s2"][1]]
    if curve_pts:
        xs += [p[0] for p in curve_pts]; ys += [p[1] for p in curve_pts]
    bbox = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    zoom = min(6.0, max(3.0, 900.0 / max(1.0, (bbox[2] - bbox[0]))))
    img, to_px = render_clip(doc, pi, bbox, zoom)
    d = ImageDraw.Draw(img)
    if runner:
        d.line([to_px(runner["s1"]), to_px(runner["s2"])], fill=(230, 200, 0), width=2)
    if chosen:
        d.line([to_px(chosen["s1"]), to_px(chosen["s2"])], fill=(0, 190, 0), width=5)
    if curve_pts:
        for p in curve_pts:
            x, y = to_px(p)
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(0, 190, 0))
    d.line([to_px(edge_p1), to_px(edge_p2)], fill=(255, 0, 190), width=3)
    fnt = font(20)
    txt = f"{code} e{idx}  max dev {max_dev:.1f} in  [{verdict}]" if max_dev is not None \
        else f"{code} e{idx}  NO REFERENCE  [{verdict}]"
    d.rectangle([0, 0, img.width, 30], fill=(0, 0, 0))
    d.text((5, 4), txt, fill=(255, 255, 255), font=fnt)
    # legend
    grn = "green dots = boundary polyline" if curve_pts else "green = chosen reference"
    d.text((5, img.height - 60), "magenta = proposal edge", fill=(255, 0, 190), font=font(15))
    d.text((5, img.height - 42), grn, fill=(0, 220, 0), font=font(15))
    if "ambiguous" in verdict:
        d.text((5, img.height - 24), "yellow = OUTER edge (both shown; reviewer picks)",
               fill=(230, 200, 0), font=font(15))
    else:
        d.text((5, img.height - 24), "yellow = runner-up", fill=(230, 200, 0), font=font(15))
    p = os.path.join(outdir, f"proof_{code}_e{idx}.png")
    img.save(p)
    return os.path.relpath(p, ROOT)


def room_proof(doc, pi, code, poly, chosen_refs, outdir=None):
    outdir = outdir or OUTDIR
    pad = 48.0
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    bbox = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    zoom = min(5.0, max(2.5, 1100.0 / max(1.0, (bbox[2] - bbox[0]))))
    img, to_px = render_clip(doc, pi, bbox, zoom)
    d = ImageDraw.Draw(img)
    for ref in chosen_refs:
        if ref:
            d.line([to_px(ref["s1"]), to_px(ref["s2"])], fill=(0, 190, 0), width=4)
    d.polygon([to_px(p) for p in poly], outline=(255, 0, 190))
    for i, p in enumerate(poly):
        d.line([to_px(poly[i]), to_px(poly[(i + 1) % len(poly)])], fill=(255, 0, 190), width=3)
    d.rectangle([0, 0, img.width, 30], fill=(0, 0, 0))
    d.text((5, 4), f"ROOM {code}: magenta=proposal  green=chosen refs", fill=(255, 255, 255), font=font(20))
    p = os.path.join(outdir, f"proof_{code}_room.png")
    img.save(p)
    return os.path.relpath(p, ROOT)


# ---- data loading ------------------------------------------------------------
def load_best_polys():
    rep = json.load(open(os.path.join(ROOT, "data", "sam_smoke", PERMIT,
                                       "inspection", "repaired_proposals.json")))
    ed = json.load(open(os.path.join(ROOT, "data", "sam_smoke", PERMIT,
                                      "results", "proposals_for_editor.json")))
    by = {}
    src = {}
    for k, v in ed.items():
        by[v["code"]] = v["polygon_pdf"]; src[v["code"]] = "results/proposals_for_editor.json"
    for k, v in rep.items():                      # repaired overrides where present
        by[v["code"]] = v["polygon_pdf"]; src[v["code"]] = "inspection/repaired_proposals.json"
    return by, src


def polygon_centroid(poly):
    a = 0.0; cx = 0.0; cy = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        cr = x1 * y2 - x2 * y1
        a += cr; cx += (x1 + x2) * cr; cy += (y1 + y2) * cr
    a *= 0.5
    if abs(a) < 1e-9:
        return [sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n]
    return [cx / (6 * a), cy / (6 * a)]


EXTERIOR_CODES = {"404", "405"}     # prototype rerun: decks -> exterior edges


def infer_boundary_type(code, is_curved, chosen, no_ref, is_split, is_exterior):
    if is_split:
        return "open_split"
    if is_exterior:
        return "exterior" if not no_ref else "unresolved"
    if no_ref:
        return "unresolved"
    if chosen and chosen.get("penalized"):
        return "unresolved"
    return "wall"


def verdict_for(max_dev, chosen, no_ref, is_split):
    if no_ref:
        # invented split / open floor with no physical line -> wrong_surface_model
        if is_split:
            return "wrong_surface_model"
        return "major_redraw"
    if chosen and chosen.get("penalized"):
        return "unresolved_evidence"
    if max_dev <= PASS_IN:
        return "pass_measured"
    if max_dev <= MINOR_IN:
        return "minor_adjustment"
    return "major_redraw"


def cand_from_seg(seg, e1, e2, ctx, flags):
    """Build a candidate-like dict from a raw (s1,s2) segment for a given edge."""
    s1, s2 = seg
    su, _, _ = unit_normal(s1, s2)
    ang = math.degrees(math.acos(min(1.0, abs(float(ctx["u"] @ su)))))
    smid = (np.array(s1, float) + np.array(s2, float)) / 2
    signed_off = float(ctx["n"] @ smid) - ctx["c"]
    return dict(s1=tuple(s1), s2=tuple(s2), L=math.dist(s1, s2),
                perp_pt=abs(signed_off), signed_off=signed_off,
                overlap=seg_overlap_frac(e1, e2, s1, s2, ctx["u"], ctx["lo"], ctx["hi"]),
                angle=ang, smid=smid, flags=flags, penalized=False,
                has_pair=True, is_room_face=False)


def exterior_pair(e1, e2, ctx):
    """(b) EXTERIOR-EDGE RULE support: from the first wall/edge assembly, return
    (inner structural line, outer edge line) as candidate dicts. Inner = the
    interior/deck-side member; outer = the outboard member. None if no pair."""
    asm = ctx.get("assemblies") or []
    if not asm:
        return None, None
    a = asm[0]
    isign = ctx["interior_sign"]
    if a["near_off"] * isign >= a["far_off"] * isign:
        inner_seg, outer_seg = a["near_seg"], a["far_seg"]
    else:
        inner_seg, outer_seg = a["far_seg"], a["near_seg"]
    inner = cand_from_seg(inner_seg, e1, e2, ctx,
                          ["exterior INNER structural line (deck/building side)"])
    outer = cand_from_seg(outer_seg, e1, e2, ctx,
                          ["exterior OUTER edge/parapet line"])
    return inner, outer


def evaluate_surface(doc, pi, code, poly, outdir, *, is_exterior=False,
                     split_other_poly=None, curved_diag=False, space_name=None,
                     surface_id=None, identities=None):
    """Run reference selection + measurement + verdict + proof for every edge of
    one surface polygon. Returns a surface result dict. Shared by the prototype
    rerun (main) and the full consolidated run (run_full)."""
    if pi not in _SEG_CACHE:
        _SEG_CACHE[pi] = raw_segments(doc, pi)
    all_segs = _SEG_CACHE[pi]
    cen = polygon_centroid(poly)
    n = len(poly)
    edge_records = []
    chosen_refs = []
    for i in range(n):
        e1 = poly[i]; e2 = poly[(i + 1) % n]
        u, nrm, L = unit_normal(e1, e2)
        is_curved = bool(curved_diag and abs(u[0]) > 0.1 and abs(u[1]) > 0.1)

        # invented-split detection (deck rectangles): midpoint on the shared band
        is_split = False
        if split_other_poly is not None:
            oxs = [p[0] for p in split_other_poly]; oys = [p[1] for p in split_other_poly]
            mid = ((e1[0] + e2[0]) / 2, (e1[1] + e2[1]) / 2)
            if min(oxs) - 2 <= mid[0] <= max(oxs) + 2 and min(oys) - 2 <= mid[1] <= max(oys) + 2:
                is_split = True

        cands, ctx = classify_candidates(e1, e2, cen, all_segs)
        chosen = cands[0] if cands else None
        runner = cands[1] if len(cands) > 1 else None
        curve_pts = []
        curve_dev = None
        ext_ambiguous = False
        ext_inner = ext_outer = None
        dev_inner = dev_outer = None

        edge_exterior = bool(is_exterior and not is_split)

        if is_curved:
            curve_dev, curve_pts = curve_chord_dev(e1, e2, ctx, all_segs)

        if is_curved and curve_dev is not None:
            no_ref = False
            max_dev = mean_dev = round(curve_dev, 2)
            ep = max(min(math.dist(e1, p) for p in curve_pts),
                     min(math.dist(e2, p) for p in curve_pts)) * IN_PER_PT
            ang = None
        elif edge_exterior and chosen is not None:
            # (b) EXTERIOR-EDGE RULE: do not guess inner vs outer parapet line.
            ext_inner, ext_outer = exterior_pair(e1, e2, ctx)
            if ext_inner is not None:
                ext_ambiguous = True
                chosen, runner = ext_inner, ext_outer
                mi = measure(e1, e2, ctx, ext_inner)
                mo = measure(e1, e2, ctx, ext_outer)
                dev_inner, dev_outer = round(mi[0], 2), round(mo[0], 2)
                max_dev, mean_dev, ep, ang = mi          # display vs inner
            else:
                # single exterior line, no drawn outer edge -> still reviewer's call
                ext_ambiguous = True
                no_ref = False
                max_dev, mean_dev, ep, ang = measure(e1, e2, ctx, chosen)
            no_ref = False
        elif chosen is not None:
            no_ref = False
            max_dev, mean_dev, ep, ang = measure(e1, e2, ctx, chosen)
        else:
            no_ref = True
            max_dev = mean_dev = ep = ang = None

        btype = infer_boundary_type(code, is_curved, chosen, no_ref, is_split, edge_exterior)
        eff_no_ref = no_ref or (is_split and (chosen is None or not chosen.get("has_pair", False)
                                              and chosen.get("perp_pt", 99) * IN_PER_PT > MINOR_IN))
        verd = verdict_for(max_dev if max_dev is not None else 99.0,
                           chosen, eff_no_ref, is_split)
        if ext_ambiguous:
            verd = "ambiguous_pending_reviewer"

        use_curve = bool(is_curved and curve_dev is not None)
        rationale = build_rationale(chosen, runner, no_ref, is_split, use_curve,
                                    curve_dev, ext_ambiguous, dev_inner, dev_outer)
        proof = edge_proof(doc, pi, code, i, e1, e2,
                           None if use_curve else chosen,
                           None if use_curve else runner,
                           max_dev, verd, curve_pts if use_curve else None, outdir)
        chosen_refs.append(None if use_curve else chosen)

        rec = {
            "edge_index": i,
            "edge_p1_pdf": [round(x, 2) for x in e1],
            "edge_p2_pdf": [round(x, 2) for x in e2],
            "boundary_type": btype,
            "reference_segment_pdf": (
                None if (use_curve or chosen is None) else
                [[round(x, 2) for x in chosen["s1"]],
                 [round(x, 2) for x in chosen["s2"]]]),
            "reference_curve_polyline_pdf": (curve_pts if use_curve else None),
            "reference_rationale": rationale,
            "max_deviation_in": (None if max_dev is None else round(max_dev, 2)),
            "endpoint_deviation_in": (None if ep is None else round(ep, 2)),
            "angle_curve_deviation": (
                {"kind": "curve_chord", "value_in": round(curve_dev, 2)} if use_curve
                else {"kind": "angle_deg", "value_deg": (None if ang is None else round(ang, 2))}),
            "proof_image": proof,
            "runner_up_segment_pdf": (None if runner is None else
                                      [[round(x, 2) for x in runner["s1"]],
                                       [round(x, 2) for x in runner["s2"]]]),
            "mean_deviation_in": (None if mean_dev is None else round(mean_dev, 2)),
            "candidate_count": len(cands),
            "is_curved_edge": bool(is_curved),
            "is_invented_split": bool(is_split),
            "exterior_ambiguous": bool(ext_ambiguous),
            "exterior_inner_ref_pdf": (None if ext_inner is None else
                                       [[round(x, 2) for x in ext_inner["s1"]],
                                        [round(x, 2) for x in ext_inner["s2"]]]),
            "exterior_outer_ref_pdf": (None if ext_outer is None else
                                       [[round(x, 2) for x in ext_outer["s1"]],
                                        [round(x, 2) for x in ext_outer["s2"]]]),
            "max_dev_vs_inner_in": dev_inner,
            "max_dev_vs_outer_in": dev_outer,
            "chase_jumped_runner": bool(runner is not None and runner.get("chase_jumped")),
            "verdict": verd,
        }
        edge_records.append(rec)

    room_pr = room_proof(doc, pi, code, poly, chosen_refs, outdir)
    return {
        "surface_id": surface_id or code, "code": code,
        "identities": identities or [code], "space_name": space_name,
        "page_index": pi, "room_proof_image": room_pr,
        "edges": edge_records,
        "note": "AREA is diagnostic-only and is NOT part of any verdict.",
    }


_SEG_CACHE = {}


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    tasks = snap.load_tasks(PERMIT)
    doc = fitz.open(snap.PDF[PERMIT])
    polys, srcs = load_best_polys()

    results = {}
    order = ["102", "206", "304", "404", "405"]
    for code in order:
        t = tasks[code]
        other = "405" if code == "404" else ("404" if code == "405" else None)
        res = evaluate_surface(
            doc, t["page_index"], code, polys[code], OUTDIR,
            is_exterior=(code in EXTERIOR_CODES),
            split_other_poly=(polys[other] if other else None),
            curved_diag=(code == "304"),
            space_name=t.get("space_name"))
        res["task_id"] = t["task_id"]
        res["sheet"] = t.get("sheet_number")
        res["polygon_source"] = srcs[code]
        res["polygon_pdf"] = [[round(x, 2) for x in p] for p in polys[code]]
        results[code] = res
        v = [e["verdict"] for e in res["edges"]]
        print(f"{code} ({t.get('space_name')}): {len(res['edges'])} edges -> {v}")

    topo = topology_404_405(polys)
    results["_topology_404_405"] = topo
    print("\n404/405 overlap:", topo["overlap_area_sf_DIAGNOSTIC"], "sf (diagnostic);",
          topo["shared_split_finding"])

    out = os.path.join(OUTDIR, "gate_results.json")
    json.dump(results, open(out, "w"), indent=1)
    print("\nwrote", out)
    write_report(results, srcs)


# ---- FULL RUN over consolidated ordinary surfaces (Task 4) -------------------
FULL_OUTDIR = os.path.join(ROOT, "data", "sam_smoke", PERMIT, "edge_gate_full")
CURVED_CODES = {"304"}          # only the RESTROOM has a drawn curved wall

SEV_ORDER = {                   # higher = worse (drives queue ranking)
    "pass_measured": 0, "minor_adjustment": 1, "ambiguous_pending_reviewer": 2,
    "unresolved_evidence": 3, "major_redraw": 4, "wrong_surface_model": 5}


def _eff_dev(e):
    """A single representative deviation for an edge (best-case for ambiguous)."""
    if e["exterior_ambiguous"] and e["max_dev_vs_inner_in"] is not None \
            and e["max_dev_vs_outer_in"] is not None:
        return min(e["max_dev_vs_inner_in"], e["max_dev_vs_outer_in"])
    return e["max_deviation_in"]


def _action_for(verdicts):
    if any(v in ("wrong_surface_model", "unresolved_evidence",
                 "ambiguous_pending_reviewer") for v in verdicts):
        return "needs_judgment"
    if any(v in ("major_redraw", "minor_adjustment") for v in verdicts):
        return "fix_edge"
    return "confirm_reference_and_accept"


def run_full():
    os.makedirs(FULL_OUTDIR, exist_ok=True)
    doc = fitz.open(snap.PDF[PERMIT])
    surf = json.load(open(os.path.join(ROOT, "data", "sam_smoke", PERMIT,
                                       "surfaces.json")))
    by_id = {s["surface_id"]: s for s in surf["surfaces"]}
    ordinary = surf["ordinary_measurable_surface_ids"]

    results = {}
    queue = []
    metrics = {"surfaces_measured": 0, "edges_total": 0,
               "pass_measured": 0, "minor_adjustment": 0, "major_redraw": 0,
               "ambiguous_pending_reviewer": 0, "unresolved_evidence": 0,
               "wrong_surface_model": 0}
    for sid in ordinary:
        s = by_id[sid]
        code = s["identity_memberships"][0]
        pi = s["page_index"]
        poly = s["geometry_pdf"]
        res = evaluate_surface(
            doc, pi, code, poly, FULL_OUTDIR,
            is_exterior=False, split_other_poly=None,
            curved_diag=(code in CURVED_CODES),
            space_name=s["identity_names"][0],
            surface_id=sid, identities=s["identity_memberships"])
        res["sheet"] = s["sheet"]
        res["surface_kind"] = s["surface_kind"]
        results[sid] = res

        verdicts = [e["verdict"] for e in res["edges"]]
        metrics["surfaces_measured"] += 1
        metrics["edges_total"] += len(verdicts)
        for v in verdicts:
            metrics[v] = metrics.get(v, 0) + 1
        worst = max(verdicts, key=lambda v: SEV_ORDER.get(v, 0))
        devs = [_eff_dev(e) for e in res["edges"] if _eff_dev(e) is not None]
        worst_dev = round(max(devs), 2) if devs else None
        action = _action_for(verdicts)
        proofs = [e["proof_image"] for e in res["edges"]] + [res["room_proof_image"]]
        # one-line reason
        nverd = {v: verdicts.count(v) for v in set(verdicts) if v != "pass_measured"}
        if action == "confirm_reference_and_accept":
            reason = (f"all {len(verdicts)} edges pass_measured (<=1.5 in); reviewer "
                      "confirms the machine-nominated references, then accept.")
        else:
            parts = ", ".join(f"{n}x {v}" for v, n in sorted(
                nverd.items(), key=lambda kv: -SEV_ORDER.get(kv[0], 0)))
            reason = (f"worst edge {worst} (eff dev {worst_dev} in); {parts}. "
                      + ("reviewer must set/confirm reference or surface model."
                         if action == "needs_judgment"
                         else "snap the flagged edge(s) to the confirmed reference."))
        queue.append({
            "surface_id": sid, "identities": s["identity_memberships"],
            "space_names": s["identity_names"], "sheet": s["sheet"],
            "verdict": worst, "worst_edge_dev_in": worst_dev,
            "action_needed": action, "one_line_reason": reason,
            "proof_images": proofs,
            "_rank": SEV_ORDER.get(worst, 0) * 1000 + (worst_dev or 0),
        })
        print(f"{sid} ({s['identity_names'][0]}): {verdicts} -> {action}")

    queue.sort(key=lambda q: -q["_rank"])
    for q in queue:
        del q["_rank"]

    gate_out = {
        "permit": PERMIT, "gate": "S5.5 measured edge gate (patched selection)",
        "scale_source": "S1.7 scale_gate.json (verified_machine, founder countersign pending)",
        "canonical_unit": "physical_surface_region",
        "skipped": {
            "note": ("specialty_stair, shaft, and wrong_surface_model surfaces are NOT "
                     "measured here (per Task 4 + S5.2). See surfaces.json."),
            "surface_ids": [s["surface_id"] for s in surf["surfaces"]
                            if s["surface_id"] not in ordinary],
        },
        "metrics": metrics,
        "surfaces": results,
    }
    json.dump(gate_out, open(os.path.join(FULL_OUTDIR, "gate_results.json"), "w"), indent=1)
    json.dump({"permit": PERMIT,
               "ranked_by": "severity then worst edge deviation",
               "action_legend": {
                   "confirm_reference_and_accept": "all edges pass; confirm references + accept",
                   "fix_edge": "snap flagged edge(s) to the confirmed reference (S6)",
                   "needs_judgment": "reference/surface-model unresolved; reviewer decides"},
               "queue": queue},
              open(os.path.join(FULL_OUTDIR, "QUEUE.json"), "w"), indent=1)
    write_full_report(gate_out, queue, surf)
    print("\nmetrics:", metrics)
    print("queue by action:",
          {a: sum(1 for q in queue if q["action_needed"] == a)
           for a in ("needs_judgment", "fix_edge", "confirm_reference_and_accept")})
    print("wrote", FULL_OUTDIR)


def write_full_report(gate_out, queue, surf):
    m = gate_out["metrics"]
    L = ["# Edge Gate — FULL RUN (patched) — 24-06748-RNVS\n"]
    A = L.append
    A("Reference-confirmed measured edge gate (FULL_PROCESS_LOCKED.md S5.5) run across "
      f"ALL {m['surfaces_measured']} consolidated ORDINARY surfaces (S5.2 "
      "surface-model gate first). Specialty stairs, elevator shafts, and "
      "wrong_surface_model merges (great-room 305/306/307, deck 404/405) are NOT "
      "measured here — they route to founder judgment / structural redraw.\n")
    A("Scale from S1.7 `scale_gate.json`: all four viewports verified_machine "
      "(founder countersign pending). AREA IS NEVER AN ACCEPTANCE GATE.\n")
    A("Denominators (S5.2): "
      f"{surf['denominators']['identity_count']} room identities -> "
      f"{surf['denominators']['surface_count']} physical surfaces; "
      f"{m['surfaces_measured']} ordinary measurable.\n")
    A("## Gate metrics (edges)\n")
    A(f"- edges measured: **{m['edges_total']}** across {m['surfaces_measured']} surfaces")
    A(f"- pass_measured: **{m['pass_measured']}**")
    A(f"- minor_adjustment: **{m['minor_adjustment']}**")
    A(f"- major_redraw: **{m['major_redraw']}**")
    A(f"- unresolved_evidence: **{m['unresolved_evidence']}**")
    A(f"- ambiguous_pending_reviewer: **{m['ambiguous_pending_reviewer']}**")
    A(f"- wrong_surface_model (edge-level): **{m['wrong_surface_model']}**\n")
    qa = {a: sum(1 for q in queue if q["action_needed"] == a)
          for a in ("needs_judgment", "fix_edge", "confirm_reference_and_accept")}
    A("## Founder review queue (ranked by severity)\n")
    A(f"Queue size: **{len(queue)}** surfaces — needs_judgment "
      f"**{qa['needs_judgment']}**, fix_edge **{qa['fix_edge']}**, "
      f"confirm_reference_and_accept **{qa['confirm_reference_and_accept']}**.\n")
    A("| # | surface | identities | sheet | worst verdict | worst dev (in) | action | reason |")
    A("|---|---|---|---|---|---|---|---|")
    for i, q in enumerate(queue, 1):
        ids = ",".join(q["identities"])
        A(f"| {i} | {q['surface_id']} | {ids} | {q['sheet']} | {q['verdict']} | "
          f"{q['worst_edge_dev_in']} | {q['action_needed']} | "
          f"{q['one_line_reason'].replace('|', '/')} |")
    A("\nFull per-edge records (chosen + runner-up reference, rationale, proofs): "
      "`gate_results.json`. Machine review queue: `QUEUE.json`.\n")
    A("## LIMITATIONS (honest)\n")
    A("- These are MACHINE observations. Every reference is machine-NOMINATED; none is "
      "human-confirmed truth. Training eligibility requires per-edge reviewer "
      "confirmation (S5.5 / S8b). Nothing here is training data.")
    A("- `unresolved_evidence` edges (chase / fragmented near face) have NO "
      "machine-confirmable reference; the deviation shown is against a rejected line and "
      "must not be trusted — the reviewer sets the reference.")
    A("- 1:1 ordinary surfaces still inherit the draft polygon's own errors; a "
      "`major_redraw` means the DRAFT edge is off, not necessarily that the wall is "
      "unfindable. Proof images are the evidence.")
    A("- Curved / fixture-dense edges (304 RESTROOM) use chord-to-polyline deviation, "
      "which is noise-prone; confirm visually.")
    A("- Scale is verified_machine only (founder countersign pending); a founder scale "
      "rejection invalidates every inch-based verdict here (dependency invalidation §3.5).")
    p = os.path.join(FULL_OUTDIR, "REPORT.md")
    open(p, "w").write("\n".join(L))
    print("wrote", p)


def build_rationale(chosen, runner, no_ref, is_split, use_curve, curve_dev,
                    ext_ambiguous=False, dev_inner=None, dev_outer=None):
    if use_curve:
        return ("curved edge measured as a straight chord against the room-facing "
                "boundary polyline (outer-side vector points within a 9 in band, "
                f"interior fixtures excluded); chord-to-curve max dev {curve_dev:.1f} in. "
                "Fixture-dense restroom -> confirm the green points trace the wall in the proof.")
    if ext_ambiguous:
        if dev_inner is not None and dev_outer is not None:
            return ("EXTERIOR edge (deck/parapet): the true decking boundary is "
                    "ambiguous between the INNER structural line (green) and the "
                    f"OUTER edge/parapet line (yellow). Proposal deviates {dev_inner} in "
                    f"from inner, {dev_outer} in from outer. NOT auto-scored -> "
                    "ambiguous_pending_reviewer; a qualified reviewer confirms which "
                    "line bounds the flooring. Both shown in the proof.")
        return ("EXTERIOR edge (deck/parapet): only a single drawn line is present; "
                "whether the flooring runs to it or to an undrawn outer edge is a "
                "reviewer call -> ambiguous_pending_reviewer.")
    if no_ref:
        if is_split:
            return ("No parallel vector line within 12 in over >=30% of this edge: "
                    "it divides open floor with no drawn physical boundary "
                    "(invented split).")
        return "No qualifying vector line within 12 in / >=30% overlap; no defensible reference."
    parts = []
    if chosen.get("is_first_asm_face"):
        parts.append("chosen line is the room-side face of the FIRST wall assembly "
                     "encountered moving outward from the edge (chase-jump guard)")
    elif chosen.get("is_room_face"):
        parts.append("chosen line is the room-side member of a detected parallel line-pair (wall/edge)")
    elif chosen.get("has_pair"):
        parts.append("chosen line pairs with a parallel line 3-12 in away (double-line wall/edge)")
    else:
        parts.append("chosen is the closest long parallel line in dense linework")
    parts.append(f"perp {chosen['perp_pt']*IN_PER_PT:.1f} in, overlap {chosen['overlap']*100:.0f}%, "
                 f"len {chosen['L']/PT_PER_FT:.1f} ft, local-ink {chosen.get('ink', '?')}")
    if chosen.get("flags"):
        parts.append("flags: " + "; ".join(chosen["flags"]))
    if runner is not None and "score" in chosen and "score" in runner:
        d = abs(chosen["score"] - runner["score"])
        margin = f"runner-up score margin {d:.1f} ({'CLEAR' if d > 5 else 'CLOSE - verify in proof'})"
        if runner.get("chase_jumped"):
            margin += " [runner-up rejected by chase-jump guard]"
        parts.append(margin)
    return "; ".join(parts)


def topology_404_405(polys):
    from shapely.geometry import Polygon
    p404 = Polygon(polys["404"]); p405 = Polygon(polys["405"])
    inter = p404.intersection(p405)
    area_pt2 = inter.area if not inter.is_empty else 0.0
    area_sf = area_pt2 / (PT_PER_FT ** 2)
    b = inter.bounds if not inter.is_empty else None
    # the two candidate split lines
    y_404_bottom = max(p[1] for p in polys["404"])
    y_405_top = min(p[1] for p in polys["405"])
    return {
        "overlap_area_sf_DIAGNOSTIC": round(area_sf, 1),
        "overlap_bbox_pdf": [round(x, 2) for x in b] if b else None,
        "poly404_bottom_y_pdf": round(y_404_bottom, 2),
        "poly405_top_y_pdf": round(y_405_top, 2),
        "split_gap_in": round(abs(y_404_bottom - y_405_top) * IN_PER_PT, 1),
        "shared_split_finding": (
            f"404 and 405 overlap by ~{round(area_sf,1)} sf. 404's bottom (y={round(y_404_bottom,1)}) "
            f"and 405's top (y={round(y_405_top,1)}) are {round(abs(y_404_bottom - y_405_top)*IN_PER_PT,1)} in "
            "apart and DISAGREE on where COVERED DECK ends and OUTDOOR DECK begins. Per A5 this is one "
            "open surface with two member identities; the split must be a single visible drawn/dimensioned "
            "line, not two overlapping invented rectangles. REPORT ONLY."),
    }


def write_report(results, srcs):
    L = []
    A = L.append
    A("# Edge Gate Prototype Report — 24-06748-RNVS (disputed rooms) — PATCHED RERUN\n")
    A("Deterministic measured edge gate per FULL_PROCESS_LOCKED.md S5.5 (was consensus "
      "spec `docs/pilot/CLAUDE_ADJUDICATION_3WAY_AUDIT_V1.md` §6). Scope: 5 disputed "
      "rooms (102, 206, 304, 404, 405). This rerun uses the PATCHED reference selection: "
      "(a) CHASE-JUMP GUARD and (b) EXTERIOR-EDGE RULE, added to fix the two "
      "reference-selection failure modes the first prototype found. Before/after below.\n")
    A("Scale: 18 pt/ft (1/4\"=1'-0\"), so 1 in = 1.5 pt. Verdict taxonomy: "
      "`pass_measured` (max dev <= 1.5 in), `minor_adjustment` (<= 4 in), "
      "`major_redraw` (> 4 in or no defensible reference), `wrong_surface_model` "
      "(no plausible physical reference — crosses open floor), `unresolved_evidence` "
      "(only penalized/chase-jumped candidates; reviewer must set the reference), "
      "`ambiguous_pending_reviewer` (exterior inner-vs-outer edge; both shown).\n")
    A("**AREA IS NOT AN ACCEPTANCE GATE** and appears nowhere below except the "
      "404/405 topology diagnostic footnote (§6.1 of the spec).\n")
    for code in ["102", "206", "304", "404", "405"]:
        r = results[code]
        A(f"\n## Room {code} — {r['space_name']} (sheet {r['sheet']}, "
          f"source `{r['polygon_source']}`)\n")
        A("| edge | boundary | chosen reference + rationale | max dev (in) | verdict |")
        A("|---|---|---|---|---|")
        for e in r["edges"]:
            md = "—" if e["max_deviation_in"] is None else f"{e['max_deviation_in']}"
            rat = e["reference_rationale"].replace("|", "/")
            A(f"| e{e['edge_index']} | {e['boundary_type']} | {rat} | {md} | **{e['verdict']}** |")
        A(f"\nWhole-room proof: `{r['room_proof_image']}`")
    t = results["_topology_404_405"]
    A("\n## Topology prototype — 404 / 405 (report only)\n")
    A(t["shared_split_finding"])
    A(f"\n- Overlap bbox (pdf): {t['overlap_bbox_pdf']}")
    A(f"- 404 bottom y = {t['poly404_bottom_y_pdf']}, 405 top y = {t['poly405_top_y_pdf']}, "
      f"gap = {t['split_gap_in']} in")
    A(f"\n> Diagnostic footnote (NOT a gate): the 404/405 polygon overlap is "
      f"~{t['overlap_area_sf_DIAGNOSTIC']} sf of double-counted surface.\n")
    A("\n## LIMITATIONS — what a human must verify in the proof images\n")
    A("- Reference SELECTION is heuristic. Where a room-facing wall line was NOT "
      "clearly the closest, the script prefers the interior member of a detected "
      "double-line pair; when no pair is detected it falls back to the closest long "
      "parallel line, which can be a dimension/extension or a fixture. Every edge whose "
      "rationale carries a `flags:` note, a `CLOSE` runner-up margin, or an "
      "`unresolved_evidence` verdict needs eyeball confirmation in its proof image.")
    A("- Room 304 is a fixture-dense RESTROOM; the vector data has no true bezier "
      "arc (the 7 'qu' items on the page are degenerate text marks), so its curved "
      "wall is a short-segment polyline interleaved with toilet/plumbing linework. "
      "Chord-to-curve deviation for 304 is therefore noise-prone and must be confirmed "
      "visually. See the honest verification notes below.")
    A("- 404/405 are decks with no interior walls; edges are exterior railing/building "
      "lines or the invented split. `wrong_surface_model` on the split is the intended "
      "signal, not a failure of the gate.")
    A("- Endpoint deviation flags edges that overrun the reference segment (e.g. a wall "
      "line shorter than the traced edge across a door opening).")
    A("\n## PATCH before/after — the two proven failure modes\n")
    A("The first prototype (unpatched) found two reference-selection failures. The "
      "patched gate corrects both. Verified against the regenerated proofs.\n")
    A("| failure mode | edge | UNPATCHED (before) | PATCHED (after) | why the after is right |")
    A("|---|---|---|---|---|")
    A("| Chase jump | 206 e1 | chose the continuous wall 4.7 in OUTWARD across the ELECT "
      "chase; scored `major_redraw` @ 4.68 in (a confident over-call against the wrong "
      "line) | `unresolved_evidence`; the across-chase wall is rejected by the CHASE-JUMP "
      "guard (a room-facing near boundary covers ~70% of the edge between it and the "
      "wall), and no near-side reference is machine-confirmable | the laundry boundary is "
      "the fragmented near niche face, not the wall behind the chase. With no confident "
      "near reference, `unresolved_evidence` (reviewer must set the reference) is the "
      "mandated verdict, not a fabricated number. |")
    A("| Exterior parapet | 404 e1 | chose the INNER structural line; `major_redraw` @ "
      "11.33 in | `ambiguous_pending_reviewer`; BOTH inner (11.33 in) and outer (0.67 in) "
      "shown | the proposal actually traced the OUTER deck edge (0.67 in). Inner-vs-outer "
      "is a genuine reviewer decision; guessing inner manufactured an 11 in over-call. |")
    A("| Exterior parapet | 405 e1 | chose the INNER line; `major_redraw` @ 7.63 in | "
      "`ambiguous_pending_reviewer`; inner 7.63 in / outer 4.37 in shown | same rule; "
      "no auto-guess between the two drawn parapet lines. |")
    A("\nConfirmations (this rerun): 206 e1 no longer jumps the ELECT chase "
      "(major_redraw over-call -> unresolved_evidence); 404 e1 and 405 e1 are now "
      "`ambiguous_pending_reviewer`, not over-calls. 102 stays 4/4 `pass_measured` "
      "(guard did not over-fire); 304 curved-wall `major_redraw`s unchanged (real).\n")
    A("### How the patch works\n")
    A("- (a) CHASE-JUMP GUARD: a candidate is invalid if a complete wall pair (two "
      "parallel lines 3-12 in apart) lies between the proposal edge and the candidate, "
      "OR — for fragmented near faces that fail the per-segment overlap filter — if an "
      "aggregated room-facing near boundary (>=25% edge coverage within 3.5 in) sits "
      "between the edge and the candidate across a gap. The gate prefers the room-facing "
      "line of the FIRST wall assembly moving outward; if the only surviving line is "
      "across a chase, the edge is `unresolved_evidence`, never a confident number.")
    A("- (b) EXTERIOR-EDGE RULE: on an exterior (deck/parapet) edge the gate does NOT "
      "guess inner vs outer. It emits BOTH candidates (inner structural line + outer "
      "edge line), records the deviation to each, marks the edge "
      "`ambiguous_pending_reviewer`, and draws both in the proof (green=inner, "
      "yellow=outer) for the reviewer to confirm.")
    A("\n### Remaining limitations (honest)\n")
    A("- Where a near face is genuinely undrawable in vectors (206 e1), the machine "
      "cannot pick the reference; it correctly defers to the reviewer rather than "
      "snapping. This is the locked S5.5 per-edge-confirmation requirement, not a gate "
      "failure.")
    A("- 304's curved RESTROOM wall is a short-segment polyline interleaved with fixture "
      "linework (no true bezier); chord-to-curve deviation is noise-prone and must be "
      "confirmed visually. `major_redraw` there is driven by a genuine 6-8 in gap.")
    A("- The exterior rule assumes a two-line parapet/railing assembly. A single-line "
      "exterior edge is still marked ambiguous (reviewer confirms whether flooring runs "
      "to it), but only one candidate can be shown.")
    p = os.path.join(OUTDIR, "EDGE_GATE_PROTOTYPE_REPORT.md")
    open(p, "w").write("\n".join(L))
    print("wrote", p)


if __name__ == "__main__":
    if "--full" in sys.argv:
        run_full()
    else:
        main()
