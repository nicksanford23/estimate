#!/usr/bin/env python3
"""Status-colored floor maps — one per level (founder redesign 2026-07-22).

Draws every surface's current-best outline on the full level viewport,
color-coded by state, with room numbers. One glance = where every room is
and how it's doing.

Colors: blue=accepted done, green=measured good, orange=needs nudge,
red=needs redraw, gray=needs input / specialty judgment.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
BASE = os.path.join(ROOT, "data", "sam_smoke", PERMIT)
OUT = os.path.join(BASE, "edge_gate_full")

BLUE, GREEN, ORANGE, RED, GRAY = (30, 90, 220), (0, 150, 60), (235, 140, 0), (220, 30, 30), (110, 110, 110)


def latest_decisions():
    path = os.path.join(ROOT, "data", "geometry_annotations", "human", f"{PERMIT}.outcomes.jsonl")
    out = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("decision"):
                out[r.get("task_id")] = r["decision"]
    return out


def main():
    tr = json.load(open(os.path.join(BASE, "bundle", "transforms.json")))
    surf = json.load(open(os.path.join(BASE, "surfaces.json")))["surfaces"]
    gate = json.load(open(os.path.join(OUT, "gate_results.json")))["surfaces"]
    gate_by_code = {v["code"]: v for v in gate.values()}
    rep_path = os.path.join(BASE, "inspection", "repaired_proposals.json")
    repaired = {}
    if os.path.exists(rep_path):
        for v in json.load(open(rep_path)).values():
            repaired[v["code"]] = v["polygon_pdf"]
    decisions = latest_decisions()

    try:
        f_num = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        f_leg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        f_num = f_leg = ImageFont.load_default()

    pages = {}
    for s in surf:
        pages.setdefault(s["page_index"], []).append(s)

    for pi, ss in sorted(pages.items()):
        pt = tr["pages"][str(pi)]
        ax, bx = pt["forward_affine"]["px_x"][0], pt["forward_affine"]["px_x"][2]
        ay, by = pt["forward_affine"]["px_y"][1], pt["forward_affine"]["px_y"][2]

        def px(p):
            return (p[0] * ax + bx, p[1] * ay + by)

        img = Image.open(os.path.join(BASE, "bundle", f"viewport_p{pi}.png")).convert("RGB")
        d = ImageDraw.Draw(img)
        for s in ss:
            code = s["identity_memberships"][0]
            poly = repaired.get(code) or s.get("geometry_pdf")
            g = gate_by_code.get(code)
            sid = s["surface_id"]
            dec = decisions.get(sid) or decisions.get(f"{PERMIT}:{s.get('sheet','')}:{code}")
            if g:
                verdicts = [e["verdict"] for e in g["edges"]]
                if any(v in ("unresolved_evidence", "ambiguous_pending_reviewer") for v in verdicts):
                    color = GRAY
                elif any(v == "major_redraw" for v in verdicts):
                    color = RED
                elif any(v == "minor_adjustment" for v in verdicts):
                    color = ORANGE
                elif dec == "accept":
                    color = BLUE
                else:
                    color = GREEN
            else:
                color = GRAY  # specialty / shaft / unmeasured -> your judgment pile
            if poly:
                d.polygon([px(p) for p in poly], outline=color, width=5)
                cx = sum(p[0] for p in poly) / len(poly)
                cy = sum(p[1] for p in poly) / len(poly)
                lx, ly = px((cx, cy))
                ids = "/".join(s["identity_memberships"])
                tb = d.textbbox((lx, ly), ids, font=f_num, anchor="mm")
                d.rectangle([tb[0] - 4, tb[1] - 2, tb[2] + 4, tb[3] + 2], fill=(255, 255, 255))
                d.text((lx, ly), ids, fill=color, font=f_num, anchor="mm")
        legend = "blue=done  green=good  orange=nudge  red=fix  gray=your call"
        hb = d.textbbox((8, 6), legend, font=f_leg)
        d.rectangle([0, 0, img.width, hb[3] + 10], fill=(20, 20, 20))
        d.text((8, 6), legend, fill=(255, 255, 255), font=f_leg)
        img.save(os.path.join(OUT, f"floormap_p{pi}.png"))
        print(f"floormap_p{pi}.png: {len(ss)} surfaces")


if __name__ == "__main__":
    main()
