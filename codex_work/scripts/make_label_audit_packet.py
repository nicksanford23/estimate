#!/usr/bin/env python3
"""Build a Codex-only label audit packet from Neon current truth.

The packet targets frozen eval permits first, with emphasis on finish pages and
potential false negatives. Outputs are for human/agent review only and stay in
codex_work/outputs.
"""
from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path


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


def load_eval_permits(split_path: Path) -> list[str]:
    split = json.loads(split_path.read_text())
    return list(split["eval"])


def fetch_truth(database_url: str, eval_permits: list[str]) -> list[dict]:
    import psycopg2

    sql = f"""
    WITH ranked AS (
      SELECT
        pl.*,
        p.document_id,
        p.page_index,
        p.image_path,
        p.has_vector_text,
        d.permit_num,
        d.onestop_doc_id,
        d.filename,
        ROW_NUMBER() OVER (
          PARTITION BY pl.page_id
          ORDER BY {SOURCE_PRIORITY_SQL} DESC, pl.created_at DESC, pl.id DESC
        ) AS rn
      FROM page_label pl
      JOIN page p ON p.id = pl.page_id
      JOIN document d ON d.id = p.document_id
      WHERE d.permit_num = ANY(%s)
    )
    SELECT
      page_id, source, category, confidence, sheet_title,
      scale_visible, finish_codes_visible, table_present,
      room_labels_visible, dimensions_visible, flag_reason, evidence,
      document_id, page_index, image_path, has_vector_text,
      permit_num, onestop_doc_id, filename
    FROM ranked
    WHERE rn = 1
    ORDER BY permit_num, document_id, page_index
    """
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(sql, (eval_permits,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()
    for row in rows:
        row["page_id"] = int(row["page_id"])
        row["document_id"] = int(row["document_id"])
        row["page_index"] = int(row["page_index"])
        row["onestop_doc_id"] = int(row["onestop_doc_id"])
        row["confidence"] = float(row["confidence"]) if row["confidence"] is not None else None
        for k in (
            "scale_visible",
            "finish_codes_visible",
            "table_present",
            "room_labels_visible",
            "dimensions_visible",
            "has_vector_text",
        ):
            row[k] = bool(row[k])
        row["image_abs_path"] = str((ROOT / row["image_path"]).resolve())
    return rows


def stable_sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    rows = sorted(rows, key=lambda r: (r["permit_num"], r["document_id"], r["page_index"]))
    if len(rows) <= n:
        return rows
    rng = random.Random(seed)
    return sorted(rng.sample(rows, n), key=lambda r: (r["permit_num"], r["document_id"], r["page_index"]))


def select_packet(rows: list[dict]) -> list[dict]:
    selected: dict[int, dict] = {}

    def add(bucket: str, candidates: list[dict], cap: int | None = None) -> None:
        use = candidates if cap is None else stable_sample(candidates, cap, seed=42 + len(selected))
        for row in use:
            row = dict(row)
            row.setdefault("audit_buckets", [])
            row["audit_buckets"] = sorted(set(row["audit_buckets"] + [bucket]))
            if row["page_id"] in selected:
                selected[row["page_id"]]["audit_buckets"] = sorted(
                    set(selected[row["page_id"]]["audit_buckets"] + [bucket])
                )
            else:
                selected[row["page_id"]] = row

    finish = [r for r in rows if r["category"] in FINISH_CATEGORIES]
    add("all_eval_finish_pages", finish)

    potential_missed_finish = [
        r
        for r in rows
        if r["category"] not in FINISH_CATEGORIES
        and (
            r["finish_codes_visible"]
            or ("finish" in (r.get("sheet_title") or "").lower())
            or ("finish" in (r.get("evidence") or "").lower())
            or r["table_present"]
        )
    ]
    add("potential_finish_false_negative", potential_missed_finish, cap=20)

    low_conf_or_flagged = [
        r
        for r in rows
        if (r["confidence"] is not None and r["confidence"] < 0.8) or r.get("flag_reason")
    ]
    add("low_confidence_or_flagged", low_conf_or_flagged, cap=15)

    floor_demo = [r for r in rows if r["category"] in {"floor_plan", "demo_plan"}]
    add("floor_demo_sample", floor_demo, cap=12)

    adjacent_nonkeep = [
        r
        for r in rows
        if r["category"]
        in {"detail", "elevation_section", "life_safety", "schedule_other", "furniture_plan"}
    ]
    add("adjacent_nonkeep_sample", adjacent_nonkeep, cap=12)

    packet = sorted(selected.values(), key=lambda r: (r["permit_num"], r["document_id"], r["page_index"]))
    for i, row in enumerate(packet, 1):
        row["audit_id"] = i
        row["current_keep"] = row["category"] in KEEP_CATEGORIES
        row["current_finish"] = row["category"] in FINISH_CATEGORIES
    return packet


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def write_summary(path: Path, rows: list[dict], packet: list[dict]) -> None:
    by_cat = {}
    for row in rows:
        by_cat[row["category"]] = by_cat.get(row["category"], 0) + 1
    packet_by_cat = {}
    for row in packet:
        packet_by_cat[row["category"]] = packet_by_cat.get(row["category"], 0) + 1
    buckets = {}
    for row in packet:
        for b in row["audit_buckets"]:
            buckets[b] = buckets.get(b, 0) + 1

    lines = [
        "# Label Audit Packet",
        "",
        "Scope: frozen split_v1 eval permits, Neon current truth.",
        "",
        "## Corpus Counts In Eval Permits",
        "",
        f"- Current-truth labeled pages: {len(rows)}",
        f"- Finish pages: {sum(1 for r in rows if r['category'] in FINISH_CATEGORIES)}",
        f"- Keep pages: {sum(1 for r in rows if r['category'] in KEEP_CATEGORIES)}",
        "",
        "## Packet Counts",
        "",
        f"- Audit pages selected: {len(packet)}",
        "",
        "| bucket | pages |",
        "|---|---:|",
    ]
    for b, n in sorted(buckets.items()):
        lines.append(f"| {b} | {n} |")
    lines.extend(["", "## Packet By Current Category", "", "| category | pages |", "|---|---:|"])
    for cat, n in sorted(packet_by_cat.items()):
        lines.append(f"| {cat} | {n} |")
    lines.extend(["", "## Eval Current Truth By Category", "", "| category | pages |", "|---|---:|"])
    for cat, n in sorted(by_cat.items()):
        lines.append(f"| {cat} | {n} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--split", default=str(ROOT / "data" / "split_v1.json"))
    parser.add_argument("--jsonl", default=str(OUT_DIR / "label_audit_packet.jsonl"))
    parser.add_argument("--summary", default=str(OUT_DIR / "label_audit_packet_summary.md"))
    args = parser.parse_args()

    env = load_env()
    database_url = args.database_url or env.get("NEON_DATABASE_URL")
    if not database_url:
        raise SystemExit("NEON_DATABASE_URL missing from .env/env; pass --database-url")

    eval_permits = load_eval_permits(Path(args.split))
    rows = fetch_truth(database_url, eval_permits)
    packet = select_packet(rows)
    write_jsonl(Path(args.jsonl), packet)
    write_summary(Path(args.summary), rows, packet)
    print(f"eval_current_truth_pages={len(rows)} audit_pages={len(packet)}")
    print(f"wrote {args.jsonl}")
    print(f"wrote {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
