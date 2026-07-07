#!/usr/bin/env python3
"""The honesty guard (post-processing stage) -- per .claude/skills/sf-extraction
SKILL.md's binding-constraint fix identified in probe 3: room polygons must be
backed by printed room-label TEXT, or they must not be trusted, no matter how
clean the polygon math looks. Probe 3 found 2/18 pages where the mechanical
pipeline FABRICATED plausible-looking rooms out of a wall-partition-detail
LEGEND box and passed the numeric self-audit anyway -- this stage is a purely
textual/geometric cross-check, independent of the wall-tracing pipeline,
applied AFTER polygonize_rooms() and BEFORE any SF number is trusted or shown.

Usage as a library:
    from sf_guard import run_guard
    guard_rows = run_guard(rooms_json, pdf_path, page_index)
    # -> list of dicts, one per room, each with: room_idx, sqft, n_labels,
    #    labels_found, in_legend_region, verdict ('accept'|'reject'|'merged'),
    #    confidence, reason

Rules (per task spec):
  (a) polygon with ZERO detected room-label words inside -> reject.
  (b) polygon inside/mostly-overlapping (>=50% of its own area) a detected
      legend/notes/keynote/schedule region -> reject (regardless of any
      numeric-looking tokens found inside -- legend index numbers like "1",
      "2", "16" look exactly like small room-number tags; this rule is
      what actually has to catch that, not the label-count rule).
  (c) polygon containing >=3 room-label words -> verdict 'merged' (flagged,
      not trusted for an SF number, but not deleted from view either).
  (d) polygon with exactly 1-2 room-label words, NOT in a legend region ->
      accept.

v2 anchor-quality rules (added after validating v1 on the 18 probe-3 pages:
v1 caught the legend-box fabrication 25/25 but FALSE-ACCEPTED 21 rooms on
15-08510-NEWC, every one anchored solely by bare number tags -- a sequential
keynote/riser run "10".."22" plus "906" repeated 5x -- while all 21 keyword
labels on that page fell outside every polygon):
  (e) anchor tiers: keyword/keyword_phrase = STRONG; number tag with 3-4
      digits or a letter/decimal/dash suffix ("109", "112A", "205.1") =
      MEDIUM; bare 2-digit tag ("10".."99") = WEAK. A polygon whose only
      anchors are WEAK is rejected -- 2-digit bare numbers collide with
      dimensions, keynote indices, and riser counts far too often to trust
      alone (measured: the 15-08510 fabrication's tags 10-22, plus the
      17-10173 BLOB's lone "11").
  (f) repeated-tag: the same tag TEXT anchoring >2 disjoint accepted
      polygons is a keynote/typical-unit callout, not room numbering
      ("906" x5 on 15-08510) -> all its polygons rejected. Threshold >2 so
      a legit duplicated pair survives.
  (g) area-callout: a MEDIUM tag that parses to a round multiple of 50,
      >=250, and >3x the polygon's own computed sqft is an area callout
      ("1000 SF") for a bigger unit sitting inside a sliver fragment
      ("1000" inside a 26.8-sqft polygon on 18-29543) -> that tag does not
      count as an anchor. Deliberately narrow (mult-of-50 AND ratio): a
      real hotel-room tag like "906" on a 97-sqft room is 9.3x but not a
      multiple of 50 -- room numbers encode floor, not size, so ratio
      alone must NOT reject.
  Accept confidence: 'high' if any STRONG anchor, 'medium' if best anchor
  is MEDIUM, 'low' if the only surviving MEDIUM anchor looked callout-ish
  by ratio but failed the mult-of-50 test (kept, flagged).

COORDINATE-SPACE NOTE (found while building this): fitz's get_drawings() and
get_text("words") both return RAW, UNROTATED content-stream coordinates
(matching page.mediabox, not page.rect) -- confirmed by direct inspection of
15-08510-NEWC page 8, a page.rotation=90 sheet, where get_drawings() segment
x/y ranges matched the *mediabox* dimensions, not page.rect's swapped
dimensions. Since probe2_sf.py's rooms_json polygon_pts come straight from
get_drawings()-derived geometry and this module's word bboxes come straight
from get_text("words") on the SAME page, both are already in the same frame
-- no rotation transform is needed for containment/overlap tests here. (A
rotation transform IS needed to render a human-readable overlay PNG; see
render_guard_overlay() below, which is a separate, corrected code path from
probe2/2b/3's render_overlay(), which does NOT correct for rotation and
mis-locates its overlay on rotated pages -- a bug this probe's validation
run happened to surface, noted in the final report.)
"""
import json
import os
import re
import sys
from collections import defaultdict

import fitz  # PyMuPDF
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import ROOT  # noqa: E402

# --------------------------------------------------------------- patterns --

ROOM_KEYWORDS = [
    "BEDROOM", "BED\\s?RM", "BATH(ROOM)?", "BATH\\s?RM", "HALL(WAY)?",
    "STAIR(S|WAY)?", "OFFICE", "KITCHEN", "DINING", "LIVING", "CLOSET",
    "LAUNDRY", "GARAGE", "FOYER", "ENTRY", "ENTRANCE", "LOBBY", "CORRIDOR",
    "MECH(ANICAL)?", "ELEV(ATOR)?", "RESTROOM", "STORAGE", "UTILITY",
    "VESTIBULE", "CONFERENCE", "RETAIL", "TENANT", "SUITE", "UNIT", "PANTRY",
    "DEN", "STUDY", "POWDER", "LOUNGE", "BREAK\\s?ROOM", "JAN(ITOR)?\\.?",
    "TRASH", "DUMPSTER", "APARTMENT", "GYM", "PATIO", "PORCH", "DECK",
    "BALCONY", "TERRACE", "PARKING", "RECEPTION", "WAITING", "EXAM",
    "TREATMENT", "WORK\\s?ROOM", "ATRIUM", "COURTYARD", "SERVER",
    "ELECTRICAL", "WATER\\s?HEATER", "ATTIC", "CRAWL", "BASEMENT", "LOFT",
    "MASTER", "GUEST", "CLASSROOM", "CAFETERIA", "LOCKER", "SHOWER",
    "VAULT", "SALES", "DISPLAY", "HOUSEKEEPING", "LINEN", "CHASE", "SHAFT",
    "MEN", "WOMEN", "STOREFRONT", "LANDING", "MORTGAGE", "BANK", "TELLER",
    "CANOPY", "SCUPPER", "ROOF",
]
KEYWORD_RE = re.compile(r"^(" + "|".join(ROOM_KEYWORDS) + r")S?\.?$", re.IGNORECASE)

# room-number tags: "115", "205.1", "112A", "208-1"
NUMBER_TAG_RE = re.compile(r"^\d{2,4}([.\-]\d{1,2})?[A-Za-z]?$")

# "703 SF" / "236SF" area callouts -- count as a label anchor too (always
# printed next to/inside the named room)
SQFT_RE = re.compile(r"^\d{2,6}(\.\d)?$")  # first token of an "N SF" pair

LEGEND_ANCHOR_RE = re.compile(
    r"\b(LEGEND|KEYNOTE|KEY\s?NOTES?|SCHEDULE|GENERAL\s+NOTES|ABBREVIATIONS?|"
    r"SYMBOLS?|WALL\s+TYPES?|WALL\s+PARTITION)\b", re.IGNORECASE)

# tokens that must NOT be treated as bare number-tags even though they're
# digit-only, because they're almost always something else in context
DIM_CHARS = set("'\"/")


def _looks_like_dim(tok):
    return any(c in DIM_CHARS for c in tok)


# ---------------------------------------------------------------- words ----

def _group_words_by_line(words):
    by_line = defaultdict(list)
    for w in words:
        x0, y0, x1, y1, txt, block, line, wn = w
        by_line[(block, line)].append((wn, x0, y0, x1, y1, txt))
    lines = []
    for key, items in by_line.items():
        items.sort()
        x0 = min(i[1] for i in items)
        y0 = min(i[2] for i in items)
        x1 = max(i[3] for i in items)
        y1 = max(i[4] for i in items)
        phrase = " ".join(i[5] for i in items)
        lines.append(dict(bbox=(x0, y0, x1, y1), text=phrase, words=items))
    return lines


def find_room_label_words(page):
    """Returns list of dicts: bbox (single-word bbox), text, kind."""
    words = page.get_text("words")
    labels = []
    lines = _group_words_by_line(words)
    # (1) keyword phrases -- test both the whole line phrase and each
    # individual word, so "CONFERENCE ROOM" and lone "KITCHEN" both hit.
    for ln in lines:
        if KEYWORD_RE.match(ln["text"].strip()):
            labels.append(dict(bbox=ln["bbox"], text=ln["text"], kind="keyword_phrase"))
    for w in words:
        x0, y0, x1, y1, txt, block, line, wn = w
        tok = txt.strip()
        if _looks_like_dim(tok):
            continue
        if KEYWORD_RE.match(tok):
            labels.append(dict(bbox=(x0, y0, x1, y1), text=tok, kind="keyword"))
        elif NUMBER_TAG_RE.match(tok):
            labels.append(dict(bbox=(x0, y0, x1, y1), text=tok, kind="number_tag"))
    # dedupe identical bbox+text entries (keyword line vs single-word overlap)
    seen = set()
    uniq = []
    for lb in labels:
        key = (lb["bbox"], lb["text"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(lb)
    return uniq


def find_legend_regions(page, pad=28.0, min_lines=3):
    """Connected-component union of text LINES that are spatially close
    (within `pad` pt of each other, both axes) and whose component contains
    at least one LEGEND/KEYNOTE/SCHEDULE/NOTES/WALL-TYPES anchor phrase.
    Returns list of shapely boxes (one per qualifying connected component).
    Also returns a second class of region: locally very dense multi-line
    text blocks (>=8 lines within a tight bounding box on the page margin)
    even with no explicit anchor keyword -- schedules/legends without an
    exact header match still read as one dense uniform text brick, unlike a
    room-labeled floor plan which is sparse text over open white space."""
    words = page.get_text("words")
    lines = _group_words_by_line(words)
    n = len(lines)
    if n == 0:
        return []
    boxes = [box(*ln["bbox"]).buffer(pad) for ln in lines]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if boxes[i].intersects(boxes[j]):
                union(i, j)

    comp = defaultdict(list)
    for i in range(n):
        comp[find(i)].append(i)

    regions = []
    for idxs in comp.values():
        texts = " ".join(lines[i]["text"] for i in idxs)
        has_anchor = bool(LEGEND_ANCHOR_RE.search(texts))
        is_dense_block = len(idxs) >= min_lines and _is_dense(lines, idxs)
        if has_anchor or is_dense_block:
            u = unary_union([box(*lines[i]["bbox"]) for i in idxs])
            regions.append(dict(
                region=u, n_lines=len(idxs), has_anchor=has_anchor,
                sample_text=texts[:80],
            ))
    return regions


def _is_dense(lines, idxs):
    """A crude 'this reads like a schedule/legend table, not a floor plan'
    check: multi-line text block where the union bbox area is mostly filled
    by individual line bboxes (>=25% areal coverage) -- floor-plan room
    labels are sparse single words/short tags scattered over big open
    (white) polygons; legend/schedule tables are lines of text stacked
    almost edge-to-edge."""
    bxs = [lines[i]["bbox"] for i in idxs]
    minx = min(b[0] for b in bxs)
    miny = min(b[1] for b in bxs)
    maxx = max(b[2] for b in bxs)
    maxy = max(b[3] for b in bxs)
    union_area = (maxx - minx) * (maxy - miny)
    if union_area <= 0:
        return False
    text_area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in bxs)
    return (text_area / union_area) >= 0.25


# --------------------------------------------------------------- guard ----

def run_guard(rooms_json, pdf_path, page_index, legend_overlap_frac=0.5):
    """rooms_json: list of dicts with at least 'polygon_pts' (list of
    [x,y] in the SAME raw fitz coordinate space as get_drawings()/
    get_text("words") on that page -- i.e. exactly probe2_sf.py's
    rooms_json format) and 'sqft'. Returns one guard-row dict per input
    room, in the same order."""
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    labels = find_room_label_words(page)
    legend_regions = find_legend_regions(page)
    doc.close()

    label_pts = [(Point((lb["bbox"][0] + lb["bbox"][2]) / 2,
                         (lb["bbox"][1] + lb["bbox"][3]) / 2), lb)
                 for lb in labels]

    rows = []
    for room in rooms_json:
        poly = Polygon(room["polygon_pts"])
        if not poly.is_valid:
            poly = poly.buffer(0)
        inside = [lb for pt, lb in label_pts if poly.contains(pt)]
        n_labels = len(inside)

        legend_frac = 0.0
        legend_hit = None
        for reg in legend_regions:
            inter = poly.intersection(reg["region"])
            if poly.area > 0:
                frac = inter.area / poly.area
            else:
                frac = 0.0
            if frac > legend_frac:
                legend_frac = frac
                legend_hit = reg
        in_legend = legend_frac >= legend_overlap_frac

        if in_legend:
            verdict, confidence = "reject", "reject"
            reason = (f"{legend_frac*100:.0f}% of polygon area overlaps a "
                      f"detected legend/notes/schedule region "
                      f"(anchor={legend_hit['has_anchor']}, "
                      f"sample={legend_hit['sample_text']!r})")
        elif n_labels == 0:
            verdict, confidence = "reject", "reject"
            reason = "zero room-label words found inside polygon"
        elif n_labels >= 3:
            verdict, confidence = "merged", "flagged_no_sf_trust"
            reason = (f"{n_labels} room-label words inside one polygon -- "
                      "likely an unresolved merged blob, SF not trustworthy")
        else:
            verdict, confidence = "accept", "high"
            reason = f"{n_labels} room-label word(s) found inside, no legend overlap"

        rows.append(dict(
            room_idx=room.get("room_idx"),
            sqft=room.get("sqft"),
            n_labels=n_labels,
            labels_found=[lb["text"] for lb in inside][:8],
            legend_overlap_frac=round(legend_frac, 2),
            verdict=verdict,
            confidence=confidence,
            reason=reason,
        ))
    return rows


def guard_summary(rows):
    c = defaultdict(int)
    for r in rows:
        c[r["verdict"]] += 1
    return dict(c)


if __name__ == "__main__":
    print(__doc__)
