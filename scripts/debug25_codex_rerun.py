#!/usr/bin/env python3
"""Codex rerun for debug_25.

This is a diagnostic rerun, not the production takeoff path. It tests the first
fixes recommended in data/triage/debug_25/DIAGNOSIS_CODEX.md:

- score floor-plan pages by scope signals instead of "most compact polygons";
- classify candidate polygons as accepted rooms, open blobs, or artifacts;
- render color overlays and compare against the answer keys where available.
"""

import csv
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import fitz
import psycopg2
import psycopg2.extras
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe2_sf import (  # noqa: E402
    ROOT,
    download_pdf,
    extract_drawings,
    r2_client,
    seg_len,
    snap_and_close,
    suppress_hatches,
    wall_candidates,
)

DEBUG_ROOT = Path(ROOT) / "data" / "triage" / "debug_25"
OUT_ROOT = DEBUG_ROOT / "codex_rerun"
OVERLAY_ROOT = OUT_ROOT / "overlays"
PI2 = math.pi

ARTIFACT_TERMS = {
    "general notes",
    "construction notes",
    "revision",
    "revisions",
    "schedule",
    "door schedule",
    "finish schedule",
    "legend",
    "partition types",
    "keynotes",
    "sheet title",
    "drawing",
    "project no",
    "architect",
    "seal",
    "approval",
    "detail",
}

PAGE_NEGATIVE_TERMS = {
    "cover sheet": 8,
    "sheet index": 8,
    "general project info": 6,
    "abbreviations": 4,
    "key plan": 4,
    "phasing": 6,
    "phase diagram": 6,
    "demolition": 5,
    "demo": 4,
    "context": 4,
    "partition types": 5,
    "door schedule": 5,
    "finish schedule": 5,
    "reflected ceiling": 4,
    "elevation": 4,
    "section": 4,
    "details": 5,
    "detail": 4,
}

PAGE_POSITIVE_TERMS = {
    "floor plan": 4,
    "architectural floor plan": 5,
    "enlarged plan": 4,
    "tenant plan": 5,
    "first floor plan": 4,
    "second floor plan": 4,
    "third floor plan": 4,
}

ROOM_TERMS = {
    "room",
    "office",
    "corridor",
    "lobby",
    "toilet",
    "restroom",
    "jan",
    "storage",
    "vestibule",
    "kitchen",
    "break",
    "conference",
    "exam",
    "bath",
    "closet",
    "mechanical",
    "elect",
    "data",
    "workroom",
    "waiting",
}

COVER_TERMS = {
    "cover sheet",
    "sheet index",
    "general project info",
    "abbreviations",
}

MIXED_SHEET_TERMS = {
    "interior elevation",
    "reflected ceiling",
    "ceiling plan",
    "interior finish legend",
    "finish legend",
}

OPEN_ZONE_TERMS = {
    "merchandise plan",
    "flooring legend",
    "store area calculations",
    "retail area",
    "sales floor",
    "lease space",
}


def load_env():
    env = {}
    with open(Path(ROOT) / ".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def db_cursor():
    conn = psycopg2.connect(load_env()["NEON_DATABASE_URL"])
    return conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def answer_keys():
    out = {}
    for path in (DEBUG_ROOT / "answer_keys").glob("*.json"):
        data = json.loads(path.read_text())
        out[data["permit"]] = data
    return out


def baseline_geometry():
    out = {}
    for path in (DEBUG_ROOT / "geometry").glob("*.json"):
        data = json.loads(path.read_text())
        out[data["permit"]] = data
    return out


def local_pdf_path(doc_id):
    doc_id = str(doc_id)
    candidates = [
        Path(ROOT) / "data" / "probe2" / "_pdf_tmp" / f"{doc_id}.pdf",
        Path(ROOT) / "data" / "pdfs_r2" / f"{doc_id}.pdf",
        Path(ROOT) / "data" / "render_tmp" / f"{doc_id}.pdf",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    matches = sorted((Path(ROOT) / "data" / "pdfs").glob(f"{doc_id}_*.pdf"))
    if matches:
        return str(matches[0])
    return None


def get_pdf_path(s3, doc_id):
    local = local_pdf_path(doc_id)
    if local:
        return local
    return download_pdf(s3, doc_id)


def fallback_floor_plan_pages(permit):
    base = baseline_geometry().get(permit) or {}
    answer = answer_keys().get(permit) or {}
    notes = answer.get("notes") or ""
    doc_id = base.get("doc_id")
    doc_match = re.search(r"\b[Dd]oc(?:ument)?\s+(\d{5,})", notes)
    if doc_match:
        doc_id = int(doc_match.group(1))
    page_indexes = set()
    for m in re.finditer(r"(?:floor_plan_page|page_index)\s*[= ]\s*(\d+)", notes):
        page_indexes.add(int(m.group(1)))
    if not page_indexes and base.get("floor_plan_page") is not None:
        page_indexes.add(int(base["floor_plan_page"]))
    if not doc_id or not page_indexes:
        return []
    return [
        {
            "doc_id": int(doc_id),
            "doc_name": "",
            "page_id": None,
            "page_index": pi,
            "categories": "floor_plan:fallback",
        }
        for pi in sorted(page_indexes)
    ]


def floor_plan_pages(permit):
    try:
        conn, cur = db_cursor()
        cur.execute(
            """
            SELECT d.onestop_doc_id AS doc_id,
                   COALESCE(d.filename, '') AS doc_name,
                   p.id AS page_id,
                   p.page_index,
                   string_agg(DISTINCT pl.category, ',' ORDER BY pl.category) AS categories
            FROM estimate.document d
            JOIN estimate.page p ON p.document_id = d.id
            JOIN estimate.page_label pl ON pl.page_id = p.id
            WHERE d.permit_num = %s
              AND pl.category = 'floor_plan'
            GROUP BY d.onestop_doc_id, d.filename, p.id, p.page_index
            ORDER BY d.onestop_doc_id, p.page_index
            """,
            (permit,),
        )
        return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        pages = fallback_floor_plan_pages(permit)
        if pages:
            for page in pages:
                page["db_error"] = str(exc)
        return pages
    finally:
        try:
            conn.close()
        except Exception:
            pass


def page_text(pdf_path, page_index):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    text = page.get_text("text") or ""
    words = page.get_text("words") or []
    doc.close()
    clean_words = []
    for w in words:
        x0, y0, x1, y1, txt = w[:5]
        if txt:
            clean_words.append((float(x0), float(y0), float(x1), float(y1), str(txt)))
    return text, clean_words


def text_score(text):
    low = text.lower()
    pos = sum(v for k, v in PAGE_POSITIVE_TERMS.items() if k in low)
    neg = sum(v for k, v in PAGE_NEGATIVE_TERMS.items() if k in low)
    roomish = sum(1 for k in ROOM_TERMS if k in low)
    return pos, neg, roomish


def term_hits(low, terms):
    return sorted(t for t in terms if t in low)


def scope_key(low):
    floors = []
    for label in ("basement", "first", "second", "third", "fourth", "fifth", "mezzanine"):
        if label in low:
            floors.append(label)
    phases = sorted(set(re.findall(r"phase\s*([0-9]+)", low)))
    if not floors:
        floors = ["unknown_floor"]
    if not phases:
        phases = ["unknown_phase"]
    return "/".join(floors[:2]) + ":" + "/".join(phases[:2])


def classify_page_route(text, accepted, open_blobs, rejected, raw_faces, n_walls, roomish):
    low = text.lower()
    has_floor_plan = "floor plan" in low or "tenant plan" in low or "merchandise plan" in low
    cover_hits = term_hits(low, COVER_TERMS)
    mixed_hits = term_hits(low, MIXED_SHEET_TERMS)
    open_hits = term_hits(low, OPEN_ZONE_TERMS)
    has_phase = "phase" in low or "not in specific phase" in low
    has_demo = "demolition" in low or re.search(r"\bdemo\b", low)
    has_enlarged = "enlarged" in low
    has_finish_plan = "finish plan" in low or "furniture & finish" in low
    tenant_phrase = ("tenant" in low and "lease space" in low) or (
        "commercial" in low and "tenant" in low and "lease" in low
    )
    residential_context = low.count("bedroom") + low.count("kitchen") >= 4
    many_room_labels = len(re.findall(r"\b[0-9]{2,4}\b", low)) >= 8

    reasons = []
    route_action = "count_rooms"
    product_state = "enclosed_rooms_candidate"
    page_kind = "floor_plan"
    adjustment = 0.0

    if cover_hits and not has_floor_plan:
        page_kind = "cover_index"
        route_action = "reject_sheet"
        product_state = "wrong_sheet"
        adjustment -= 80.0
        reasons.extend(cover_hits)
    elif cover_hits and "sheet index" in cover_hits:
        page_kind = "cover_index"
        route_action = "reject_sheet"
        product_state = "wrong_sheet"
        adjustment -= 80.0
        reasons.extend(cover_hits)
    elif tenant_phrase and residential_context:
        page_kind = "whole_building_context_plan"
        route_action = "scope_review"
        product_state = "wrong_context_plan"
        adjustment -= 18.0
        reasons.extend(["tenant_plus_residential_context"])
    elif tenant_phrase:
        page_kind = "tenant_focus_plan"
        route_action = "open_zone_review"
        product_state = "open_zone_needs_sf"
        adjustment += 16.0
        reasons.extend(["tenant_focus"])
    elif has_floor_plan and mixed_hits and (has_finish_plan or len(mixed_hits) >= 2):
        page_kind = "mixed_plan_sheet"
        route_action = "region_crop_required"
        product_state = "partial_or_detail_sheet"
        adjustment -= 35.0
        reasons.extend(mixed_hits)
    elif has_demo:
        page_kind = "demolition_plan"
        route_action = "scope_review"
        product_state = "partial_or_detail_sheet"
        adjustment -= 18.0
        reasons.extend(["demolition"])
    elif has_enlarged:
        page_kind = "enlarged_or_partial_plan"
        route_action = "scope_review"
        product_state = "partial_or_detail_sheet"
        adjustment -= 10.0
        reasons.extend(["enlarged"])
    elif has_phase:
        page_kind = "phase_plan"
        route_action = "scope_review"
        product_state = "multi_page_scope"
        adjustment -= 3.0
        reasons.extend(["phase"])
    elif has_floor_plan:
        page_kind = "full_floor_plan"
        adjustment += 6.0
        reasons.extend(["floor_plan"])

    if open_hits and route_action == "count_rooms":
        page_kind = "open_or_fixture_plan"
        route_action = "open_zone_review"
        product_state = "open_zone_needs_sf"
        adjustment += 4.0
        reasons.extend(open_hits[:4])

    if n_walls >= 800 and raw_faces <= max(45, accepted * 4) and product_state == "enclosed_rooms_candidate":
        product_state = "geometry_underclosed"
        route_action = "geometry_debug"
        adjustment -= 2.0
        reasons.append("many_walls_few_faces")

    if rejected >= 1500 and accepted >= 20 and not many_room_labels and product_state == "enclosed_rooms_candidate":
        product_state = "artifact_review"
        route_action = "region_crop_required"
        adjustment -= 8.0
        reasons.append("many_rejected_fragments")

    if many_room_labels and accepted <= 3 and n_walls >= 100 and product_state == "enclosed_rooms_candidate":
        product_state = "geometry_underclosed"
        route_action = "geometry_debug"
        adjustment -= 6.0
        reasons.append("labels_without_closed_rooms")

    if open_blobs > 0 and product_state == "enclosed_rooms_candidate":
        product_state = "open_zone_needs_sf"
        route_action = "open_zone_review"
        reasons.append("open_blob")

    return {
        "page_kind": page_kind,
        "route_action": route_action,
        "product_state": product_state,
        "scope_key": scope_key(low),
        "router_adjustment": round(adjustment, 3),
        "router_reasons": sorted(set(reasons)),
    }


def page_candidate_score(accepted, open_blobs, rejected, pos_score, neg_score, roomish):
    reject_penalty = min(8.0, rejected * 0.0025)
    no_room_penalty = 8.0 if accepted <= 0 and open_blobs <= 0 else 0.0
    return round(
        accepted
        + 1.5 * open_blobs
        + 0.35 * roomish
        + pos_score
        - neg_score
        - reject_penalty
        - no_room_penalty,
        3,
    )


def words_inside(poly, words, limit=30):
    hits = []
    minx, miny, maxx, maxy = poly.bounds
    for x0, y0, x1, y1, txt in words:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if cx < minx or cx > maxx or cy < miny or cy > maxy:
            continue
        try:
            inside = poly.contains(Point(cx, cy))
        except Exception:
            inside = False
        if inside:
            hits.append(txt)
            if len(hits) >= limit:
                break
    return hits


def compactness(poly):
    return (4 * PI2 * poly.area / (poly.length ** 2)) if poly.length else 0.0


def classify_polygon(poly, pw, ph, wall_bbox_area, words):
    area = poly.area
    if area <= 0 or not poly.is_valid:
        return "reject", "invalid"

    page_area = pw * ph
    area_frac = area / max(1.0, wall_bbox_area)
    page_frac = area / max(1.0, page_area)
    minx, miny, maxx, maxy = poly.bounds
    cx, cy = poly.centroid.x, poly.centroid.y
    cxn, cyn = cx / pw, cy / ph
    bw, bh = maxx - minx, maxy - miny
    comp = compactness(poly)
    word_hits = words_inside(poly, words)
    word_text = " ".join(word_hits).lower()
    has_artifact_text = any(term in word_text for term in ARTIFACT_TERMS)
    has_room_text = any(term in word_text for term in ROOM_TERMS) or bool(
        re.search(r"\b[0-9]{2,4}[a-z]?\b", word_text)
    )

    if page_frac > 0.65 or area_frac > 0.92:
        return "reject", "page_or_building_shell"
    aspect = min(bw, bh) / max(1.0, max(bw, bh))
    if comp < 0.25:
        return "reject", "sliver"
    if aspect < 0.12 and not has_room_text:
        return "reject", "thin_artifact"
    if cxn > 0.88 and (bw > 0.025 * pw or bh > 0.025 * ph):
        return "reject", "right_title_block_strip"
    if cyn > 0.83 and (bw > 0.08 * pw or bh > 0.05 * ph):
        return "reject", "bottom_notes_or_title_block"
    if cxn < 0.03 or cyn < 0.03 or cxn > 0.97 or cyn > 0.97:
        return "reject", "sheet_edge_artifact"
    if has_artifact_text and not has_room_text:
        return "reject", "artifact_text"
    if area_frac > 0.22 or page_frac > 0.075:
        return "open_blob", "large_blob"
    if area_frac < 0.004 and not has_room_text:
        return "reject", "small_unlabeled_noise"

    return "accept", "candidate_room"


def analyze_page(pdf_path, page):
    page_index = page["page_index"]
    ex = extract_drawings(pdf_path, page_index)
    pw, ph = ex["pw"], ex["ph"]
    text, words = page_text(pdf_path, page_index)
    pos_score, neg_score, roomish = text_score(text)

    walls, dom, thick = wall_candidates(ex)
    walls_clean, n_hatch_dropped = suppress_hatches(walls, pw)
    if not walls_clean:
        score = page_candidate_score(0, 0, 0, pos_score, neg_score, roomish)
        route = classify_page_route(text, 0, 0, 0, 0, 0, roomish)
        return {
            **page,
            "error": None,
            "n_walls": 0,
            "raw_faces": 0,
            "accepted": 0,
            "open_blobs": 0,
            "rejected": 0,
            "score": score,
            "router_score": round(score + route["router_adjustment"], 3),
            "pos_score": pos_score,
            "neg_score": neg_score,
            "roomish_text_hits": roomish,
            **route,
            "polygons": [],
        }

    lines, gap_info = snap_and_close(walls_clean, ex["arcs"], pw, feet_per_pt=0.1)
    polys = list(polygonize(unary_union(lines)))
    xs = [c for p0, p1, _l, _w in walls_clean for c in (p0[0], p1[0])]
    ys = [c for p0, p1, _l, _w in walls_clean for c in (p0[1], p1[1])]
    wall_bbox_area = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys))) if xs and ys else pw * ph

    classified = []
    counts = Counter()
    reason_counts = Counter()
    for idx, poly in enumerate(polys, 1):
        kind, reason = classify_polygon(poly, pw, ph, wall_bbox_area, words)
        counts[kind] += 1
        reason_counts[reason] += 1
        classified.append(
            {
                "id": idx,
                "kind": kind,
                "reason": reason,
                "area_frac": round(poly.area / wall_bbox_area, 5),
                "page_frac": round(poly.area / (pw * ph), 5),
                "compactness": round(compactness(poly), 3),
                "cx": round(poly.centroid.x / pw, 4),
                "cy": round(poly.centroid.y / ph, 4),
                "points": [[round(x, 1), round(y, 1)] for x, y in poly.exterior.coords],
            }
        )

    accepted = counts["accept"]
    open_blobs = counts["open_blob"]
    rejected = counts["reject"]
    score = page_candidate_score(accepted, open_blobs, rejected, pos_score, neg_score, roomish)
    route = classify_page_route(text, accepted, open_blobs, rejected, len(polys), len(walls_clean), roomish)

    return {
        **page,
        "error": None,
        "n_walls": len(walls_clean),
        "n_hatch_dropped": n_hatch_dropped,
        "raw_faces": len(polys),
        "accepted": accepted,
        "open_blobs": open_blobs,
        "rejected": rejected,
        "reject_reasons": dict(reason_counts),
        "score": round(score, 3),
        "router_score": round(score + route["router_adjustment"], 3),
        "pos_score": pos_score,
        "neg_score": neg_score,
        "roomish_text_hits": roomish,
        **route,
        "dominant_angle": round(dom, 3),
        "gap_closing": gap_info,
        "polygons": classified,
    }


def selected_pages(page_results):
    valid = [p for p in page_results if not p.get("error")]
    if not valid:
        return []
    valid.sort(key=lambda p: (p.get("router_score", p["score"]), p["accepted"], -p["rejected"]), reverse=True)
    viable = [p for p in valid if p.get("route_action") != "reject_sheet"]
    if not viable:
        return []
    primary = viable[0]
    if primary.get("route_action") in {"scope_review", "region_crop_required", "open_zone_review", "geometry_debug"}:
        return [primary]
    best = primary.get("router_score", primary["score"])
    picked = []
    for p in viable:
        if len(picked) >= 4:
            break
        if p["accepted"] <= 0 and p["open_blobs"] <= 0:
            continue
        if picked and p.get("scope_key") != primary.get("scope_key"):
            continue
        if p.get("route_action") != "count_rooms":
            continue
        if p.get("router_score", p["score"]) >= max(1.0, best * 0.55) or len(picked) == 0:
            picked.append(p)
    return picked or [primary]


def candidate_pages(page_results, limit=6):
    valid = [p for p in page_results if not p.get("error")]
    valid.sort(key=lambda p: (p.get("router_score", p.get("score", -999)), p.get("accepted", 0)), reverse=True)
    out = []
    for p in valid[:limit]:
        out.append(
            {
                "doc_id": p["doc_id"],
                "page_index": p["page_index"],
                "score": p.get("score"),
                "router_score": p.get("router_score"),
                "accepted": p.get("accepted"),
                "open_blobs": p.get("open_blobs"),
                "rejected": p.get("rejected"),
                "page_kind": p.get("page_kind"),
                "route_action": p.get("route_action"),
                "product_state": p.get("product_state"),
                "scope_key": p.get("scope_key"),
                "router_reasons": p.get("router_reasons", []),
            }
        )
    return out


def permit_product_state(status, picked, page_results):
    if status == "NO_FLOOR_PLAN":
        return "missing_floor_plan_label", "find_or_label_floor_plan"
    if status == "NO_USABLE_PAGE":
        return "missing_pdf_or_no_input", "download_or_cache_pdf"
    if not picked:
        return "missing_pdf_or_no_input", "download_or_cache_pdf"

    primary = picked[0]
    action = primary.get("route_action")
    state = primary.get("product_state") or "enclosed_rooms_candidate"
    valid = [p for p in page_results if not p.get("error") and p.get("route_action") != "reject_sheet"]
    scope_keys = {p.get("scope_key") for p in valid if p.get("scope_key")}

    if action == "region_crop_required":
        return "mixed_sheet_region_needed", "crop_plan_region_then_rerun_geometry"
    if action == "open_zone_review":
        return state, "extract_open_zone_sf_and_review"
    if action == "scope_review" or len(scope_keys) > 1:
        return "multi_page_scope_review", "choose_scope_pages_before_summing"
    if action == "geometry_debug":
        return "geometry_underclosed", "anchor_room_labels_and_close_walls"
    return state, "use_room_polygons_with_confidence_review"


def render_overlay(pdf_path, page_result, out_path, target_w=1800):
    doc = fitz.open(pdf_path)
    page = doc[page_result["page_index"]]
    zoom = target_w / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    doc.close()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        font = ImageFont.load_default()

    colors = {
        "accept": ((0, 150, 0, 90), (0, 90, 0, 220)),
        "open_blob": ((240, 180, 0, 80), (180, 120, 0, 220)),
        "reject": ((210, 0, 0, 45), (150, 0, 0, 180)),
    }
    for poly in page_result["polygons"]:
        if poly["kind"] == "reject" and poly["area_frac"] < 0.004:
            continue
        fill, outline = colors.get(poly["kind"], colors["reject"])
        pts = [(x * zoom, y * zoom) for x, y in poly["points"]]
        if len(pts) < 3:
            continue
        draw.polygon(pts, fill=fill, outline=outline)
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        if poly["kind"] != "reject":
            label = {"accept": "R", "open_blob": "O", "reject": "X"}[poly["kind"]]
            draw.text((cx, cy), f"{label}{poly['id']}", fill=(0, 0, 0, 255), font=font)

    Image.alpha_composite(img, overlay).convert("RGB").save(out_path, quality=85)


def process_permit(permit, pages, answer, baseline, s3):
    real = answer.get("real_room_count") if answer else None
    baseline_rooms = baseline.get("rooms_counted", 0) if baseline else 0
    baseline_gap = None if real is None else baseline_rooms - real

    if not pages:
        return {
            "permit": permit,
            "real_rooms": real,
            "baseline_rooms": baseline_rooms,
            "baseline_gap": baseline_gap,
            "selected_pages": [],
            "candidate_pages": [],
            "accepted_rooms": 0,
            "open_blobs": 0,
            "rejected": 0,
            "codex_gap": None if real is None else -real,
            "status": "NO_FLOOR_PLAN",
            "product_state": "missing_floor_plan_label",
            "recommended_action": "find_or_label_floor_plan",
            "pages": [],
        }

    docs = {}
    for p in pages:
        docs.setdefault(p["doc_id"], []).append(p)

    page_results = []
    pdf_paths = {}
    for doc_id, doc_pages in docs.items():
        try:
            pdf_path = get_pdf_path(s3, doc_id)
            pdf_paths[doc_id] = pdf_path
        except Exception as exc:
            for page in doc_pages:
                page_results.append({**page, "error": f"download: {exc}", "score": -999})
            continue
        for page in doc_pages:
            try:
                page_results.append(analyze_page(pdf_path, page))
            except Exception as exc:
                page_results.append({**page, "error": f"analyze: {exc}", "score": -999})

    picked = selected_pages(page_results)
    status = "OK" if picked else "NO_USABLE_PAGE"
    product_state, recommended_action = permit_product_state(status, picked, page_results)
    accepted_total = sum(p.get("accepted", 0) for p in picked)
    open_total = sum(p.get("open_blobs", 0) for p in picked)
    rejected_total = sum(p.get("rejected", 0) for p in picked)

    for p in picked:
        pdf_path = pdf_paths.get(p["doc_id"])
        if not pdf_path:
            continue
        overlay_path = OVERLAY_ROOT / f"{permit}_d{p['doc_id']}_p{p['page_index']}.jpg"
        render_overlay(pdf_path, p, overlay_path)
        p["overlay"] = str(overlay_path.relative_to(ROOT))

    return {
        "permit": permit,
        "real_rooms": real,
        "baseline_rooms": baseline_rooms,
        "accepted_rooms": accepted_total,
        "open_blobs": open_total,
        "rejected": rejected_total,
        "codex_gap": None if real is None else accepted_total - real,
        "baseline_gap": baseline_gap,
        "product_state": product_state,
        "recommended_action": recommended_action,
        "selected_pages": [
            {
                "doc_id": p["doc_id"],
                "page_index": p["page_index"],
                "score": p.get("score"),
                "router_score": p.get("router_score"),
                "accepted": p.get("accepted"),
                "open_blobs": p.get("open_blobs"),
                "rejected": p.get("rejected"),
                "page_kind": p.get("page_kind"),
                "route_action": p.get("route_action"),
                "product_state": p.get("product_state"),
                "scope_key": p.get("scope_key"),
                "router_reasons": p.get("router_reasons", []),
                "overlay": p.get("overlay"),
            }
            for p in picked
        ],
        "candidate_pages": candidate_pages(page_results),
        "status": status,
        "pages": page_results,
    }


def write_outputs(results):
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    OVERLAY_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "results.json").write_text(json.dumps(results, indent=2))

    rows = []
    for r in results:
        rows.append(
            {
                "permit": r["permit"],
                "real_rooms": r["real_rooms"],
                "baseline_rooms": r["baseline_rooms"],
                "baseline_gap": r["baseline_gap"],
                "codex_accepted_rooms": r["accepted_rooms"],
                "codex_gap": r["codex_gap"],
                "open_blobs": r["open_blobs"],
                "rejected": r["rejected"],
                "product_state": r["product_state"],
                "recommended_action": r["recommended_action"],
                "selected_pages": ";".join(
                    f"d{p['doc_id']}:p{p['page_index']}:{p.get('page_kind')}({p['accepted']}R/{p['open_blobs']}O)"
                    for p in r["selected_pages"]
                ),
                "status": r["status"],
            }
        )
    with open(OUT_ROOT / "summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    comparable = [r for r in results if r["real_rooms"] is not None]
    lines = [
        "# Codex debug_25 rerun",
        "",
        "This is a diagnostic rerun with page scoring, artifact rejection, and open-blob classification.",
        "",
        "## Comparable answer-key rows",
        "",
        "| permit | real | baseline | baseline gap | codex accepted | codex gap | state | action | selected pages |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for r in comparable:
        pages = ", ".join(
            f"d{p['doc_id']} p{p['page_index']} {p.get('page_kind')} ({p.get('route_action')})"
            for p in r["selected_pages"]
        )
        lines.append(
            f"| {r['permit']} | {r['real_rooms']} | {r['baseline_rooms']} | {r['baseline_gap']} "
            f"| {r['accepted_rooms']} | {r['codex_gap']} | {r['product_state']} "
            f"| {r['recommended_action']} | {pages} |"
        )
    lines.extend(
        [
            "",
            "## Read",
            "",
            "This rerun is intentionally conservative. `codex_accepted_rooms` is not the final takeoff count; "
            "it is the count after rejecting obvious sheet artifacts and separating large/open blobs. "
            "A lower count can be an improvement when the baseline was counting title blocks, notes, parking bays, or context drawings as rooms.",
            "",
            "`product_state` is the decision layer. It says whether the count can be used, whether the sheet needs a crop, "
            "whether the scope needs review, or whether wall closure/room-label anchoring is the next debug action.",
            "",
            "Next metric to add: room-label hit rate and spatial overlap against answer-key room labels/crops.",
        ]
    )
    (OUT_ROOT / "summary.md").write_text("\n".join(lines) + "\n")


def main():
    permits = sorted(json.loads((Path(ROOT) / "data" / "triage" / "label_batch25.json").read_text()).keys())
    if len(sys.argv) > 1:
        wanted = set(sys.argv[1:])
        permits = [p for p in permits if p in wanted]

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    OVERLAY_ROOT.mkdir(parents=True, exist_ok=True)

    answers = answer_keys()
    baseline = baseline_geometry()
    s3 = r2_client()

    results = []
    for permit in permits:
        print(f"== {permit} ==", flush=True)
        pages = floor_plan_pages(permit)
        r = process_permit(permit, pages, answers.get(permit), baseline.get(permit), s3)
        results.append(r)
        print(
            f"  real={r['real_rooms']} baseline={r['baseline_rooms']} "
            f"accepted={r['accepted_rooms']} open={r['open_blobs']} rejected={r['rejected']}",
            flush=True,
        )

    write_outputs(results)
    print(f"\nWrote {OUT_ROOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
