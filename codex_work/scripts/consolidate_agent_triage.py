#!/usr/bin/env python3
"""Consolidate two-agent document triage outputs into reversible queues."""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs" / "agent_triage_wave_001"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_packet_index(batch_dir: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for path in sorted(batch_dir.glob("batch_*.jsonl")):
        for packet in load_jsonl(path):
            for doc in packet.get("documents", []):
                out[int(doc["doc_id"])] = {
                    "doc_id": int(doc["doc_id"]),
                    "permit_num": packet["permit_num"],
                    "name": doc.get("name", ""),
                    "already_downloaded": doc.get("already_downloaded", False),
                    "permit_description": packet.get("description", ""),
                }
    return out


def parse_agent_outputs(out_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    pattern = str(out_dir / "agent_*_batch_*.jsonl")
    by_batch: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for filename in sorted(glob.glob(pattern)):
        path = Path(filename)
        match = re.match(r"agent_([^_]+)_batch_(\d+)\.jsonl$", path.name)
        if not match:
            continue
        agent, batch = match.groups()
        rows = load_jsonl(path)
        by_batch[batch][agent] = {row["permit_num"]: row for row in rows}
    return by_batch


def doc_votes(agent_records: dict[str, dict[str, Any]]) -> dict[int, list[dict[str, str]]]:
    votes: dict[int, list[dict[str, str]]] = defaultdict(list)
    for agent, permits in agent_records.items():
        for permit_num, record in permits.items():
            for doc in record.get("documents", []):
                if doc.get("decision") == "download_now":
                    votes[int(doc["doc_id"])].append(
                        {
                            "agent": agent,
                            "permit_num": permit_num,
                            "reason": doc.get("reason", ""),
                        }
                    )
    return votes


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave-dir", default=str(OUT_DIR))
    parser.add_argument("--batch-dir", default=None)
    parser.add_argument("--min-votes", type=int, default=2)
    args = parser.parse_args()

    wave_dir = Path(args.wave_dir)
    batch_dir = Path(args.batch_dir) if args.batch_dir else wave_dir / "batches"
    packet_index = load_packet_index(batch_dir)
    by_batch = parse_agent_outputs(wave_dir)

    consensus_rows: list[dict[str, Any]] = []
    second_review_rows: list[dict[str, Any]] = []
    permit_agreement = Counter()
    permit_decisions = Counter()

    for batch, agents in sorted(by_batch.items()):
        if len(agents) < 2:
            continue
        all_permits = sorted(set().union(*(set(records) for records in agents.values())))
        for permit in all_permits:
            decisions = {
                agent: records.get(permit, {}).get("permit_decision", "missing")
                for agent, records in agents.items()
            }
            permit_decisions.update(decisions.values())
            permit_agreement["agree" if len(set(decisions.values())) == 1 else "disagree"] += 1

        votes = doc_votes(agents)
        for doc_id, doc_votes_for_id in sorted(votes.items()):
            meta = packet_index.get(doc_id, {"doc_id": doc_id})
            row = {
                "doc_id": doc_id,
                "permit_num": meta.get("permit_num", doc_votes_for_id[0]["permit_num"]),
                "already_downloaded": meta.get("already_downloaded", ""),
                "name": meta.get("name", ""),
                "votes": len(doc_votes_for_id),
                "agents": ";".join(v["agent"] for v in doc_votes_for_id),
                "reasons": " || ".join(f"{v['agent']}: {v['reason']}" for v in doc_votes_for_id),
            }
            if len(doc_votes_for_id) >= args.min_votes and not row["already_downloaded"]:
                consensus_rows.append(row)
            else:
                second_review_rows.append(row)

    fields = ["doc_id", "permit_num", "already_downloaded", "name", "votes", "agents", "reasons"]
    write_csv(wave_dir / "consensus_download_queue.csv", consensus_rows, fields)
    write_csv(wave_dir / "second_review_queue.csv", second_review_rows, fields)

    lines = [
        "# Agent Triage Consolidation",
        "",
        f"- Batches with at least two agent outputs: {sum(1 for a in by_batch.values() if len(a) >= 2)}",
        f"- Consensus download docs: {len(consensus_rows)}",
        f"- Second-review docs: {len(second_review_rows)}",
        f"- Permit decision agreement: {dict(permit_agreement)}",
        f"- Permit decisions seen: {dict(permit_decisions)}",
        "",
        "## Consensus Queue",
        "",
        "| doc_id | permit | name | votes |",
        "|---:|---|---|---:|",
    ]
    for row in consensus_rows[:80]:
        name = str(row["name"]).replace("|", "/")[:100]
        lines.append(f"| {row['doc_id']} | {row['permit_num']} | {name} | {row['votes']} |")
    (wave_dir / "consolidation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"consensus_docs={len(consensus_rows)}")
    print(f"second_review_docs={len(second_review_rows)}")
    print(f"summary={wave_dir / 'consolidation_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
