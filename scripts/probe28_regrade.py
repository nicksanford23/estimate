#!/usr/bin/env python3
"""Probe 28 -- re-grade the RULES geometry path with probe27's two
recommended counters implemented, on the EXACT same 4 truth_area permits /
pages / anchoring as probe26_truth_grading.py / probe27_regrade.py (imported
verbatim; only the geometry engine and grading-time rules change).

New vs probe27_regrade.py:
  FIX 1 (geometry, geometry_v3.py): ANCHOR-CLUSTER MEMBERSHIP FILTER. Any
    wall-graph-connected component of closed polygons containing ZERO of
    the page's addressable room-code anchors is demoted to ARTIFACT before
    grading -- never a matching candidate, never summed into
    unlabeled/"fabricated" SF. Targets probe27's diagnosed dominant cause of
    fabricated SF (other-building/other-plan blobs sharing the sheet).
  FIX 2 (grader, this file): UNIT/CORRIDOR MERGE GUARD, applied to every
    MERGED_ERROR row (the "merge candidate" rooms):
    (a) CROSS-UNIT CHECK: if the row's room-code tokens span >=2 distinct
        unit/building families (per the truth schedule's own `building`/
        `unit` fields, or the token's hyphen-prefix family when neither
        field is populated -- e.g. "A-101" -> family "A"), the blob is
        GUARANTEED wrong (it sums rooms from different units/buildings into
        one number) -- candidate for MERGE_CROSS_UNIT.
    (b) CHEAP RE-SPLIT ATTEMPT (tried FIRST, on every merge candidate,
        cross-unit or not -- a successful split is strictly better than any
        flag): re-run polygonize over the SAME wall-candidate graph with
        the v2 generic gap closer disabled (arcs-chords only -- the
        DETERMINISTIC "gap closer off" alternative, computed once per page
        via geometry_v3.build_arcs_only_rooms rather than truly re-cropping
        a local bbox subset -- documented design shortcut, see report). If,
        within the merged blob's footprint, this arcs-only graph produces
        one distinct closed sub-polygon per anchor (a bijection: every
        token's anchor point lands in its OWN arcs-only polygon, no two
        tokens sharing one), the merge is resolved: each token becomes its
        own graded row (MATCHED / CONFIDENT_WRONG / MATCHED_NO_AREA, same
        thresholds as fix 3) instead of one failed MERGED_ERROR row.
    Only if re-split FAILS do we fall through to the cross-unit check: a
    row that is both un-resplittable AND cross-unit becomes MERGE_CROSS_UNIT
    (flagged, EXCLUDED from any auto-quantity sum); un-resplittable and
    NOT cross-unit is left as MERGED_ERROR unchanged (same as probe27).

  Fix 3 (confident-wrong guard) and fix 4 (merge-scoring fix) are REUSED
  UNCHANGED from probe27_regrade.py (imported, not copied), per the task's
  instruction to keep them exactly as-is.

Deletes fetched PDFs after use.
"""
import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import Point  # noqa: E402

import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import probe2_sf  # noqa: E402
from probe2_sf import (  # noqa: E402
    ROOT, r2_client, download_pdf, extract_drawings, find_scale,
    extract_dim_words,
)
from probe2b_sf import build_grading_table  # noqa: E402
from geometry_v3 import run_geometry_engine_v3, build_arcs_only_rooms  # noqa: E402
import probe26_truth_grading as v1  # noqa: E402 -- reuse config/anchoring/overlay verbatim
import probe27_regrade as v2g  # noqa: E402 -- reuse fix3/fix4 verbatim

OUT_DIR = os.path.join(ROOT, "data", "probe28")
os.makedirs(OUT_DIR, exist_ok=True)
PDF_TMP_DIR = os.path.join(OUT_DIR, "_pdf_tmp")
os.makedirs(PDF_TMP_DIR, exist_ok=True)
probe2_sf.PDF_TMP_DIR = PDF_TMP_DIR

MERGE_OK_TOL = v1.MERGE_OK_TOL
apply_confident_wrong_guard = v2g.apply_confident_wrong_guard   # fix 3, unchanged
apply_merge_scoring_fix = v2g.apply_merge_scoring_fix           # fix 4, unchanged


# ------------------------------------------------------- unit/family keying --

def unit_key_for_token(truth_row):
    """Best-available unit/building grouping for a truth room: explicit
    `building` field, else explicit `unit` field, else the hyphen-prefix of
    a hyphenated room code ("A-101" -> "A"), else None (permit has no
    unit/building distinction to check -- e.g. 24-06748's single building,
    multi-level; different levels never co-occur in one merge blob since
    each level is graded on its own page)."""
    b = truth_row.get("building")
    if b:
        return ("building", b)
    u = truth_row.get("unit")
    if u:
        return ("unit", u)
    room = truth_row.get("room") or ""
    if "-" in room:
        return ("prefix", room.split("-")[0])
    return None


def is_cross_unit(tokens, truth_by_token):
    keys = set()
    for t in tokens:
        tr = truth_by_token.get(t)
        if tr is None:
            continue
        k = unit_key_for_token(tr)
        if k is not None:
            keys.add(k)
    return len(keys) >= 2


# --------------------------------------------------------- re-split attempt --

def attempt_resplit(blob_poly, tokens, anchors, arcs_only_rooms, feet_per_pt,
                     truth_by_token, confwrong_frac, confwrong_abs_sf,
                     is_utility_name_fn):
    """Try to resolve a MERGED_ERROR blob using the arcs-only ("gap closer
    disabled") room graph. Success requires every token's anchor point to
    land inside its OWN arcs-only sub-polygon (a true bijection -- if two
    tokens still land in the same arcs-only polygon, or a token's anchor
    lands outside every candidate sub-polygon, the split failed and we
    leave the row flagged). Returns (success, new_rows_or_None)."""
    # candidate sub-polygons: arcs-only rooms materially inside this blob
    candidates = []
    for p in arcs_only_rooms:
        if not p.intersects(blob_poly):
            continue
        inter_area = p.intersection(blob_poly).area
        if p.area > 0 and inter_area / p.area > 0.5:
            candidates.append(p)
    if len(candidates) < 2:
        return False, None, "no_candidates" if not candidates else "too_few_candidates"

    token_to_subpoly_id = {}
    for tok in tokens:
        pts = anchors.get(tok, [])
        found_id = None
        for (x, y) in pts:
            pt = Point(x, y)
            for j, sp in enumerate(candidates):
                if sp.contains(pt):
                    found_id = j
                    break
            if found_id is not None:
                break
        if found_id is None:
            return False, None, "anchor_outside_all_candidates"
        token_to_subpoly_id[tok] = found_id

    if len(set(token_to_subpoly_id.values())) != len(tokens):
        return False, None, "bijection_fail_still_shared"  # two+ tokens still share one sub-polygon

    new_rows = []
    for tok in tokens:
        sp = candidates[token_to_subpoly_id[tok]]
        sqft = sp.area * feet_per_pt ** 2
        tr = truth_by_token.get(tok, {})
        truth_sf = tr.get("area_sf")
        name = tr.get("name", "")
        if truth_sf is None:
            new_rows.append(dict(kind="MATCHED_NO_AREA", tokens=[tok], poly_idx=None,
                                  computed_sqft=round(sqft, 1), resolved_via="resplit",
                                  poly_coords=list(sp.exterior.coords)))
            continue
        pct_err = round(100 * (sqft - truth_sf) / truth_sf, 1) if truth_sf else None
        reasons = []
        if truth_sf and sqft < confwrong_frac * truth_sf:
            reasons.append(f"computed {sqft:.1f}sf < {confwrong_frac:.0%} of truth {truth_sf:.0f}sf")
        if sqft < confwrong_abs_sf and not is_utility_name_fn(name):
            reasons.append(f"computed {sqft:.1f}sf < {confwrong_abs_sf}sf floor for non-utility room '{name}'")
        kind = "CONFIDENT_WRONG" if reasons else "MATCHED"
        row = dict(kind=kind, tokens=[tok], poly_idx=None, computed_sqft=round(sqft, 1),
                    truth_sqft=truth_sf, pct_error=pct_err, resolved_via="resplit",
                    poly_coords=list(sp.exterior.coords))
        if reasons:
            row["guard_reasons"] = reasons
            row["orig_kind"] = "MATCHED"
        new_rows.append(row)
    return True, new_rows, "ok"


def apply_unit_merge_guard(rows, rooms_all, truth_by_token, anchors,
                            arcs_only_rooms, feet_per_pt):
    out_rows = []
    n_resplit_rooms = 0
    n_resplit_groups = 0
    n_cross_unit_rooms = 0
    n_cross_unit_groups = 0
    resplit_fail_reasons = defaultdict(int)
    for row in rows:
        if row["kind"] != "MERGED_ERROR":
            out_rows.append(row)
            continue
        tokens = row["tokens"]
        blob_poly = rooms_all[row["poly_idx"]]
        success, new_rows, reason = attempt_resplit(
            blob_poly, tokens, anchors, arcs_only_rooms, feet_per_pt,
            truth_by_token, v2g.CONFWRONG_FRAC, v2g.CONFWRONG_ABS_SF,
            v2g.is_utility_name)
        if success:
            n_resplit_rooms += len(tokens)
            n_resplit_groups += 1
            out_rows.extend(new_rows)
            continue
        resplit_fail_reasons[reason] += 1
        if is_cross_unit(tokens, truth_by_token):
            new_row = dict(row)
            new_row["kind"] = "MERGE_CROSS_UNIT"
            new_row["orig_kind"] = "MERGED_ERROR"
            new_row["excluded_from_auto_totals"] = True
            new_row["resplit_fail_reason"] = reason
            out_rows.append(new_row)
            n_cross_unit_rooms += len(tokens)
            n_cross_unit_groups += 1
        else:
            row = dict(row)
            row["resplit_fail_reason"] = reason
            out_rows.append(row)
    return out_rows, dict(n_resplit_rooms=n_resplit_rooms, n_resplit_groups=n_resplit_groups,
                            n_cross_unit_rooms=n_cross_unit_rooms, n_cross_unit_groups=n_cross_unit_groups,
                            resplit_fail_reasons=dict(resplit_fail_reasons))


def render_artifact_addon(pdf_path, page_index, rooms_all_pre_filter, ac_diag, feet_per_pt, overlay_path):
    """Draw the anchor-cluster-filter-KILLED polygons on top of the overlay
    (dull red = ordinary artifact kill, YELLOW outline = false-positive
    suspect per the room-band+principal-region heuristic) so a human can
    actually SEE what got removed and judge the false-kill risk by eye."""
    killed_idx = ac_diag.get("killed_idx") if ac_diag else None
    if not killed_idx:
        return
    suspect_idxs = set()
    for s in ac_diag.get("false_positive_suspects", []):
        suspect_idxs.update(s["idxs"])
    doc = fitz.open(pdf_path)
    pg = doc[page_index]
    Z = 1800 / pg.rect.width
    doc.close()
    img = Image.open(overlay_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(overlay)
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except Exception:
        fnt = ImageFont.load_default()
    for i in killed_idx:
        poly = rooms_all_pre_filter[i]
        pts = [(x * Z, y * Z) for x, y in poly.exterior.coords]
        is_suspect = i in suspect_idxs
        outline = (230, 200, 0, 255) if is_suspect else (120, 0, 0, 180)
        fill = (230, 200, 0, 60) if is_suspect else (90, 0, 0, 45)
        dd.polygon(pts, fill=fill, outline=outline)
        cen = poly.centroid
        sqft = poly.area * feet_per_pt ** 2
        label = ("SUSPECT " if is_suspect else "ARTIFACT ") + f"{sqft:.0f}sf"
        dd.text((cen.x * Z, cen.y * Z), label, fill=(80, 60, 0, 255) if is_suspect else (60, 0, 0, 255), font=fnt)
    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(overlay_path)


def render_resplit_addon(pdf_path, page_index, resplit_rows, overlay_path):
    """Draw the resplit sub-polygons (fix 5's re-split path) on top of the
    already-saved overlay PNG -- they have no rooms_all poly_idx (they come
    from the arcs-only oracle graph, not the v3 engine's own polygon list),
    so v1.render_overlay skips them; this addon makes the split visible for
    human grading."""
    if not resplit_rows:
        return
    doc = fitz.open(pdf_path)
    pg = doc[page_index]
    Z = 1800 / pg.rect.width
    doc.close()
    img = Image.open(overlay_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(overlay)
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except Exception:
        fnt = ImageFont.load_default()
    for row in resplit_rows:
        coords = row.get("poly_coords")
        if not coords:
            continue
        pts = [(x * Z, y * Z) for x, y in coords]
        dd.polygon(pts, fill=(160, 0, 220, 90), outline=(90, 0, 140, 255))
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        label = "+".join(row["tokens"]) + f"\nSPLIT {row['computed_sqft']:.0f}sf"
        dd.text((cx, cy), label, fill=(60, 0, 90, 255), font=fnt)
    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(overlay_path)


# ---------------------------------------------------------------- pipeline --

def run_engine_wrapper(pdf_path, page_index, anchor_points):
    extracted = extract_drawings(pdf_path, page_index)
    doc_id_for_scale = int(os.path.splitext(os.path.basename(pdf_path))[0])
    feet_per_pt, scale_text = find_scale(doc_id_for_scale, page_index)
    diag = dict(scale_text=scale_text, feet_per_pt=feet_per_pt)
    if feet_per_pt is None:
        diag["verdict"] = "scale_unverified"
        diag["reason"] = "no scale note found in page text"
        return None, diag
    out, engine_diag = run_geometry_engine_v3(extracted, feet_per_pt, anchor_points)
    diag.update(engine_diag)
    if out is None:
        return None, diag
    return out, diag


def process_permit(s3, cfg):
    permit = cfg["permit"]
    truth = v1.load_truth(cfg["truth"])
    print(f"\n{'=' * 70}\n{permit} (v3 engine)\n{'=' * 70}")

    for r in truth["rooms"]:
        r["_addressable"] = cfg["addressable"](r)
        r["_token"] = cfg["room_token"](r)
        r["_page_key"] = None
        if r["_addressable"]:
            r["_page_key"] = cfg["page_for_room"](r)

    not_addr = [r for r in truth["rooms"] if not r["_addressable"]]
    addr = [r for r in truth["rooms"] if r["_addressable"]]
    not_addr_by_key = defaultdict(list)
    for r in not_addr:
        not_addr_by_key[cfg["not_addressable_key"](r)].append(r)

    permit_result = dict(permit=permit, truth_total_sf=truth["total_sf"],
                          truth_n_rooms=len(truth["rooms"]),
                          n_not_addressable=len(not_addr),
                          not_addressable_by_key={
                              k: dict(n=len(v), sf=sum((x["area_sf"] or 0) for x in v))
                              for k, v in not_addr_by_key.items()},
                          pages=[])

    all_rows = []
    for page_cfg in cfg["pages"]:
        pi = page_cfg["page_index"]
        doc_id = page_cfg.get("doc_id", cfg["doc_id"])
        tag = f"{permit}_{doc_id}_p{pi}"
        print(f"\n--- page {tag} ({page_cfg['sheet']}) [v3] ---")
        pdf_path = download_pdf(s3, doc_id)

        page_truth_rooms = [r for r in addr if r["_page_key"] == (doc_id, pi)]
        truth_by_token = {r["_token"]: r for r in page_truth_rooms}
        target_tokens = [r["_token"] for r in page_truth_rooms]

        # anchors computed BEFORE the engine call -- plain text lookup,
        # independent of geometry, needed by the anchor-cluster filter
        anchors = v1.find_room_anchors(pdf_path, pi, target_tokens)
        anchor_points = [pt for pts in anchors.values() for pt in pts]

        engine_out, diag = run_engine_wrapper(pdf_path, pi, anchor_points)
        print("  engine diag (v3):", json.dumps(
            {k: v for k, v in diag.items()
             if k not in ("cavity_hatch_killed_detail", "anchor_cluster_false_positive_suspects")},
            default=str))
        page_result = dict(doc_id=doc_id, page_index=pi, sheet=page_cfg["sheet"], diag=diag)

        if engine_out is None:
            page_result["verdict"] = diag["verdict"]
            page_result["rows"] = []
            permit_result["pages"].append(page_result)
            continue

        rooms_all = engine_out["rooms_all"]
        feet_per_pt = engine_out["feet_per_pt"]
        walls_final = engine_out["walls_final"]
        rows, unlabeled_polys, ambiguous = v1.grade_page(rooms_all, feet_per_pt, anchors, page_truth_rooms)

        # FIX 3: confident-wrong guard (unchanged, probe27)
        rows, n_demoted = apply_confident_wrong_guard(rows, truth_by_token)
        # FIX 4: merge scoring fix (unchanged, probe27)
        rows, n_downgraded = apply_merge_scoring_fix(rows, rooms_all, walls_final)
        # FIX 5 (new): unit/corridor merge guard -- resplit attempt, then
        # cross-unit flag for whatever doesn't resplit
        extracted = engine_out["extracted"]
        arcs_only_rooms = build_arcs_only_rooms(
            walls_final, extracted["arcs"], extracted["pw"], extracted["ph"], feet_per_pt)
        rows, merge_guard_stats = apply_unit_merge_guard(
            rows, rooms_all, truth_by_token, anchors, arcs_only_rooms, feet_per_pt)

        page_result["n_anchors_found_on_page"] = len(anchors)
        page_result["n_target_tokens"] = len(target_tokens)
        page_result["ambiguous_tokens"] = ambiguous
        page_result["n_unlabeled_polys"] = len(unlabeled_polys)
        page_result["unlabeled_polys_sqft"] = sorted(
            [round(rooms_all[i].area * feet_per_pt ** 2, 1) for i in unlabeled_polys], reverse=True)
        page_result["n_confident_wrong_demoted"] = n_demoted
        page_result["n_merge_suspect_downgraded"] = n_downgraded
        page_result["merge_guard_stats"] = merge_guard_stats
        page_result["rows"] = rows
        page_result["verdict"] = "GRADED"

        dims = extract_dim_words(pdf_path, pi)
        dim_texts = sorted({d["text"] for d in dims})
        all_rooms_sorted = sorted(rooms_all, key=lambda p: -p.area)
        dim_grading = build_grading_table(all_rooms_sorted, feet_per_pt, dim_texts)
        page_result["dimension_grading_table"] = dim_grading

        overlay_path = os.path.join(OUT_DIR, f"overlay_{tag}_v3.png")
        v1.render_overlay(pdf_path, pi, rooms_all, feet_per_pt, rows, overlay_path, unlabeled_polys)
        rooms_all_pre_filter = engine_out.get("rooms_all_pre_anchor_filter")
        ac_diag = engine_out.get("anchor_cluster_diag")
        if rooms_all_pre_filter is not None:
            render_artifact_addon(pdf_path, pi, rooms_all_pre_filter, ac_diag, feet_per_pt, overlay_path)
        render_resplit_addon(pdf_path, pi, [r for r in rows if r.get("resolved_via") == "resplit"],
                              overlay_path)
        page_result["overlay_path"] = os.path.relpath(overlay_path, ROOT)

        all_rows.extend(rows)
        permit_result["pages"].append(page_result)

        pdf_full = os.path.join(PDF_TMP_DIR, f"{doc_id}.pdf")
        if os.path.exists(pdf_full):
            os.remove(pdf_full)

    matched = [r for r in all_rows if r["kind"] in ("MATCHED", "MATCHED_NO_AREA")]
    conf_wrong = [r for r in all_rows if r["kind"] == "CONFIDENT_WRONG"]
    merged_ok = [r for r in all_rows if r["kind"] == "MERGED_OK"]
    merge_suspect = [r for r in all_rows if r["kind"] == "MERGE_SUSPECT"]
    merged_err = [r for r in all_rows if r["kind"] == "MERGED_ERROR"]
    merge_cross_unit = [r for r in all_rows if r["kind"] == "MERGE_CROSS_UNIT"]
    missed = [r for r in all_rows if r["kind"] == "MISSED_NO_POLYGON"]
    not_on_page = [r for r in all_rows if r["kind"] == "NOT_ON_PAGE"]

    errs = [abs(r["pct_error"]) for r in matched if r.get("pct_error") is not None]
    merge_errs = [abs(r["pct_error"]) for r in merged_err if r.get("pct_error") is not None]

    matched_computed = sum(r["computed_sqft"] for r in matched)
    matched_truth = sum(r.get("truth_sqft") or 0 for r in matched)
    merged_ok_computed = sum(r["computed_sqft"] for r in merged_ok)
    merged_ok_truth = sum(r["truth_sqft_sum"] for r in merged_ok)

    addressable_truth_sf = sum((r["area_sf"] or 0) for r in addr)

    permit_result["summary"] = dict(
        n_addressable=len(addr),
        addressable_truth_sf=addressable_truth_sf,
        n_matched=len(matched),
        n_confident_wrong=len(conf_wrong),
        n_merged_ok_groups=len(merged_ok), n_merged_ok_rooms=sum(len(r["tokens"]) for r in merged_ok),
        n_merge_suspect_groups=len(merge_suspect), n_merge_suspect_rooms=sum(len(r["tokens"]) for r in merge_suspect),
        n_merged_err_groups=len(merged_err), n_merged_err_rooms=sum(len(r["tokens"]) for r in merged_err),
        n_merge_cross_unit_groups=len(merge_cross_unit),
        n_merge_cross_unit_rooms=sum(len(r["tokens"]) for r in merge_cross_unit),
        n_missed_no_polygon=len(missed),
        n_not_on_page=len(not_on_page),
        median_abs_pct_error_matched=round(statistics.median(errs), 1) if errs else None,
        median_abs_pct_error_merged_err=round(statistics.median(merge_errs), 1) if merge_errs else None,
        matched_computed_sf=round(matched_computed, 1), matched_truth_sf=round(matched_truth, 1),
        merged_ok_computed_sf=round(merged_ok_computed, 1), merged_ok_truth_sf=round(merged_ok_truth, 1),
    )
    print("\nSUMMARY (v3):", json.dumps(permit_result["summary"], indent=2))
    return permit_result


def main():
    s3 = r2_client()
    results = []
    for cfg in v1.PERMITS:
        r = process_permit(s3, cfg)
        results.append(r)

    with open(os.path.join(OUT_DIR, "results_v3.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    for f in os.listdir(PDF_TMP_DIR):
        os.remove(os.path.join(PDF_TMP_DIR, f))
    try:
        os.rmdir(PDF_TMP_DIR)
    except OSError:
        pass

    print("\n\n=== ALL DONE (v3) ===")
    for r in results:
        print(r["permit"], r["summary"])


if __name__ == "__main__":
    main()
