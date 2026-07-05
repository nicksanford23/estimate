#!/usr/bin/env python3
"""Build prioritized neutral packets for the next agent triage wave.

The score here only decides review order. It does not decide what to download.
Agents still make permit/document decisions from the packet evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def packet_text(packet: dict[str, Any]) -> str:
    docs = " ".join(doc.get("name", "") for doc in packet.get("documents", []))
    return f"{packet.get('description', '')} {packet.get('permit_class', '')} {docs}".lower()


def score_packet(packet: dict[str, Any]) -> int:
    text = packet_text(packet)
    score = 0
    positives = [
        (r"finish plan|finishes|finish schedule|room finish|material schedule|floor finish", 80),
        (r"interior design|interior scope|interiors|tenant|build ?out|fit ?out|whitebox", 55),
        (r"architectural|\barch\b|arc package|architecture set|a[- ]?\d", 45),
        (r"floor plan|floors plan|overall layout|enlarged layout", 45),
        (r"permit set|construction documents|cd set|issued for permit|approved plans|stamped plans|rcc", 35),
        (r"restaurant|hotel|retail|office|school|classroom|clinic|bar|coffee|commercial", 14),
        (r"renovation|remodel|alteration|change of use", 14),
    ]
    negatives = [
        (r"no interior work|exterior only|roof|re-roof|reroof|gutter|fence|sign|solar", -40),
        (r"receipt|invoice|certificate of occupancy|building permit|application|contract|letter|email", -18),
        (r"civil|survey|stormwater|foundation|structural|framing|pile|shoring", -16),
        (r"mep|mechanical|electrical|plumbing|sprinkler|fire alarm|comcheck|riser|hvac", -14),
    ]
    for pattern, points in positives:
        if re.search(pattern, text):
            score += points
    for pattern, points in negatives:
        if re.search(pattern, text):
            score += points

    if packet.get("already_downloaded_count", 0) == 0:
        score += 10
    elif packet.get("already_downloaded_count", 0) < packet.get("doc_count", 0):
        score += 4

    doc_count = int(packet.get("doc_count") or 0)
    if doc_count <= 30:
        score += 6
    elif doc_count > 80:
        score -= 15

    code = packet.get("code")
    if code in {"RNVS", "RNVN"}:
        score += 8
    return score


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", default=str(OUT_DIR / "agent_triage_packets.jsonl"))
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--out-dir", default=str(OUT_DIR / "agent_triage_wave_001"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--min-score", type=int, default=40)
    args = parser.parse_args()

    packets = load_jsonl(Path(args.packets))
    excluded: set[str] = set()
    for path_text in args.exclude:
        path = Path(path_text)
        if path.exists():
            excluded.update(row["permit_num"] for row in load_jsonl(path))

    candidates = []
    for packet in packets:
        if packet["permit_num"] in excluded:
            continue
        if packet.get("undownloaded_count", 0) <= 0:
            continue
        priority = score_packet(packet)
        if priority < args.min_score:
            continue
        packet = dict(packet)
        packet["triage_priority_score"] = priority
        candidates.append(packet)

    candidates.sort(key=lambda p: (-p["triage_priority_score"], p["permit_num"]))
    selected = candidates[: args.limit]

    out_dir = Path(args.out_dir)
    batch_dir = out_dir / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    for old in batch_dir.glob("batch_*.jsonl"):
        old.unlink()

    batch_paths = []
    for index in range(0, len(selected), args.batch_size):
        batch = selected[index : index + args.batch_size]
        path = batch_dir / f"batch_{index // args.batch_size:03d}.jsonl"
        write_jsonl(path, batch)
        batch_paths.append(path)

    manifest = [
        "# Agent Triage Wave 001",
        "",
        "Prioritized neutral packets for agent review. The score only selected review order.",
        "",
        f"- Selected permits: {len(selected)}",
        f"- Batch size: {args.batch_size}",
        f"- Batches: {len(batch_paths)}",
        f"- Min score: {args.min_score}",
        "",
        "| batch | permits | score_range |",
        "|---|---:|---|",
    ]
    for path in batch_paths:
        rows = load_jsonl(path)
        scores = [row["triage_priority_score"] for row in rows]
        manifest.append(f"| {path.name} | {len(rows)} | {min(scores)}-{max(scores)} |")
    (out_dir / "manifest.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")

    print(f"selected={len(selected)}")
    print(f"batches={len(batch_paths)}")
    print(f"out_dir={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
