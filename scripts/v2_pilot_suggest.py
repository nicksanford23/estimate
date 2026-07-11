#!/usr/bin/env python3
"""
v2_pilot_suggest.py — get ALL 10 pilot buildings into V2 Page Review with
machine label suggestions (dashed chips).

Idempotent end-to-end (safe to rerun):
  1. Ensure v2.building + v2.permit_building for every pilot permit
     (incl. new pilots #9 24-19187-RNVN and #10 25-09195-RNVN).
  2. Ensure v2.document rows for every plan-like downloaded doc (some were
     never in legacy estimate.document, e.g. all of 13-27145's arch sheets).
  3. Extract pagetext for docs missing data/pagetext/<docid>/: fetch PDF from
     R2, fitz per-page text -> page_%04d.txt (EVERY page gets a file so the
     filename<->pdf_page_index map has no gaps), delete PDF after.
  4. Ensure v2.page rows for all pilot docs with pagetext.
  5. machine_observation rows (source=title_heuristic, v2):
       - claim=page_category for EVERY pilot page. Title-block region (last
         ~15 non-empty lines of pagetext) searched BEFORE whole page, to dodge
         the cover/index-sheet trap (index lists every sheet title).
       - claim=sheet_title (guess_title, same as v2_backfill.py) if missing.
       - claim=page_flags where detectable: contains_area_table (>=3 SF
         numbers + AREA/TOTAL vocab, SCHEMA_V2 §14 — checked on EVERY page),
         enlarged_plan, contains_finish_schedule, contains_legend.
     Skips pages that already have a title_heuristic obs for that claim.
Never touches legacy estimate.* or public.* (read-only). Append-only writes.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PAGETEXT = DATA / "pagetext"

# permit -> {onestop_doc_id: filename} — plan-like docs confirmed present in R2
PILOT_DOCS = {
    "14-11290-NEWC": {
        1494156: "Approved Set Plans 14-11290.pdf",
        1381113: "A-1.0 Floor Plan Liberty Bank Gentilly 06.30.14.pdf",
        1381114: "A-1.1 Branch Floor Plan Liberty Bank Gentilly 06.30.14.pdf",
        1381115: "A-1.2 Retail Floor Plan Liberty Bank Gentilly 06.30.14.pdf",
        1381117: "A-1.4 Enlarged Plans Liberty Bank Gentilly 06.30.14.pdf",
        1381132: "A-10.1 Schedules and Details Liberty Bank Gentilly 06.30.14.pdf",
        1381147: "demolition plan 31 march 14.pdf",
        1381157: "IW-2.1 Branch Finish Plan Liberty Bank Gentilly 06.30.14.pdf",
    },
    "26-10321-RNVN": {9058456: "100 CD_ARCH 04-06-26.pdf"},
    "13-44121-NEWC": {1017493: "Arch Set (11/13/2013)"},
    "13-27145-NEWC": {
        923878: "A120.pdf",
        923885: "A101 - partial.pdf",
        923889: "A201.pdf",
        923890: "partial 201 - multi-purpose.pdf",
        926984: "ITEM 3 - MULTI-PURPOSE PLAN.pdf",
    },
    "24-06748-RNVS": {7372349: "600 Baronne_6-28-24_Arch.pdf"},
    "26-05332-NEWC": {8929774: "Z_10145 Curran Boulevard_PERMIT SET 2-12-26 (RCC).pdf"},
    "20-29653-RNVS": {
        4941399: "2nd floor plan.pdf",
        4941401: "3rd floor plan.pdf",
        4941403: "1514 Interior Elevation.pdf",
        4941409: "Finish schedule.pdf",
    },
    "25-33341-NEWC": {8640130: "4480 Dauphine Street ARCH_ Issued for Permit_251024 (RCC).pdf"},
    "24-19187-RNVN": {7352761: "24-03_CD_ARCH_6-21-24.pdf"},  # pilot 9
    "25-09195-RNVN": {  # pilot 10
        8260951: "2025.04.25 - 621 St Louis VCC approved arch 1of4 (VCC).pdf",
        8260953: "2025.04.25 - 621 St Louis VCC approved arch 2of4 (RCC).pdf",
        8260955: "2025.04.25 - 621 St Louis VCC approved arch 3of4 (RCC).pdf",
        8260957: "2025.04.25 - 621 St Louis VCC approved arch 4of4 (RCC).pdf",
        8260959: "2025.06.13 - 621 St Louis VCC approved rooftop lights, finishes.pdf",
    },
}
PILOT_PERMITS = list(PILOT_DOCS)


def env(key):
    v = os.environ.get(key)
    if v:
        return v
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return None


def get_conn():
    return psycopg2.connect(env("NEON_DATABASE_URL"))


# ---------------------------------------------------------------- pagetext
def extract_missing_pagetext():
    missing = []
    for docs in PILOT_DOCS.values():
        for doc_id in docs:
            if not (PAGETEXT / str(doc_id)).is_dir():
                missing.append(doc_id)
    if not missing:
        print("pagetext: nothing missing")
        return
    import boto3
    import fitz

    s3 = boto3.client(
        "s3",
        endpoint_url=env("R2_ENDPOINT"),
        aws_access_key_id=env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=env("R2_SECRET_ACCESS_KEY"),
    )
    bucket = env("R2_BUCKET") or "nola-permit-docs"
    for doc_id in missing:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
            s3.download_fileobj(bucket, f"docs/{doc_id}.pdf", tmp)
            tmp.flush()
            head = open(tmp.name, "rb").read(5)
            if head[:4] != b"%PDF":
                print(f"pagetext: doc {doc_id} is not a PDF, skipping", file=sys.stderr)
                continue
            pdf = fitz.open(tmp.name)
            outdir = PAGETEXT / str(doc_id)
            outdir.mkdir(parents=True, exist_ok=True)
            for i, page in enumerate(pdf):
                (outdir / f"page_{i:04d}.txt").write_text(page.get_text()[:20000])
            n = len(pdf)
            pdf.close()
        print(f"pagetext: extracted {n} pages for doc {doc_id}")


# ---------------------------------------------------------------- category rules
# (regex, category) — order matters; specific before generic. Applied to
# uppercased text; title-block region first, whole page as fallback.
RULES = [
    (r"FINISH\s+(SCHEDULE|LEGEND)|SCHEDULE\s+OF\s+FINISHES|ROOM\s+FINISH", "finish_schedule"),
    (r"FINISH\s+(PLAN|FLOOR\s*PLAN)|FLOOR\s+FINISH|FLOORING\s+PLAN", "finish_plan"),
    (r"DEMO(LITION)?\s+(PLAN|FLOOR)", "demo_plan"),
    (r"REFLECTED\s+CEILING|\bRCP\b|CEILING\s+PLAN", "reflected_ceiling"),
    (r"FURNITURE\s+PLAN", "furniture_plan"),
    (r"SITE\s+PLAN|SURVEY|PLAT\b|GRADING\s+PLAN|PAVING\s+PLAN|DRAINAGE|EROSION|UTILITY\s+PLAN|LANDSCAPE", "site_plan"),
    (r"LIFE\s+SAFETY|EGRESS|CODE\s+(DATA|PLAN|SUMMARY|ANALYSIS)|OCCUPANCY\s+PLAN", "life_safety"),
    (r"MECHANICAL|ELECTRICAL|PLUMBING|\bHVAC\b|POWER\s+PLAN|LIGHTING\s+PLAN|SANITARY|\bDUCT|RISER\s+DIAGRAM|PANEL\s+SCHEDULE|FIRE\s+ALARM|TECHNOLOGY|\bDATA\s+PLAN", "mep"),
    (r"STRUCTURAL|FOUNDATION|FRAMING|\bSLAB\s+PLAN|PILE\b|ROOF\s+PLAN|GRADE\s+BEAM", "structural"),
    (r"COVER\s+SHEET|TITLE\s+SHEET|DRAWING\s+(INDEX|LIST)|SHEET\s+INDEX|INDEX\s+OF\s+DRAWINGS", "cover_index"),
    (r"SPECIFICATIONS|GENERAL\s+NOTES|PROJECT\s+NOTES|ABBREVIATIONS", "specs_notes"),
    (r"(DOOR|WINDOW|HARDWARE|FIXTURE|EQUIPMENT)\s+SCHEDULE", "schedule_other"),
    (r"(WALL|BUILDING)\s+SECTIONS?\b|ELEVATIONS?\b|\bSECTIONS\b", "elevation_section"),
    (r"\bDETAILS?\b", "detail"),
    (r"ENLARGED\s+(\w+\s+)?PLANS?|(FLOOR|UNIT|LEVEL|DIMENSION)\s+PLAN", "floor_plan"),
]
RULES = [(re.compile(p), c) for p, c in RULES]

AREA_NUM_RE = re.compile(r"\b[\d,]{2,9}(\.\d+)?\s*(S\.?\s?F\.?\b|SQ\.?\s?(FT|FEET))", re.I)
AREA_VOCAB_RE = re.compile(r"\bAREA\b|\bTOTAL\b", re.I)


COVER_RE = re.compile(r"COVER\s+SHEET|TITLE\s+SHEET|DRAWING\s+(INDEX|LIST)|SHEET\s+INDEX|INDEX\s+OF\s+DRAWINGS")
SHEETNUM_LINE_RE = re.compile(r"^\s*[A-Z]{1,3}-?\d[\d.\-]*\s*$")


def classify(text_upper, tail_upper, page_index):
    # 1. title-block region (last ~15 lines) — the sheet's own title lives here
    for rx, cat in RULES:
        m = rx.search(tail_upper)
        if m:
            return cat, m.group(0).strip()[:80], "title_block"
    # 2. cover/index trap: a sheet index lists EVERY title, so before any
    #    full-page keyword match, detect index pages: explicit cover words
    #    anywhere, or (page 0 only — detail callouts fake the pattern on
    #    drawing pages) a dense run of bare sheet-number lines.
    if COVER_RE.search(text_upper) or (page_index == 0 and sum(
        1 for l in text_upper.splitlines() if SHEETNUM_LINE_RE.match(l)
    ) >= 10):
        return "cover_index", "sheet index density / cover words", "full_page"
    # 3. whole-page fallback
    for rx, cat in RULES:
        m = rx.search(text_upper)
        if m:
            return cat, m.group(0).strip()[:80], "full_page"
    return "other", None, "none"


def page_flags(text, text_upper, tail_upper):
    flags = []
    if len(AREA_NUM_RE.findall(text)) >= 3 and AREA_VOCAB_RE.search(text):
        flags.append("contains_area_table")
    if re.search(r"ENLARGED\s+(\w+\s+)?PLAN", tail_upper):
        flags.append("enlarged_plan")
    if re.search(r"FINISH\s+SCHEDULE", text_upper) and not re.search(r"FINISH\s+SCHEDULE", tail_upper):
        flags.append("contains_finish_schedule")
    if re.search(r"\bLEGEND\b", text_upper):
        flags.append("contains_legend")
    return flags


TITLE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-/&.,']{4,60}$")


def guess_title(lines):
    for line in lines[:40]:
        s = line.strip()
        if not s:
            continue
        letters = [c for c in s if c.isalpha()]
        if len(letters) < 4:
            continue
        if sum(1 for c in letters if c.isupper()) / len(letters) > 0.8 and TITLE_RE.match(s):
            return s[:200]
    return None


# ---------------------------------------------------------------- main
def main():
    extract_missing_pagetext()

    conn = get_conn()
    conn.autocommit = False
    counts = {"building": 0, "permit_building": 0, "document": 0, "page": 0,
              "obs_category": 0, "obs_title": 0, "obs_flags": 0}
    cur = conn.cursor()

    # 1. buildings
    cur.execute("SELECT permit_num, id FROM v2.permit WHERE permit_num = ANY(%s)", (PILOT_PERMITS,))
    permit_id_by_num = dict(cur.fetchall())
    missing_permits = [p for p in PILOT_PERMITS if p not in permit_id_by_num]
    if missing_permits:
        sys.exit(f"v2.permit missing for {missing_permits} — run v2_backfill.py shallow pass first")
    cur.execute("SELECT permit_id FROM v2.permit_building WHERE permit_id = ANY(%s)",
                (list(permit_id_by_num.values()),))
    have_building = {r[0] for r in cur.fetchall()}
    for pnum, pid in permit_id_by_num.items():
        if pid in have_building:
            continue
        cur.execute(
            "INSERT INTO v2.building (name, address, notes) VALUES (%s, NULL, %s) RETURNING id",
            (f"Pilot building — {pnum}", "auto-created by v2_pilot_suggest.py"))
        bid = cur.fetchone()[0]
        cur.execute("INSERT INTO v2.permit_building (permit_id, building_id, role) VALUES (%s,%s,'primary') ON CONFLICT DO NOTHING",
                    (pid, bid))
        counts["building"] += 1
        counts["permit_building"] += 1

    # 2. documents
    all_doc_ids = [d for docs in PILOT_DOCS.values() for d in docs]
    cur.execute("SELECT onestop_doc_id, id FROM v2.document WHERE onestop_doc_id = ANY(%s)", (all_doc_ids,))
    v2doc = dict(cur.fetchall())
    for pnum, docs in PILOT_DOCS.items():
        for doc_id, fname in docs.items():
            if doc_id in v2doc:
                continue
            cur.execute(
                "INSERT INTO v2.document (onestop_doc_id, permit_id, filename) VALUES (%s,%s,%s) ON CONFLICT (onestop_doc_id) DO NOTHING RETURNING id",
                (doc_id, permit_id_by_num[pnum], fname))
            row = cur.fetchone()
            if row:
                v2doc[doc_id] = row[0]
                counts["document"] += 1

    # 3. pages
    cur.execute("SELECT document_id, pdf_page_index, id FROM v2.page WHERE document_id = ANY(%s)",
                (list(v2doc.values()),))
    page_id = {(r[0], r[1]): r[2] for r in cur.fetchall()}
    page_rows = []
    for doc_id, v2id in v2doc.items():
        d = PAGETEXT / str(doc_id)
        if not d.is_dir():
            continue
        for i in range(len(list(d.glob("page_*.txt")))):
            if (v2id, i) not in page_id:
                page_rows.append((v2id, i))
    if page_rows:
        psycopg2.extras.execute_values(
            cur, "INSERT INTO v2.page (document_id, pdf_page_index) VALUES %s ON CONFLICT DO NOTHING", page_rows)
        counts["page"] = len(page_rows)
        cur.execute("SELECT document_id, pdf_page_index, id FROM v2.page WHERE document_id = ANY(%s)",
                    (list(v2doc.values()),))
        page_id = {(r[0], r[1]): r[2] for r in cur.fetchall()}

    # 4. observations
    all_page_ids = list(page_id.values())
    existing = {}
    for claim in ("page_category", "sheet_title", "page_flags"):
        cur.execute(
            "SELECT target_id FROM v2.machine_observation WHERE claim=%s AND source='title_heuristic' AND target_type='page' AND target_id = ANY(%s)",
            (claim, all_page_ids))
        existing[claim] = {r[0] for r in cur.fetchall()}

    obs = []
    for doc_id, v2id in v2doc.items():
        d = PAGETEXT / str(doc_id)
        if not d.is_dir():
            continue
        for i, f in enumerate(sorted(d.glob("page_*.txt"))):
            pid = page_id.get((v2id, i))
            if not pid:
                continue
            text = f.read_text(errors="ignore")
            lines = text.splitlines()
            # Title block is the LAST text a plotter writes — except on
            # city-stamped (RCC) sets, where the Safety & Permits stamp is
            # appended after it on every page. Strip the stamp, then window.
            body = [l for l in lines if l.strip()]
            for marker in ("DEPARTMENT OF SAFETY AND PERMITS", "PLAN REVIEW DIVISION",
                           "FINAL PERMIT RELEASE", "REVIEWED FOR CODE"):
                for j, l in enumerate(body):
                    if marker in l.upper():
                        body = body[:j]
                        break
            tail = "\n".join(body[-30:])
            tu, xu = tail.upper(), text.upper()

            if pid not in existing["page_category"]:
                cat, ev, region = classify(xu, tu, i)
                obs.append((pid, "page_category",
                            json.dumps({"category": cat, "evidence": ev, "region": region})))
                counts["obs_category"] += 1
            if pid not in existing["sheet_title"]:
                t = guess_title(lines)
                if t:
                    obs.append((pid, "sheet_title", json.dumps({"title": t})))
                    counts["obs_title"] += 1
            if pid not in existing["page_flags"]:
                fl = page_flags(text, xu, tu)
                if fl:
                    obs.append((pid, "page_flags", json.dumps({"flags": fl})))
                    counts["obs_flags"] += 1

    if obs:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO v2.machine_observation (target_type, target_id, claim, value_json, source, source_version) VALUES %s",
            [("page", pid, claim, val, "title_heuristic", "v2") for pid, claim, val in obs])

    conn.commit()
    print("\n=== v2_pilot_suggest.py — inserted this run ===")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    # verification table
    cur.execute("""
        SELECT p.permit_num,
               count(DISTINCT d.id) FILTER (WHERE pg.id IS NOT NULL) AS docs,
               count(DISTINCT pg.id) AS pages,
               count(mo.id) FILTER (WHERE mo.claim='page_category') AS cat_obs,
               count(mo.id) FILTER (WHERE mo.claim='sheet_title') AS title_obs,
               count(mo.id) FILTER (WHERE mo.claim='page_flags') AS flag_obs
        FROM v2.permit p
        JOIN v2.permit_building pb ON pb.permit_id = p.id
        LEFT JOIN v2.document d ON d.permit_id = p.id
        LEFT JOIN v2.page pg ON pg.document_id = d.id
        LEFT JOIN v2.machine_observation mo ON mo.target_type='page' AND mo.target_id = pg.id
             AND mo.source='title_heuristic'
        WHERE p.permit_num = ANY(%s)
        GROUP BY 1 ORDER BY 1
    """, (PILOT_PERMITS,))
    print("\npermit            docs pages cat_obs title_obs flag_obs")
    for r in cur.fetchall():
        print(f"{r[0]:<17} {r[1]:>4} {r[2]:>5} {r[3]:>7} {r[4]:>9} {r[5]:>8}")
    conn.close()


if __name__ == "__main__":
    main()
