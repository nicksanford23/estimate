#!/usr/bin/env python3
"""Assemble a G2 room-segmenter training manifest from human outcome files.

CODE ONLY — pure local reads/writes, no network, no GPU. This is the G2
"data contract before GPU spend" step (docs/pilot/GEOMETRY_REBOOT_V1.md).

WHAT IT DOES
------------
Reads human-confirmed room outlines from
    data/geometry_annotations/human/<permit>.outcomes.jsonl
(the ONLY training truth — a machine proposal never enters here; see the
room-outline-proposals skill), joins each row to its crop + transform from the
per-permit bundle (data/sam_smoke/<permit>/bundle_g1b/), and emits a dataset
manifest with sha256s, per-class counts, provenance, the frozen split, and an
honest eligibility verdict.

SPLIT LAW (GEOMETRY_REBOOT_V1 ladder, non-negotiable)
-----------------------------------------------------
* Project-disjoint: a whole plan set (permit) is atomic — every room of a
  permit goes to exactly ONE split. Never split rooms/crops of one building
  across train and val. Four floors of one plan set are ONE project.
* The builder REFUSES to emit (raises) if any permit lands in two splits.

ELIGIBILITY (zero-trust reset, ML_ROADMAP R2/R3)
------------------------------------------------
A manifest is `eligible=true` for promotion decisions only if ALL gates pass:
    - tier == human_truth  (NOT built from machine proposals)
    - label book is LOCKED (a DRAFT book cannot certify training truth)
    - >= 2 distinct projects (needed for a project-held-out val split)
    - >= --min-rooms trainable rooms (ladder target 150; one building can't
      generalize)
    - project-disjoint split holds
A manifest built with --source machine is ALWAYS tier=diagnostic_weak and
eligible=false: its metrics may never be cited for promotion, demos, or
architecture verdicts. It exists only to prove the harness plumbing.

Run today (empty/machine-only truth) it emits an honest eligible=false
manifest and exits 0.

USAGE
-----
  python3 scripts/build_training_manifest.py                 # human truth
  python3 scripts/build_training_manifest.py --source machine  # diag_weak
  python3 scripts/build_training_manifest.py --val-project 24-06748-RNVS ...
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from geometry_raster import apply_affine, shoelace_area  # noqa: E402

HUMAN_DIR = os.path.join(ROOT, "data", "geometry_annotations", "human")
BUNDLE_ROOT = os.path.join(ROOT, "data", "sam_smoke")
LABEL_BOOK = os.path.join(ROOT, "docs", "pilot", "GEOMETRY_LABEL_BOOK_V1_DRAFT.md")
OUT_DEFAULT = os.path.join(ROOT, "data", "training", "manifest_v1.json")

# The four training classes named by the reboot doc. Priority order matters:
# exterior/deck is a first-class class (L4 is mostly deck), so an exterior
# boundary wins over the open/interior distinction; unresolved/out-of-scope
# rows carry no trainable mask and are counted-but-excluded.
CLASSES = ["room_interior", "open_zone", "exterior_deck", "unresolved_excluded"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def label_book_version():
    """Read the label-book file: return (version_string, locked_bool)."""
    if not os.path.exists(LABEL_BOOK):
        return ("geometry-label-book-MISSING", False)
    txt = open(LABEL_BOOK, encoding="utf-8").read()
    # DRAFT header explicitly says it is not locked until founder answers + review.
    locked = "not locked" not in txt.lower() and "DRAFT" not in txt.split("\n")[0]
    ver = "geometry-label-book-v1" if locked else "geometry-label-book-v1-DRAFT"
    return (ver, locked)


def classify(outcome, boundary_types):
    bt = set(boundary_types or [])
    if outcome in ("not_in_scope", "unresolved", None):
        return "unresolved_excluded"
    if "exterior" in bt:
        return "exterior_deck"
    if outcome == "open_zone":
        return "open_zone"
    # enclosed_polygon, finish_zone -> interior field flooring
    return "room_interior"


# ---------------------------------------------------------------------------
# per-permit bundle join: task_id -> {crop, forward_affine, anchor_px, ppf}
# ---------------------------------------------------------------------------
def load_bundle(permit):
    bdir = os.path.join(BUNDLE_ROOT, permit, "bundle_g1b")
    tf_path = os.path.join(bdir, "transforms.json")
    tk_path = os.path.join(bdir, "tasks.json")
    if not (os.path.exists(tf_path) and os.path.exists(tk_path)):
        return None
    tf = json.load(open(tf_path)).get("tasks", {})
    tk_raw = json.load(open(tk_path)).get("tasks", {})
    # tasks.json "tasks" may be a list or dict keyed by task_id
    tk = {}
    if isinstance(tk_raw, list):
        for t in tk_raw:
            tk[t.get("task_id")] = t
    else:
        tk = tk_raw
    out = {}
    for task_id, tr in tf.items():
        t = tk.get(task_id, {})
        prompt = None
        pv = (t.get("prompt_variants") or {}).get("point_only") or {}
        pos = pv.get("positive_points_px")
        if pos:
            prompt = pos[0]
        elif t.get("anchor_px"):
            prompt = t["anchor_px"]
        out[task_id] = {
            "bundle_dir": os.path.relpath(bdir, ROOT),
            "crop": tr.get("image"),
            "crop_path": os.path.join(bdir, tr.get("image")) if tr.get("image") else None,
            "forward_affine": tr.get("forward_affine"),
            "size": tr.get("size"),
            "px_per_foot": tr.get("px_per_foot"),
            "prompt_point_px": prompt,
            "anchor_provenance": t.get("anchor_provenance"),
        }
    return out


# ---------------------------------------------------------------------------
# human outcomes: newest-per-task, resolving append-only supersession
# ---------------------------------------------------------------------------
def load_human_rows(human_dir):
    """Return {permit: {task_id: latest_row}} using max saved_at per task."""
    by_permit = {}
    for path in sorted(glob.glob(os.path.join(human_dir, "*.outcomes.jsonl"))):
        permit = os.path.basename(path).split(".outcomes.jsonl")[0]
        latest = {}
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            tid = row.get("task_id")
            prev = latest.get(tid)
            if prev is None or (row.get("saved_at") or "") >= (prev.get("saved_at") or ""):
                latest[tid] = row
        if latest:
            by_permit[permit] = latest
    return by_permit


def load_machine_rows():
    """Diagnostic-weak source: machine proposals from proposals_for_editor.json.

    These become tier=diagnostic_weak samples ONLY (never promotion-eligible).
    """
    by_permit = {}
    for pf in sorted(glob.glob(os.path.join(
            BUNDLE_ROOT, "*", "results", "proposals_for_editor.json"))):
        permit = pf.split(os.sep)[-3]
        d = json.load(open(pf))
        rows = {}
        for task_id, p in d.items():
            rows[task_id] = {
                "task_id": task_id,
                "outcome": p.get("outcome_suggestion"),
                "boundary_types": [],  # proposals don't carry per-edge outcome types
                "polygon_pdf": p.get("polygon_pdf"),
                "proposal_source": p.get("proposal_source", "machine"),
                "reviewer": None,
                "saved_at": None,
            }
        if rows:
            by_permit[permit] = rows
    return by_permit


# ---------------------------------------------------------------------------
def build_samples(by_permit, source):
    """Join rows to bundles -> trainable samples + counts + skips."""
    samples = []
    class_counts = {c: 0 for c in CLASSES}
    provenance = {}
    skips = []
    for permit, rows in sorted(by_permit.items()):
        bundle = load_bundle(permit)
        if bundle is None:
            skips.append({"permit": permit, "reason": "no_bundle_g1b"})
            continue
        for task_id, row in sorted(rows.items()):
            cls = classify(row.get("outcome"), row.get("boundary_types"))
            class_counts[cls] += 1
            prov = row.get("proposal_source") or "unknown"
            provenance[prov] = provenance.get(prov, 0) + 1
            poly_pdf = row.get("polygon_pdf")
            # counted-but-excluded classes / null polygons never become samples
            if cls == "unresolved_excluded" or not poly_pdf:
                continue
            bt = bundle.get(task_id)
            if not bt or not bt.get("forward_affine") or not bt.get("crop_path"):
                skips.append({"permit": permit, "task_id": task_id,
                              "reason": "no_bundle_transform_or_crop"})
                continue
            if not os.path.exists(bt["crop_path"]):
                skips.append({"permit": permit, "task_id": task_id,
                              "reason": "crop_png_missing"})
                continue
            poly_px = apply_affine(poly_pdf, bt["forward_affine"])
            w, h = bt.get("size", [None, None])
            ppf = bt.get("px_per_foot")
            area_px = shoelace_area(poly_px)
            area_sf = area_px / (ppf * ppf) if ppf else None
            samples.append({
                "sample_id": sha256_obj([permit, task_id, poly_pdf])[:16],
                "permit": permit,
                "task_id": task_id,
                "class": cls,
                "outcome": row.get("outcome"),
                "boundary_types": row.get("boundary_types") or [],
                "proposal_source": prov,
                "crop": os.path.relpath(bt["crop_path"], ROOT),
                "crop_sha256": sha256_file(bt["crop_path"]),
                "crop_wh": [w, h],
                "px_per_foot": ppf,
                "prompt_point_px": bt.get("prompt_point_px"),
                "polygon_px": [[round(x, 3), round(y, 3)] for x, y in poly_px],
                "polygon_pdf": poly_pdf,
                "area_px": round(area_px, 2),
                "area_sf_geom": round(area_sf, 2) if area_sf else None,
                "split": None,  # filled by assign_splits
            })
    return samples, class_counts, provenance, skips


# ---------------------------------------------------------------------------
def assign_splits(samples, val_projects, seed_tag="g2"):
    """Project-disjoint train/val. val_projects explicit, else hash lowest ~25%.

    Returns (split_map {permit:split}, project_disjoint_ok).
    """
    permits = sorted({s["permit"] for s in samples})
    split_map = {}
    if val_projects:
        for p in permits:
            split_map[p] = "val" if p in set(val_projects) else "train"
    elif len(permits) >= 2:
        ranked = sorted(permits, key=lambda p: hashlib.sha256(
            (seed_tag + ":" + p).encode()).hexdigest())
        n_val = max(1, len(permits) // 4)
        n_val = min(n_val, len(permits) - 1)  # keep >=1 train project
        val = set(ranked[:n_val])
        for p in permits:
            split_map[p] = "val" if p in val else "train"
    else:
        # single project: no project-held-out val is possible
        for p in permits:
            split_map[p] = "train"
    for s in samples:
        s["split"] = split_map[s["permit"]]
    # invariant: a permit never appears in two splits (structurally guaranteed
    # because we key the map by permit) — assert it anyway.
    seen = {}
    for s in samples:
        seen.setdefault(s["permit"], set()).add(s["split"])
    disjoint = all(len(v) == 1 for v in seen.values())
    return split_map, disjoint


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--human-dir", default=HUMAN_DIR)
    ap.add_argument("--source", choices=["human", "machine"], default="human",
                    help="human=truth (default); machine=diagnostic_weak plumbing")
    ap.add_argument("--val-project", action="append", default=[],
                    help="permit(s) to force into val; repeatable")
    ap.add_argument("--min-rooms", type=int, default=150,
                    help="ladder target trainable rooms for eligibility (150-300)")
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    lbver, lblocked = label_book_version()
    tier = "human_truth" if args.source == "human" else "diagnostic_weak"

    if args.source == "human":
        by_permit = load_human_rows(args.human_dir)
    else:
        by_permit = load_machine_rows()

    samples, class_counts, provenance, skips = build_samples(by_permit, args.source)
    split_map, disjoint = assign_splits(samples, args.val_project)

    projects = sorted({s["permit"] for s in samples})
    n_trainable = len(samples)
    n_val_projects = sum(1 for p, sp in split_map.items() if sp == "val")

    # ---- eligibility gates ----
    gates = {
        "tier_is_human_truth": tier == "human_truth",
        "label_book_locked": {"required": True, "actual": lblocked, "pass": lblocked},
        "min_two_projects": {"required": 2, "actual": len(projects),
                             "pass": len(projects) >= 2},
        "min_rooms": {"required": args.min_rooms, "actual": n_trainable,
                      "pass": n_trainable >= args.min_rooms},
        "project_disjoint_split": {"required": True, "actual": disjoint,
                                   "pass": disjoint},
        "held_out_val_project_exists": {"required": True, "actual": n_val_projects >= 1,
                                        "pass": n_val_projects >= 1},
    }
    reasons = []
    if tier != "human_truth":
        reasons.append("tier=diagnostic_weak: built from machine proposals "
                       "(zero-trust reset) — never promotion-eligible")
    if not lblocked:
        reasons.append(f"label book not locked ({lbver}); a DRAFT book cannot "
                       "certify training truth")
    if len(projects) < 2:
        reasons.append(f"only {len(projects)} project(s); project-disjoint "
                       "train/val needs >=2 (one building can't generalize)")
    if n_trainable < args.min_rooms:
        reasons.append(f"{n_trainable} trainable rooms < ladder target "
                       f"{args.min_rooms} (150-300 across >=2 projects)")
    if not disjoint:
        reasons.append("REFUSED: a permit appeared in two splits")

    eligible = (tier == "human_truth" and lblocked and len(projects) >= 2
                and n_trainable >= args.min_rooms and disjoint
                and n_val_projects >= 1)

    # hard refusal: never emit a manifest that leaks a project across splits
    if not disjoint:
        raise SystemExit("REFUSE: project-disjoint split violated — a permit "
                         "spans train and val. Manifest not written.")

    manifest = {
        "schema": "geometry_training_manifest_v1",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tier": tier,
        "source_mode": args.source,
        "label_book_version": lbver,
        "label_book_locked": lblocked,
        "eligible": eligible,
        "eligible_label_count": (n_trainable if eligible else 0),
        "discovered_label_count": n_trainable,
        "eligibility": {
            "eligible": eligible,
            "note": ("Eligible manifests may inform promotion/architecture "
                     "decisions. diagnostic_weak manifests may ONLY prove the "
                     "harness runs — never cited for promotion, demos, or "
                     "verdicts."),
            "gates": gates,
            "reasons_not_eligible": reasons,
        },
        "split_law": ("project-disjoint: whole plan sets (permits) are atomic; "
                      "four floors of one plan set are one project; never split "
                      "rooms/crops of one building across train and val"),
        "projects": projects,
        "split_map": split_map,
        "counts": {
            "trainable_rooms": n_trainable,
            "by_class": class_counts,
            "by_provenance": provenance,
            "by_split": {sp: sum(1 for s in samples if s["split"] == sp)
                         for sp in ("train", "val")},
            "projects": len(projects),
            "val_projects": n_val_projects,
        },
        "skips": skips,
        "samples": samples,
    }
    manifest["manifest_sha256"] = sha256_obj(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"})

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[manifest] wrote {args.out}")
    print(f"[manifest] tier={tier}  eligible={eligible}  "
          f"eligible_labels={n_trainable if eligible else 0}  "
          f"discovered_labels={n_trainable}  projects={len(projects)}")
    print(f"[manifest] by_class={class_counts}")
    if reasons:
        print("[manifest] NOT eligible for promotion because:")
        for r in reasons:
            print("   -", r)
    if tier == "human_truth" and n_trainable == 0:
        print("[manifest] HONEST EMPTY STATE: 0 eligible human labels today. "
              "Training is one recorded command away once human outcomes land.")


if __name__ == "__main__":
    main()
