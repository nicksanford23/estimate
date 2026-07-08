#!/usr/bin/env python3
"""Shared layer->class ontology for the semantic-segmentation training idea.
A layered CAD PDF pre-sorts every line by what it is. We map each layer NAME to
one of a few classes an estimator cares about. Text/annotation is stripped FIRST
(so 'Finish tag', 'DOOR LABELS' -> annotation, not finish/door)."""
import re

# (class, keyword regex). First match wins -> annotation must come before the
# physical classes so text layers named after objects don't pollute them.
RULES = [
    ("annotation", r"tag|label|note|\bdim|text|title|bord|ref\b|leader|anno|symbol|keynote|\bkey\b|schedule|legend"),
    ("wall",       r"wall|cmu|stud|gyp|stucco|partition|mason"),
    ("door",       r"door|window|glaz|glass|storefront|\bstore|curtain|mullion|\bframe"),
    ("fixture",    r"plumb|toilet|sink|\blav|urinal|fixt|\bwc\b|bath|ada"),
    ("furniture",  r"furn|case|mill|cabinet|counter|equip|desk|appl|attic|storage above|sunscreen|beyond|shelf|eqpm"),
    ("structure",  r"grid|column|col-|colbb|struct|beam|foot|brace|\bsteel|stl\b"),
    ("finish",     r"floor|finish|carpet|\bvct|tile|ceramic|resil|epoxy|hatch|thresh|\bbase|slab|patio"),
]
_COMPILED = [(c, re.compile(p, re.I)) for c, p in RULES]

CLASSES = ["wall", "door", "fixture", "furniture", "structure", "finish", "annotation", "other"]
# RGB for the color-coded panel
COLOR = {
    "wall":       (222, 45, 38),    # red  — the boundary
    "door":       (33, 102, 220),   # blue — openings/transitions
    "fixture":    (0, 160, 160),    # teal — plumbing
    "furniture":  (150, 150, 150),  # gray — CLUTTER to ignore
    "structure":  (150, 60, 200),   # purple — grid/columns
    "finish":     (30, 170, 90),    # green — floor material
    "annotation": (205, 205, 205),  # light gray — text noise
    "other":      (120, 120, 120),
}


def classify_layer(name):
    if name is None:
        return "other"
    for cls, rx in _COMPILED:
        if rx.search(name):
            return cls
    return "other"
