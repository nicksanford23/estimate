#!/usr/bin/env python3
"""Build a cheap no-agent queue of likely architectural/primary-plan docs.

This is intentionally conservative and reversible:
- uses existing neutral permit/document packets
- excludes permits already selected in the primary-plan wave
- excludes doc_ids already logged as downloaded
- keeps one strong PDF per new permit by default for permit diversity
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_downloaded_ids(paths: list[Path]) -> set[int]:
    out: set[int] = set()
    for path in paths:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8", errors="ignore") as f:
            for row in csv.DictReader(f):
                status = row.get("status", "")
                if status and status not in {"ok", "already_in_r2", "rendered", "already_rendered"}:
                    continue
                try:
                    out.add(int(row["doc_id"]))
                except (KeyError, ValueError):
                    continue
    return out


def load_existing_permits(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {row["permit_num"] for row in csv.DictReader(f) if row.get("permit_num")}


def norm(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[_/.-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def has(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text, re.I))


def score_doc(packet: dict[str, Any], doc: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    name = norm(doc.get("name", ""))
    desc = norm(packet.get("description", ""))
    full = f"{name} {desc}"
    score = 0
    tags: list[str] = []
    reasons: list[str] = []

    strong = [
        ("architectural", 120, r"\barchitectural\b|\barchitecture\b|\barch\b|\barch set\b|\barc package\b|\bcd arch\b"),
        ("interior_design", 115, r"\binterior design\b|\binterior scope\b|\binteriors? package\b|\bid[- ]?\d"),
        ("finish", 125, r"\bfinish(?:es)?\b|\bfinish plan\b|\bfinish schedule\b|\broom finish\b|\bfloor finish\b"),
        ("permit_cd_set", 95, r"\bpermit set\b|\bconstruction documents?\b|\bcd set\b|\b100 ?cds?\b|\bissued for permit\b|\bifp\b"),
        ("approved_plans", 85, r"\bapproved plans?\b|\bstamped plans?\b|\brcc stamped\b|\bsealed for permit\b"),
        ("floor_layout", 80, r"\bfloor plans?\b|\boverall layout\b|\benlarged layout\b|\blayout plan\b"),
        ("drawing_set", 65, r"\bdrawings?\b|\bdwg\b|\bcombined set\b|\bplan set\b"),
        ("sheet_a", 55, r"(^| )a[- ]?\d{1,3}(?:[ .-]|$)|\bsheet a\d\b"),
    ]
    for tag, points, pattern in strong:
        if has(pattern, name):
            score += points
            tags.append(tag)
            reasons.append(f"filename signal: {tag}")

    scope = [
        ("interior_scope", 25, r"\binterior\b|\btenant\b|\bbuild ?out\b|\bfit ?out\b|\bremodel\b|\brenovation\b|\balteration\b"),
        ("commercial_use", 15, r"\brestaurant\b|\bhotel\b|\bretail\b|\boffice\b|\bclinic\b|\bschool\b|\bclassroom\b|\bcafe\b|\bbar\b|\bcommercial\b"),
        ("plans_scope", 12, r"\bper plans\b|\bplans and specifications\b"),
    ]
    for tag, points, pattern in scope:
        if has(pattern, desc):
            score += points
            tags.append(tag)

    hard_junk = [
        ("non_pdf", r"\.pdf(?:\s|$|\()" ),
        ("admin", r"\breceipt\b|\binvoice\b|\bfee\b|\bapplication\b|\bcertificate of occupancy\b|\bbuilding permit\b|\bcontract\b|\bletter\b|\bemail\b|\bresponse\b|\breview comments?\b"),
        ("trade", r"\bmep\b|\bmechanical\b|\belectrical\b|\belec\b|\bplumbing\b|\bplumb\b|\bhvac\b|\bsprinkler\b|\bfire alarm\b|\bfire protection\b|\bcomcheck\b|\briser\b|\blighting\b"),
        ("site_struct", r"\bcivil\b|\bsurvey\b|\bstorm ?water\b|\bswmp\b|\bsite plan\b|\blandscape\b|\bstructural\b|\bstruct\b|\bfoundation\b|\bframing\b|\bpile\b|\bshoring\b|\bslab\b"),
        ("exterior_only", r"\broof\b|\bre ?roof\b|\bgutter\b|\bfence\b|\bsign\b|\bsolar\b|\bno interior work\b|\bexterior only\b"),
        ("media", r"\bphoto\b|\bpictures?\b|\bimage\b|\bcompanycam\b"),
    ]

    if not has(hard_junk[0][1], doc.get("name", "")):
        return -999, ["non_pdf"], ["not a PDF"]

    junk_hits: list[str] = []
    for tag, pattern in hard_junk[1:]:
        if has(pattern, name):
            junk_hits.append(tag)

    # Strong architectural/interior/finish names can survive weak admin words
    # like "approved", but not contracts/certificates/review letters.
    if junk_hits:
        if {"architectural", "interior_design", "finish", "floor_layout"} & set(tags):
            score -= 35 * len(junk_hits)
            tags.extend(junk_hits)
            reasons.append("junk words present but overridden by strong plan signal")
        else:
            return -999, junk_hits, [f"hard pass filename signal: {', '.join(junk_hits)}"]

    if score < 90:
        return score, tags, reasons
    return score, sorted(set(tags)), reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", default=str(OUT_DIR / "agent_triage_packets.jsonl"))
    parser.add_argument("--existing-queue", default=str(OUT_DIR / "download_queue_primary_plan_full.csv"))
    parser.add_argument("--target-docs", type=int, default=150)
    parser.add_argument("--out", default=str(OUT_DIR / "low_token_arch_queue_150.csv"))
    parser.add_argument("--summary", default=str(OUT_DIR / "low_token_arch_queue_150.md"))
    args = parser.parse_args()

    packets = load_jsonl(Path(args.packets))
    downloaded = load_downloaded_ids(
        [
            OUT_DIR / "targeted_download_run.csv",
            ROOT / "data" / "download_run.csv",
        ]
    )
    existing_permits = load_existing_permits(Path(args.existing_queue))

    candidates: list[dict[str, Any]] = []
    for packet in packets:
        permit = packet["permit_num"]
        if permit in existing_permits:
            continue
        best: dict[str, Any] | None = None
        for doc in packet.get("documents", []):
            doc_id = int(doc["doc_id"])
            if doc_id in downloaded or doc.get("already_downloaded"):
                continue
            score, tags, reasons = score_doc(packet, doc)
            if score < 90:
                continue
            row = {
                "doc_id": doc_id,
                "permit_num": permit,
                "code": packet.get("code", ""),
                "score": score,
                "tags": ";".join(tags),
                "name": doc.get("name", ""),
                "description": packet.get("description", ""),
                "reasons": " | ".join(reasons),
            }
            if best is None or row["score"] > best["score"]:
                best = row
        if best:
            candidates.append(best)

    candidates.sort(key=lambda r: (-int(r["score"]), r["permit_num"], int(r["doc_id"])))
    selected = candidates[: args.target_docs]

    fields = ["doc_id", "permit_num", "code", "score", "tags", "name", "description", "reasons"]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)

    by_code = Counter(row["code"] for row in selected)
    by_tag = Counter(tag for row in selected for tag in row["tags"].split(";") if tag)
    lines = [
        "# Low-Token Architectural Queue",
        "",
        "Deterministic, no-agent queue. One selected PDF per new permit.",
        "",
        f"- Candidate docs after filters: {len(candidates)}",
        f"- Selected docs: {len(selected)}",
        f"- Selected permits: {len({row['permit_num'] for row in selected})}",
        f"- Existing primary-wave permits excluded: {len(existing_permits)}",
        "",
        "## By Permit Type",
        "",
        "| code | docs |",
        "|---|---:|",
    ]
    for code, n in by_code.most_common():
        lines.append(f"| {code} | {n} |")
    lines.extend(["", "## Top Signals", "", "| tag | docs |", "|---|---:|"])
    for tag, n in by_tag.most_common(12):
        lines.append(f"| {tag} | {n} |")
    lines.extend(["", "## First 40", "", "| doc_id | permit | score | name |", "|---:|---|---:|---|"])
    for row in selected[:40]:
        lines.append(f"| {row['doc_id']} | {row['permit_num']} | {row['score']} | {row['name'][:110].replace('|', '/')} |")
    Path(args.summary).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"selected_docs={len(selected)}")
    print(f"selected_permits={len({row['permit_num'] for row in selected})}")
    print(f"queue={out_path}")
    print(f"summary={args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
