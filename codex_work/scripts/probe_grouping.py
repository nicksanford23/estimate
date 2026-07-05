#!/usr/bin/env python3
"""Codex-only Stage 2 grouping probe.

Reads current truth labels from Neon, loads local page text when available, and
groups takeoff-relevant pages into rough floor/area packets with deterministic
rules. This is exploratory: outputs stay under codex_work/outputs and no main
project code/schema is touched.

Usage:
    python codex_work/scripts/probe_grouping.py
    python codex_work/scripts/probe_grouping.py --limit-permits 10
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs"
KEEP_CATEGORIES = {"floor_plan", "finish_plan", "finish_schedule", "demo_plan"}
FINISH_CATEGORIES = {"finish_plan", "finish_schedule"}


SOURCE_PRIORITY_SQL = """
CASE pl.source
  WHEN 'human' THEN 4
  WHEN 'claude-code-adjudicate' THEN 3
  WHEN 'claude-code-review' THEN 2
  WHEN 'claude-code' THEN 1
  WHEN 'claude-code-pilot' THEN 1
  ELSE 0
END
"""


@dataclass
class PageRecord:
    page_id: int
    document_id: int
    permit_num: str
    onestop_doc_id: int
    filename: str
    page_index: int
    image_path: str
    has_vector_text: bool
    category: str
    label_confidence: float | None
    sheet_title: str | None
    evidence: str | None
    text: str = ""


@dataclass
class Assignment:
    page: PageRecord
    sheet_number: str | None
    floor: str | None
    area: str | None
    group_key: str | None
    confidence: float
    matched_rules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_env() -> dict[str, str]:
    env = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    env.update({k: v for k, v in os.environ.items() if k not in env})
    return env


def page_text_path(image_path: str) -> Path:
    rel = image_path
    if rel.startswith(str(ROOT)):
        rel = os.path.relpath(rel, ROOT)
    if rel.startswith("data/pages/"):
        rel = rel.replace("data/pages/", "data/pagetext/", 1)
    rel = os.path.splitext(rel)[0] + ".txt"
    return ROOT / rel


def read_page_text(image_path: str, max_chars: int = 12000) -> str:
    path = page_text_path(image_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]


def fetch_pages(database_url: str, permit_limit: int | None = None) -> list[PageRecord]:
    import psycopg2

    sql = f"""
    WITH ranked AS (
      SELECT
        pl.*,
        p.document_id,
        d.permit_num,
        d.onestop_doc_id,
        d.filename,
        p.page_index,
        p.image_path,
        p.has_vector_text,
        ROW_NUMBER() OVER (
          PARTITION BY pl.page_id
          ORDER BY {SOURCE_PRIORITY_SQL} DESC, pl.created_at DESC, pl.id DESC
        ) AS rn
      FROM page_label pl
      JOIN page p ON p.id = pl.page_id
      JOIN document d ON d.id = p.document_id
    ),
    truth AS (
      SELECT * FROM ranked WHERE rn = 1
    )
    SELECT
      page_id,
      document_id,
      permit_num,
      onestop_doc_id,
      filename,
      page_index,
      image_path,
      has_vector_text,
      category,
      confidence,
      sheet_title,
      evidence
    FROM truth
    WHERE category = ANY(%s)
    ORDER BY permit_num, document_id, page_index
    """
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(sql, (sorted(KEEP_CATEGORIES),))
        rows = cur.fetchall()
    finally:
        conn.close()

    pages = [
        PageRecord(
            page_id=int(r[0]),
            document_id=int(r[1]),
            permit_num=str(r[2]),
            onestop_doc_id=int(r[3]),
            filename=str(r[4] or ""),
            page_index=int(r[5]),
            image_path=str(r[6] or ""),
            has_vector_text=bool(r[7]),
            category=str(r[8]),
            label_confidence=float(r[9]) if r[9] is not None else None,
            sheet_title=str(r[10]) if r[10] else None,
            evidence=str(r[11]) if r[11] else None,
        )
        for r in rows
    ]
    if permit_limit is not None:
        permits = []
        seen = set()
        for p in pages:
            if p.permit_num not in seen:
                seen.add(p.permit_num)
                permits.append(p.permit_num)
            if len(permits) >= permit_limit:
                break
        keep = set(permits)
        pages = [p for p in pages if p.permit_num in keep]

    for page in pages:
        page.text = read_page_text(page.image_path)
    return pages


SHEET_RX = re.compile(
    r"\b((?:[A-Z]{1,4}|ID|I|A|AD|D|G|FS|FP|F|LS|P)[- .]?\d{1,4}"
    r"(?:\.\d+)*(?:[A-Z])?)\b",
    re.IGNORECASE,
)


def normalize_token(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s.strip().lower())
    return re.sub(r"_+", "_", s).strip("_")


def parse_sheet_number(*texts: str | None) -> tuple[str | None, str | None]:
    for source_name, text in texts:
        if not text:
            continue
        m = SHEET_RX.search(text[:1000])
        if m:
            sheet = re.sub(r"[\s.]+", "", m.group(1).upper())
            return sheet, f"sheet_number:{source_name}"
    return None, None


ORDINAL_FLOORS = [
    ("basement", [r"\bbasement\b", r"\bcellar\b"]),
    ("ground_floor", [r"\bground\s+floor\b"]),
    ("level_01", [r"\bfirst\s+floor\b", r"\b1st\s+floor\b", r"\blevel\s*0?1\b", r"\bl0?1\b"]),
    ("level_02", [r"\bsecond\s+floor\b", r"\b2nd\s+floor\b", r"\blevel\s*0?2\b", r"\bl0?2\b"]),
    ("level_03", [r"\bthird\s+floor\b", r"\b3rd\s+floor\b", r"\blevel\s*0?3\b", r"\bl0?3\b"]),
    ("level_04", [r"\bfourth\s+floor\b", r"\b4th\s+floor\b", r"\blevel\s*0?4\b", r"\bl0?4\b"]),
    ("level_05", [r"\bfifth\s+floor\b", r"\b5th\s+floor\b", r"\blevel\s*0?5\b", r"\bl0?5\b"]),
    ("level_06", [r"\bsixth\s+floor\b", r"\b6th\s+floor\b", r"\blevel\s*0?6\b", r"\bl0?6\b"]),
    ("roof", [r"\broof\b", r"\broof\s+plan\b"]),
    ("mezzanine", [r"\bmezzanine\b", r"\bmezz\b"]),
    ("penthouse", [r"\bpenthouse\b"]),
]

AREA_PATTERNS = [
    ("building", r"\bbuilding\s+([A-Z0-9-]+)\b"),
    ("tower", r"\btower\s+([A-Z0-9-]+)\b"),
    ("area", r"\barea\s+([A-Z0-9-]+)\b"),
    ("quad", r"\bquad(?:rant)?\s+([A-Z0-9-]+)\b"),
    ("wing", r"\b([A-Z0-9-]+)\s+wing\b"),
    ("suite", r"\bsuite\s+([A-Z0-9-]+)\b"),
    ("unit", r"\bunit\s+([A-Z0-9-]+)\b"),
    ("lobby", r"\blobby\b"),
    ("ballroom", r"\bballroom\b"),
]


def find_floor(texts: Iterable[tuple[str, str]]) -> tuple[str | None, str | None]:
    for source, text in texts:
        if not text:
            continue
        hay = text[:4000].lower()
        for floor, patterns in ORDINAL_FLOORS:
            for pat in patterns:
                if re.search(pat, hay, re.IGNORECASE):
                    return floor, f"floor:{source}:{floor}"
        m = re.search(r"\b(?:floor|level)\s+([0-9]{1,2})\b", hay, re.IGNORECASE)
        if m:
            return f"level_{int(m.group(1)):02d}", f"floor:{source}:numeric"
    return None, None


def find_area(texts: Iterable[tuple[str, str]]) -> tuple[str | None, str | None]:
    for source, text in texts:
        if not text:
            continue
        hay = text[:2500]
        for name, pat in AREA_PATTERNS:
            m = re.search(pat, hay, re.IGNORECASE)
            if m:
                if m.lastindex:
                    val = normalize_token(f"{name}_{m.group(1)}")
                else:
                    val = normalize_token(name)
                return val, f"area:{source}:{val}"
    return None, None


def initial_assignment(page: PageRecord) -> Assignment:
    title = page.sheet_title or ""
    filename = page.filename or ""
    evidence = page.evidence or ""
    text = page.text or ""
    sheet, sheet_rule = parse_sheet_number(
        ("sheet_title", title),
        ("filename", filename),
        ("page_text", text),
        ("evidence", evidence),
    )
    floor, floor_rule = find_floor(
        [
            ("sheet_title", title),
            ("filename", filename),
            ("evidence", evidence),
            ("page_text", text),
        ]
    )
    area, area_rule = find_area(
        [
            ("sheet_title", title),
            ("filename", filename),
            ("evidence", evidence),
        ]
    )
    rules = [r for r in [sheet_rule, floor_rule, area_rule] if r]
    warnings = []

    confidence = 0.0
    if sheet:
        confidence += 0.12
    if floor:
        confidence += 0.62 if floor_rule and "sheet_title" in floor_rule else 0.42
    if area:
        confidence += 0.16

    group_key = None
    if floor:
        group_key = f"{page.permit_num}:doc_{page.document_id}:{floor}"
        if area:
            group_key += f":{area}"
    elif page.category == "finish_schedule":
        group_key = f"{page.permit_num}:doc_{page.document_id}:global_schedule"
        confidence = max(confidence, 0.45)
        rules.append("fallback:global_finish_schedule")
        warnings.append("schedule has no floor token; may apply to multiple groups")
    else:
        warnings.append("no floor/area token found")

    if not page.text.strip():
        warnings.append("missing local pagetext")
    if not page.sheet_title:
        warnings.append("missing sheet_title")

    return Assignment(
        page=page,
        sheet_number=sheet,
        floor=floor,
        area=area,
        group_key=group_key,
        confidence=min(confidence, 0.95),
        matched_rules=rules,
        warnings=warnings,
    )


def apply_adjacent_fallback(assignments: list[Assignment]) -> None:
    by_doc: dict[int, list[Assignment]] = {}
    for a in assignments:
        by_doc.setdefault(a.page.document_id, []).append(a)
    for doc_assignments in by_doc.values():
        doc_assignments.sort(key=lambda a: a.page.page_index)
        for i, a in enumerate(doc_assignments):
            if a.group_key or a.page.category == "finish_schedule":
                continue
            candidates = []
            for j, other in enumerate(doc_assignments):
                if i == j or not other.floor or not other.group_key:
                    continue
                dist = abs(other.page.page_index - a.page.page_index)
                if dist <= 2:
                    candidates.append((dist, other))
            if not candidates:
                continue
            candidates.sort(key=lambda x: x[0])
            neighbor = candidates[0][1]
            a.floor = neighbor.floor
            a.area = neighbor.area
            a.group_key = neighbor.group_key
            a.confidence = max(a.confidence, 0.35)
            a.matched_rules.append(
                f"fallback:adjacent_page:{neighbor.page.page_id}:distance_{candidates[0][0]}"
            )
            a.warnings.append("assigned by adjacent-page fallback")


def compact_page(a: Assignment) -> dict:
    p = a.page
    return {
        "page_id": p.page_id,
        "page_index": p.page_index,
        "category": p.category,
        "sheet_title": p.sheet_title,
        "sheet_number": a.sheet_number,
        "floor": a.floor,
        "area": a.area,
        "confidence": round(a.confidence, 3),
        "matched_rules": a.matched_rules,
        "warnings": a.warnings,
    }


def packetize(assignments: list[Assignment]) -> list[dict]:
    packets: dict[tuple[str, int], list[Assignment]] = {}
    for a in assignments:
        packets.setdefault((a.page.permit_num, a.page.document_id), []).append(a)

    out = []
    for (permit, doc_id), rows in sorted(packets.items()):
        rows.sort(key=lambda a: a.page.page_index)
        groups: dict[str, list[Assignment]] = {}
        ungrouped = []
        warnings = []
        for a in rows:
            warnings.extend(a.warnings)
            if a.group_key:
                groups.setdefault(a.group_key, []).append(a)
            else:
                ungrouped.append(a)

        group_objs = []
        for key, items in sorted(groups.items()):
            cats = sorted({i.page.category for i in items})
            group_objs.append(
                {
                    "group_key": key,
                    "floor": items[0].floor,
                    "area": items[0].area,
                    "categories": cats,
                    "confidence": round(statistics.mean(i.confidence for i in items), 3),
                    "pages": [compact_page(i) for i in sorted(items, key=lambda x: x.page.page_index)],
                }
            )
        first = rows[0].page
        out.append(
            {
                "permit_num": permit,
                "document_id": doc_id,
                "onestop_doc_id": first.onestop_doc_id,
                "filename": first.filename,
                "n_relevant_pages": len(rows),
                "n_grouped_pages": sum(len(g["pages"]) for g in group_objs),
                "groups": group_objs,
                "ungrouped_pages": [compact_page(a) for a in ungrouped],
                "warnings": sorted(set(warnings)),
            }
        )
    return out


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def summarize(assignments: list[Assignment], packets: list[dict], elapsed_ms: int) -> str:
    total = len(assignments)
    grouped = sum(1 for a in assignments if a.group_key)
    low_conf = sum(1 for a in assignments if a.group_key and a.confidence < 0.5)
    ungrouped = total - grouped
    finish = [a for a in assignments if a.page.category in FINISH_CATEGORIES]
    finish_grouped = sum(1 for a in finish if a.group_key)
    paired_groups = 0
    total_groups = 0
    for p in packets:
        for g in p["groups"]:
            total_groups += 1
            cats = set(g["categories"])
            if "floor_plan" in cats and (cats & FINISH_CATEGORIES):
                paired_groups += 1

    by_category = {}
    for a in assignments:
        d = by_category.setdefault(a.page.category, {"total": 0, "grouped": 0})
        d["total"] += 1
        d["grouped"] += int(bool(a.group_key))

    lines = [
        "# Grouping Probe Summary",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"Elapsed: {elapsed_ms} ms",
        "",
        "## Headline",
        "",
        f"- Packets: {len(packets)} permit/document packets",
        f"- Relevant pages: {total}",
        f"- Grouped pages: {grouped} ({grouped / total:.1%})" if total else "- Grouped pages: 0",
        f"- Ungrouped pages: {ungrouped}",
        f"- Low-confidence grouped pages: {low_conf}",
        f"- Finish pages grouped: {finish_grouped}/{len(finish)}",
        f"- Groups containing floor_plan plus finish_plan/finish_schedule: {paired_groups}/{total_groups}",
        "",
        "## By Category",
        "",
        "| category | total | grouped | grouped % |",
        "|---|---:|---:|---:|",
    ]
    for cat, d in sorted(by_category.items()):
        pct = d["grouped"] / d["total"] if d["total"] else 0
        lines.append(f"| {cat} | {d['total']} | {d['grouped']} | {pct:.1%} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a rule baseline over existing current-truth labels and local page text.",
            "It is not an accuracy claim because no floor/area gold set exists yet.",
            "The next step is to manually review a small gold set of permit/document packets",
            "and score whether these group assignments match the actual floors/areas.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--limit-permits", type=int, default=None)
    parser.add_argument(
        "--jsonl",
        default=str(OUT_DIR / "grouping_probe.jsonl"),
        help="Codex-owned packet JSONL output path",
    )
    parser.add_argument(
        "--summary",
        default=str(OUT_DIR / "grouping_probe_summary.md"),
        help="Codex-owned Markdown summary output path",
    )
    args = parser.parse_args()

    env = load_env()
    database_url = args.database_url or env.get("NEON_DATABASE_URL")
    if not database_url:
        raise SystemExit("NEON_DATABASE_URL missing from .env/env; pass --database-url")

    t0 = time.time()
    pages = fetch_pages(database_url, permit_limit=args.limit_permits)
    assignments = [initial_assignment(p) for p in pages]
    apply_adjacent_fallback(assignments)
    packets = packetize(assignments)
    elapsed_ms = int(round((time.time() - t0) * 1000))

    jsonl_path = Path(args.jsonl)
    summary_path = Path(args.summary)
    write_jsonl(jsonl_path, packets)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summarize(assignments, packets, elapsed_ms) + "\n", encoding="utf-8")

    print(f"pages={len(pages)} packets={len(packets)}")
    print(f"wrote {jsonl_path}")
    print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
