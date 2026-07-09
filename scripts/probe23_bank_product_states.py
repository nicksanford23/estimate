#!/usr/bin/env python3
"""Probe 23 — reframe bank geometry as product actions, not raw failures.

Uses the already-rendered Probe 15 room crops plus Probe 22's independent
dimension reads. The important output is the action the product should take:
auto quantity, ask for geometry review, or split an open zone by finish.
"""
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_MANIFEST = os.path.join(ROOT, "data", "probe15", "manifest.json")
OUT = os.path.join(ROOT, "data", "probe23")
os.makedirs(OUT, exist_ok=True)

VDIM = {
    101: 78, 102: 202, 103: 223, 104: 156, 105: 190, 106: 119,
    107: 119, 108: 220, 109: 100, 110: 113, 111: 67, 112: 68,
    113: 115, 114: 37, 115: 52, 116: 54, 117: 38, 118: 23,
}

MATERIAL = {
    101: "Tile", 102: "Tile", 103: "Carpet", 104: "Carpet",
    105: "Carpet", 106: "Carpet", 107: "Carpet", 108: "Carpet",
    109: "Carpet", 110: "Carpet", 111: "Carpet", 112: "Tile",
    113: "Resilient", 114: "Carpet", 115: "Resilient",
    116: "Resilient", 117: "Carpet", 118: "Resilient",
}

OPEN_GROUP = {
    102: "front_of_house_open_zone",
    103: "front_of_house_open_zone",
    105: "front_of_house_open_zone",
    110: "copy_mortgage_open_zone",
    111: "copy_mortgage_open_zone",
}

MANUAL_FAILURE_MODE = {
    101: (
        "true_fragment",
        "Rotated storefront/glass vestibule with multiple door leaves. The "
        "polygon catches the central vestibule fragment but misses the full "
        "vestibule footprint implied by the printed dimensions. Probe 17 found "
        "no nearby missing-wall gap, so this is a storefront/glass/door "
        "semantic failure rather than simple endpoint closure.",
    ),
    109: (
        "door_opening_review",
        "Mostly enclosed office, but the polygon crosses the doorway/opening "
        "edge and comes out 25% above the dimension read. Keep as a geometry "
        "review case, not a model-wide wall failure. Probe 17 sees only "
        "hairline gaps and a small door/opening nearby.",
    ),
    114: (
        "service_core_corridor_zone",
        "Corridor label sits inside a hatched restroom/service-core area with "
        "door swings and attic-storage annotation. The polygon measures the "
        "larger service-zone shape, not a clean corridor path. Probe 17 sees "
        "only hairline gaps nearby, so the issue is semantic zoning.",
    ),
}


def validation(geom_sf, dim_sf):
    if geom_sf is None:
        return "open"
    diff = (geom_sf - dim_sf) / dim_sf
    adiff = abs(diff)
    if adiff <= 0.15:
        return "validated"
    if adiff <= 0.30:
        return "check"
    return "disagree"


def product_action(room, is_open, verdict):
    if is_open:
        return "open_zone_split"
    if verdict == "validated":
        return "auto_quantity"
    if room == 101:
        return "vision_correct_or_redraw"
    return "geometry_review"


def confidence(action, verdict):
    if action == "auto_quantity":
        return "high"
    if action == "open_zone_split":
        return "medium"
    if verdict == "check":
        return "low"
    return "very_low"


def main():
    with open(IN_MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)

    rows = []
    for item in manifest:
        room = int(item["room"])
        geom_sf = item["geom_sf"]
        dim_sf = VDIM[room]
        verdict = validation(geom_sf, dim_sf)
        action = product_action(room, item["open"], verdict)
        if geom_sf is None:
            diff_pct = None
        else:
            diff_pct = round(100 * (geom_sf - dim_sf) / dim_sf, 1)
        mode, note = MANUAL_FAILURE_MODE.get(room, ("none", ""))
        if item["open"]:
            mode = "open_plan_not_wall_failure"
            note = (
                "No full-height wall separates this label from its neighboring "
                "open area. Split by finish/material boundary instead of "
                "forcing a separate closed room polygon."
            )

        rows.append({
            "room": room,
            "name": item["name"],
            "material": MATERIAL[room],
            "geom_sf": geom_sf,
            "dimension_sf": dim_sf,
            "diff_pct": diff_pct,
            "validation": verdict,
            "product_action": action,
            "confidence": confidence(action, verdict),
            "open_group": OPEN_GROUP.get(room),
            "failure_mode": mode,
            "debug_note": note,
            "crop_path": item["path"],
        })

    action_counts = Counter(r["product_action"] for r in rows)
    validation_counts = Counter(r["validation"] for r in rows)
    open_groups = defaultdict(list)
    for r in rows:
        if r["open_group"]:
            open_groups[r["open_group"]].append(r["room"])

    summary = {
        "permit": "14-11290-NEWC",
        "doc_id": 1494156,
        "page_index": 3,
        "question_to_score": (
            "What should the product do with this room/zone: auto quantity, "
            "review geometry, or split an open zone?"
        ),
        "wrong_question": (
            "Did every room label produce a separate closed polygon?"
        ),
        "action_counts": dict(sorted(action_counts.items())),
        "validation_counts": dict(sorted(validation_counts.items())),
        "open_groups": {k: v for k, v in sorted(open_groups.items())},
        "rows": sorted(rows, key=lambda r: r["room"]),
    }

    json_path = os.path.join(OUT, "bank_product_states.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    md_path = os.path.join(OUT, "bank_product_states.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Probe 23 — Bank Product-State Diagnostic\n\n")
        f.write("This reframes the bank page around product actions instead of raw geometry statuses.\n\n")
        f.write(f"**Question to score:** {summary['question_to_score']}\n\n")
        f.write(f"**Wrong question:** {summary['wrong_question']}\n\n")
        f.write("## Action Counts\n\n")
        for action, n in sorted(action_counts.items()):
            f.write(f"- {action}: {n}\n")
        f.write("\n## Targeted Debug Read\n\n")
        for room in (101, 109, 114):
            r = next(x for x in rows if x["room"] == room)
            f.write(
                f"- {room} {r['name']}: {r['product_action']} / "
                f"{r['failure_mode']} / geom {r['geom_sf']} SF vs "
                f"dimension {r['dimension_sf']} SF ({r['diff_pct']}%). "
                f"{r['debug_note']}\n"
            )
        f.write("\n## Open-Zone Read\n\n")
        for group, rooms in sorted(open_groups.items()):
            f.write(f"- {group}: rooms {', '.join(map(str, rooms))}; split by finish/material boundary.\n")
        f.write("\n## Room Table\n\n")
        f.write("| Room | Name | Geom SF | Dim SF | Diff | Validation | Product action | Failure mode |\n")
        f.write("|---:|---|---:|---:|---:|---|---|---|\n")
        for r in sorted(rows, key=lambda x: x["room"]):
            geom = "" if r["geom_sf"] is None else f"{r['geom_sf']:.1f}"
            diff = "" if r["diff_pct"] is None else f"{r['diff_pct']:+.1f}%"
            f.write(
                f"| {r['room']} | {r['name']} | {geom} | {r['dimension_sf']} | "
                f"{diff} | {r['validation']} | {r['product_action']} | "
                f"{r['failure_mode']} |\n"
            )

    print(f"wrote {os.path.relpath(json_path, ROOT)}")
    print(f"wrote {os.path.relpath(md_path, ROOT)}")
    print("action_counts:", dict(sorted(action_counts.items())))
    print("validation_counts:", dict(sorted(validation_counts.items())))


if __name__ == "__main__":
    main()
