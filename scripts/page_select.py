"""Floor-plan page selection (merged from exp_pageselect after testing on all 25).

Replaces the old "pick the page with the most compact polygons" heuristic — which
rewarded false positives and often chose phasing/demolition/overall/enlarged-detail
sheets — with a geometry-free score:

  1. drop clearly-bad-title sheets (phasing / demolition / overall / context /
     detail / schedule / roof / ceiling / elevation / section) unless nothing else;
  2. among the rest, prefer the most ROOM LABELS (room-number text in the drawing);
  3. tie-break to the earliest page.

Validated: 8/25 picks changed, all toward real floor plans (e.g. 25-33341
enlarged-detail→A-101 first floor 7→99 labels; 22-03626 generic→tenant plan
0→11), with no previously-good pick broken. Room labels rely on real text; on
vectorized-text sheets label counts are 0 and selection falls back to title+order.
"""
import re

TITLE_BAD = re.compile(r"phas|demo|overall|context|partition type|\bdetail|schedul|legend|"
                       r"\bnotes?\b|cover|index|\bsite\b|roof|ceiling|elevation|section", re.I)
TITLE_GOOD = re.compile(r"floor plan|enlarged|tenant|1st|2nd|3rd|first floor|second floor|"
                        r"level|unit|\bplan\b", re.I)
ROOM_NUM = re.compile(r"^\d{2,4}[A-Za-z]?$")


def title_score(t):
    t = t or ""
    return (2 if TITLE_GOOD.search(t) else 0) - (3 if TITLE_BAD.search(t) else 0)


def room_label_count(page):
    """# of room-number tokens in the page's real text (0 if vectorized)."""
    return sum(1 for w in page.get_text("words") if ROOM_NUM.match(w[4].strip()))


def select_floor_plan_page(doc, pages_titles):
    """pages_titles: list of (page_index, sheet_title). Returns the chosen
    page_index, or None if empty. `doc` is an open fitz document."""
    scored = []
    for pi, st in pages_titles:
        try:
            lb = room_label_count(doc[pi])
        except Exception:
            lb = 0
        scored.append((pi, st or "", lb, title_score(st)))
    if not scored:
        return None
    # non-bad title first, then most labels, then earliest page
    best = max(scored, key=lambda x: (x[3] > -1, x[2], -x[0]))
    return best[0]
