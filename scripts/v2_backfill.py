#!/usr/bin/env python3
"""
v2_backfill.py — idempotent backfill from legacy `estimate.*` + local data/
into the new `v2.*` schema (SCHEMA_V2.md, scripts/v2_schema.sql).

SHALLOW (all permits/documents):
  - v2.permit  <- estimate.permits
  - v2.document <- estimate.document (dedup on onestop_doc_id)

DEEP (pilot permits only):
  - v2.building (one per pilot permit) + v2.permit_building
  - v2.page for docs having data/pagetext/<docid>/ dirs (page count = txt file count)
  - v2.machine_observation:
      claim=page_category, source=title_heuristic  <- data/triage/label_proposals_*.json
      claim=page_category, source=agent_vision     <- legacy estimate.page_label (source LIKE 'claude-code%')
      claim=sheet_title,   source=title_heuristic  <- first plausible title line of each pagetext file
  - v2.human_decision (binding=false, imported):
      from estimate.page_label where source='nick_ui'          (actor_type=importer, original_source='nick_ui')
      from data/triage/eyeball_verdicts.csv                     (actor_type=importer, original_source='eyeball_verdicts')

Idempotent: re-running does not duplicate rows (checked via in-memory
existence sets before insert). Never touches legacy estimate.* tables
(read-only). Uses bulk SELECTs + execute_values to avoid per-row Neon
round trips (network latency, not CPU, is the binding constraint here).
"""

import csv
import json
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

PILOT_PERMITS = [
    "14-11290-NEWC", "26-10321-RNVN", "13-44121-NEWC", "13-27145-NEWC",
    "24-06748-RNVS", "26-05332-NEWC", "20-29653-RNVS", "25-33341-NEWC",
]


def get_conn():
    url = os.environ.get("NEON_DATABASE_URL")
    if not url:
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("NEON_DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    if not url:
        sys.exit("NEON_DATABASE_URL not set")
    return psycopg2.connect(url)


def shallow_permits(cur, counts):
    cur.execute("SELECT permit_num, description, sqft, address FROM estimate.permits")
    rows = cur.fetchall()
    cur.execute("SELECT permit_num FROM v2.permit")
    existing = {r[0] for r in cur.fetchall()}
    to_insert = [r for r in rows if r[0] not in existing]
    if to_insert:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO v2.permit (permit_num, city_description, city_sqft, address_raw) VALUES %s ON CONFLICT (permit_num) DO NOTHING",
            to_insert,
        )
    counts["v2.permit (shallow)"] = len(to_insert)


def shallow_documents(cur, counts):
    cur.execute(
        """
        SELECT DISTINCT ON (d.onestop_doc_id)
            d.onestop_doc_id, d.permit_num, d.filename, d.sha256
        FROM estimate.document d
        ORDER BY d.onestop_doc_id, d.id
        """
    )
    rows = cur.fetchall()
    cur.execute("SELECT permit_num, id FROM v2.permit")
    permit_id_by_num = {r[0]: r[1] for r in cur.fetchall()}
    cur.execute("SELECT onestop_doc_id FROM v2.document")
    existing = {r[0] for r in cur.fetchall()}
    to_insert = []
    for onestop_doc_id, permit_num, filename, sha256 in rows:
        if onestop_doc_id in existing:
            continue
        permit_id = permit_id_by_num.get(permit_num)
        to_insert.append((onestop_doc_id, permit_id, filename, sha256))
    if to_insert:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO v2.document (onestop_doc_id, permit_id, filename, sha256) VALUES %s ON CONFLICT (onestop_doc_id) DO NOTHING",
            to_insert,
        )
    counts["v2.document (shallow)"] = len(to_insert)


def deep_buildings(cur, counts):
    cur.execute("SELECT id, permit_num FROM v2.permit WHERE permit_num = ANY(%s)", (PILOT_PERMITS,))
    permit_rows = cur.fetchall()
    cur.execute(
        "SELECT pb.permit_id FROM v2.permit_building pb JOIN v2.permit p ON p.id = pb.permit_id WHERE p.permit_num = ANY(%s)",
        (PILOT_PERMITS,),
    )
    already = {r[0] for r in cur.fetchall()}
    n_b = 0
    n_pb = 0
    for permit_id, permit_num in permit_rows:
        if permit_id in already:
            continue
        cur.execute(
            "INSERT INTO v2.building (name, address, notes) VALUES (%s, NULL, %s) RETURNING id",
            (f"Pilot building — {permit_num}", "auto-created by v2_backfill.py deep pass"),
        )
        building_id = cur.fetchone()[0]
        n_b += 1
        cur.execute(
            "INSERT INTO v2.permit_building (permit_id, building_id, role) VALUES (%s, %s, 'primary') ON CONFLICT DO NOTHING",
            (permit_id, building_id),
        )
        n_pb += cur.rowcount
    counts["v2.building (deep)"] = n_b
    counts["v2.permit_building (deep)"] = n_pb


def load_pilot_legacy_docs(cur):
    """legacy estimate.document rows for pilot permits: legacy_id, onestop_doc_id, permit_num"""
    cur.execute(
        "SELECT id, onestop_doc_id, permit_num FROM estimate.document WHERE permit_num = ANY(%s)",
        (PILOT_PERMITS,),
    )
    return cur.fetchall()


def deep_pages(cur, counts, legacy_docs, v2_doc_id_by_onestop):
    cur.execute("SELECT document_id, pdf_page_index FROM v2.page")
    existing = {(r[0], r[1]) for r in cur.fetchall()}
    to_insert = []
    for legacy_doc_id, onestop_doc_id, permit_num in legacy_docs:
        pagetext_dir = DATA / "pagetext" / str(onestop_doc_id)
        if not pagetext_dir.is_dir():
            continue
        txt_files = sorted(pagetext_dir.glob("page_*.txt"))
        if not txt_files:
            continue
        v2_doc_id = v2_doc_id_by_onestop.get(onestop_doc_id)
        if not v2_doc_id:
            continue
        for idx in range(len(txt_files)):
            if (v2_doc_id, idx) in existing:
                continue
            to_insert.append((v2_doc_id, idx))
            existing.add((v2_doc_id, idx))
    if to_insert:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO v2.page (document_id, pdf_page_index) VALUES %s ON CONFLICT (document_id, pdf_page_index) DO NOTHING",
            to_insert,
        )
    counts["v2.page (deep)"] = len(to_insert)


TITLE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-/&.,']{4,60}$")


def guess_title(text_path: Path):
    try:
        lines = text_path.read_text(errors="ignore").splitlines()
    except Exception:
        return None
    for line in lines[:40]:
        s = line.strip()
        if not s:
            continue
        letters = [c for c in s if c.isalpha()]
        if len(letters) < 4:
            continue
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.8 and TITLE_RE.match(s):
            return s[:200]
    return None


def deep_machine_observations(cur, counts, legacy_docs, v2_doc_id_by_onestop):
    # page_id lookup: (v2_doc_id, pdf_page_index) -> page_id, restricted to pilot docs
    v2_doc_ids = list(v2_doc_id_by_onestop.values())
    cur.execute("SELECT id, document_id, pdf_page_index FROM v2.page WHERE document_id = ANY(%s)", (v2_doc_ids,))
    page_id_by_docpage = {(r[1], r[2]): r[0] for r in cur.fetchall()}

    cur.execute(
        "SELECT target_id, source FROM v2.machine_observation WHERE claim = 'page_category' AND target_type = 'page'"
    )
    existing_mo_cat = {(r[0], r[1]) for r in cur.fetchall()}
    cur.execute(
        "SELECT target_id, source FROM v2.machine_observation WHERE claim = 'sheet_title' AND target_type = 'page'"
    )
    existing_mo_title = {(r[0], r[1]) for r in cur.fetchall()}

    mo_cat_rows = []
    mo_title_rows = []

    legacy_id_to_onestop = {r[0]: r[1] for r in legacy_docs}
    permit_to_onestop_ids = {}
    for legacy_doc_id, onestop_doc_id, permit_num in legacy_docs:
        permit_to_onestop_ids.setdefault(permit_num, []).append(onestop_doc_id)

    # --- title_heuristic page_category from data/triage/label_proposals_*.json ---
    for path in sorted((DATA / "triage").glob("label_proposals_*.json")):
        permit_num = path.stem.replace("label_proposals_", "")
        if permit_num not in PILOT_PERMITS:
            continue
        try:
            proposals = json.loads(path.read_text())
        except Exception:
            continue
        for onestop_doc_id in permit_to_onestop_ids.get(permit_num, []):
            v2_doc_id = v2_doc_id_by_onestop.get(onestop_doc_id)
            if not v2_doc_id:
                continue
            for page_index_str, obs in proposals.items():
                try:
                    page_index = int(page_index_str)
                except ValueError:
                    continue
                page_id = page_id_by_docpage.get((v2_doc_id, page_index))
                if not page_id:
                    continue
                if (page_id, "title_heuristic") in existing_mo_cat:
                    continue
                value = {"category": obs.get("label"), "evidence": obs.get("evidence")}
                mo_cat_rows.append((page_id, json.dumps(value), "title_heuristic", "v1", None, None))
                existing_mo_cat.add((page_id, "title_heuristic"))

    # --- agent_vision page_category from legacy estimate.page_label ---
    cur.execute(
        """
        SELECT pl.category, pl.confidence, pl.source, ep.document_id, ep.page_index
        FROM estimate.page_label pl
        JOIN estimate.page ep ON ep.id = pl.page_id
        JOIN estimate.document ed ON ed.id = ep.document_id
        WHERE ed.permit_num = ANY(%s) AND pl.source LIKE 'claude-code%%'
        """,
        (PILOT_PERMITS,),
    )
    for category, confidence, source, legacy_doc_id, page_index in cur.fetchall():
        onestop_doc_id = legacy_id_to_onestop.get(legacy_doc_id)
        if not onestop_doc_id:
            continue
        v2_doc_id = v2_doc_id_by_onestop.get(onestop_doc_id)
        if not v2_doc_id:
            continue
        page_id = page_id_by_docpage.get((v2_doc_id, page_index))
        if not page_id:
            continue
        if (page_id, "agent_vision") in existing_mo_cat:
            continue
        value = {"category": category, "legacy_source": source}
        mo_cat_rows.append((page_id, json.dumps(value), "agent_vision", source, confidence, "confidence"))
        existing_mo_cat.add((page_id, "agent_vision"))

    if mo_cat_rows:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO v2.machine_observation
                (target_type, target_id, claim, value_json, source, source_version, score_raw, score_type)
            VALUES %s
            """,
            [("page", pid, "page_category", val, src, srcver, score, scoretype)
             for (pid, val, src, srcver, score, scoretype) in mo_cat_rows],
        )

    # --- sheet_title from first plausible title line of pagetext files ---
    for legacy_doc_id, onestop_doc_id, permit_num in legacy_docs:
        pagetext_dir = DATA / "pagetext" / str(onestop_doc_id)
        if not pagetext_dir.is_dir():
            continue
        v2_doc_id = v2_doc_id_by_onestop.get(onestop_doc_id)
        if not v2_doc_id:
            continue
        for idx, txt_file in enumerate(sorted(pagetext_dir.glob("page_*.txt"))):
            title = guess_title(txt_file)
            if not title:
                continue
            page_id = page_id_by_docpage.get((v2_doc_id, idx))
            if not page_id:
                continue
            if (page_id, "title_heuristic") in existing_mo_title:
                continue
            mo_title_rows.append((page_id, json.dumps({"title": title})))
            existing_mo_title.add((page_id, "title_heuristic"))

    if mo_title_rows:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO v2.machine_observation (target_type, target_id, claim, value_json, source, source_version) VALUES %s",
            [("page", pid, "sheet_title", val, "title_heuristic", "v1") for (pid, val) in mo_title_rows],
        )

    n_titleheur = sum(1 for r in mo_cat_rows if r[2] == "title_heuristic")
    n_agentvision = sum(1 for r in mo_cat_rows if r[2] == "agent_vision")
    counts["v2.machine_observation page_category (title_heuristic)"] = n_titleheur
    counts["v2.machine_observation page_category (agent_vision)"] = n_agentvision
    counts["v2.machine_observation sheet_title (title_heuristic)"] = len(mo_title_rows)


def deep_human_decisions(cur, counts, legacy_docs, v2_doc_id_by_onestop):
    v2_doc_ids = list(v2_doc_id_by_onestop.values())
    cur.execute("SELECT id, document_id, pdf_page_index FROM v2.page WHERE document_id = ANY(%s)", (v2_doc_ids,))
    page_id_by_docpage = {(r[1], r[2]): r[0] for r in cur.fetchall()}
    legacy_id_to_onestop = {r[0]: r[1] for r in legacy_docs}

    cur.execute("SELECT target_id, note FROM v2.human_decision WHERE claim = 'page_category' AND original_source = 'nick_ui'")
    existing_nickui_notes = {r[1] for r in cur.fetchall()}
    cur.execute("SELECT target_id, note FROM v2.human_decision WHERE claim = 'page_flags' AND original_source = 'eyeball_verdicts'")
    existing_eyeball_notes = {r[1] for r in cur.fetchall()}

    nickui_rows = []
    eyeball_rows = []

    # --- imported from estimate.page_label where source='nick_ui' ---
    cur.execute(
        """
        SELECT pl.id, pl.category, ep.document_id, ep.page_index
        FROM estimate.page_label pl
        JOIN estimate.page ep ON ep.id = pl.page_id
        JOIN estimate.document ed ON ed.id = ep.document_id
        WHERE ed.permit_num = ANY(%s) AND pl.source = 'nick_ui'
        """,
        (PILOT_PERMITS,),
    )
    for legacy_pl_id, category, legacy_doc_id, page_index in cur.fetchall():
        if not category:
            continue
        onestop_doc_id = legacy_id_to_onestop.get(legacy_doc_id)
        if not onestop_doc_id:
            continue
        v2_doc_id = v2_doc_id_by_onestop.get(onestop_doc_id)
        if not v2_doc_id:
            continue
        page_id = page_id_by_docpage.get((v2_doc_id, page_index))
        if not page_id:
            continue
        note_key = f"legacy_page_label.id={legacy_pl_id}"
        if note_key in existing_nickui_notes:
            continue
        nickui_rows.append((page_id, json.dumps({"category": category}), note_key))

    if nickui_rows:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO v2.human_decision
                (target_type, target_id, claim, value_json, actor_type, actor_id, original_source, binding, note)
            VALUES %s
            """,
            [("page", pid, "page_category", val, "importer", "legacy_import", "nick_ui", False, note)
             for (pid, val, note) in nickui_rows],
        )

    # --- imported from data/triage/eyeball_verdicts.csv ---
    csv_path = DATA / "triage" / "eyeball_verdicts.csv"
    if csv_path.exists():
        with csv_path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader):
                permit_num = row.get("permit")
                if permit_num not in PILOT_PERMITS:
                    continue
                onestop_doc_id_raw = row.get("doc_id")
                page_str = row.get("page")
                if not onestop_doc_id_raw or page_str is None:
                    continue
                try:
                    onestop_doc_id = int(onestop_doc_id_raw)
                    page_index = int(page_str)
                except ValueError:
                    continue
                v2_doc_id = v2_doc_id_by_onestop.get(onestop_doc_id)
                if not v2_doc_id:
                    continue
                page_id = page_id_by_docpage.get((v2_doc_id, page_index))
                if not page_id:
                    continue
                note_key = f"eyeball_verdicts.csv:row{row_idx}"
                if note_key in existing_eyeball_notes:
                    continue
                value = {
                    "verdict": row.get("verdict"),
                    "is_floor_plan": row.get("is_floor_plan"),
                    "reason": row.get("reason"),
                    "slice": row.get("slice"),
                }
                eyeball_rows.append((page_id, json.dumps(value), note_key))

    if eyeball_rows:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO v2.human_decision
                (target_type, target_id, claim, value_json, actor_type, actor_id, original_source, binding, note)
            VALUES %s
            """,
            [("page", pid, "page_flags", val, "importer", "legacy_import", "eyeball_verdicts", False, note)
             for (pid, val, note) in eyeball_rows],
        )

    counts["v2.human_decision (nick_ui import)"] = len(nickui_rows)
    counts["v2.human_decision (eyeball_verdicts import)"] = len(eyeball_rows)


def main():
    conn = get_conn()
    conn.autocommit = False
    counts = {}
    try:
        with conn.cursor() as cur:
            shallow_permits(cur, counts)
            shallow_documents(cur, counts)
            deep_buildings(cur, counts)

            legacy_docs = load_pilot_legacy_docs(cur)
            onestop_ids = list({r[1] for r in legacy_docs})
            cur.execute("SELECT onestop_doc_id, id FROM v2.document WHERE onestop_doc_id = ANY(%s)", (onestop_ids,))
            v2_doc_id_by_onestop = {r[0]: r[1] for r in cur.fetchall()}

            deep_pages(cur, counts, legacy_docs, v2_doc_id_by_onestop)
            deep_machine_observations(cur, counts, legacy_docs, v2_doc_id_by_onestop)
            deep_human_decisions(cur, counts, legacy_docs, v2_doc_id_by_onestop)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("\n=== v2_backfill.py — row-count summary (rows inserted this run) ===")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
