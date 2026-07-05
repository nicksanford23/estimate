#!/usr/bin/env python3
"""Report raw Neon documents that have not been downloaded yet.

This is Codex-only inventory analysis. It reads:
- Neon `estimate.documents` + `estimate.permits`
- R2 object listing under `docs/*.pdf` as the primary downloaded flag
- local `data/download_run.csv` and Neon `estimate.document` as secondary
  diagnostics

Outputs stay under codex_work/outputs.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "codex_work" / "outputs"


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


def load_download_run(path: Path) -> dict[int, dict]:
    out = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            try:
                doc_id = int(row[0])
            except ValueError:
                continue
            out[doc_id] = {
                "status": row[1],
                "bytes": int(row[2]) if len(row) > 2 and row[2].isdigit() else None,
                "filename": row[3] if len(row) > 3 else "",
            }
    return out


def list_r2_doc_ids(env: dict[str, str]) -> set[int]:
    """Return doc_ids for R2 objects named docs/<doc_id>.pdf."""
    import boto3

    required = ["R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise RuntimeError(f"missing R2 env keys: {', '.join(missing)}")

    s3 = boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    out: set[int] = set()
    token = None
    while True:
        kwargs = {"Bucket": env["R2_BUCKET"], "Prefix": "docs/"}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            key = obj.get("Key", "")
            m = re.fullmatch(r"docs/(\d+)\.pdf", key)
            if m:
                out.add(int(m.group(1)))
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return out


def fetch_docs(database_url: str) -> list[dict]:
    import psycopg2

    sql = """
    SELECT
      d.doc_id,
      d.permit_num,
      d.name,
      p.code,
      p.cost,
      p.sqft,
      p.permit_class,
      p.status,
      p.issue_date,
      p.description
    FROM estimate.documents d
    JOIN estimate.permits p USING (permit_num)
    ORDER BY d.doc_id
    """
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()
    for row in rows:
        row["doc_id"] = int(row["doc_id"])
        row["name"] = row["name"] or ""
        row["description"] = row["description"] or ""
    return rows


def fetch_working_downloads(database_url: str) -> dict[int, dict]:
    """Docs present in estimate.document. `rendered`/`downloaded` means we have
    the PDF in the working pipeline; `pending` is only queued."""
    import psycopg2

    sql = """
    SELECT onestop_doc_id, status, storage_path, page_count
    FROM estimate.document
    """
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO estimate, public")
        cur.execute(sql)
        rows = cur.fetchall()
    finally:
        conn.close()
    out = {}
    for doc_id, status, storage_path, page_count in rows:
        out[int(doc_id)] = {
            "status": status,
            "storage_path": storage_path,
            "page_count": page_count,
        }
    return out


def is_pdf(name: str) -> bool:
    return bool(re.search(r"\.pdf(?:\s|$|\()", name, re.I))


def doc_type(name: str) -> str:
    n = name.lower()
    if not is_pdf(name):
        return "non_pdf_or_message"
    if re.search(r"receipt|invoice|contract|license|letter|approval|extension|application|form|fee|email", n):
        return "admin_pdf"
    if re.search(
        r"finish plan|finish schedule|finished floor|finish floor|finishes plan|"
        r"room finish|material.?schedule|finish legend|flooring|floor finish",
        n,
    ):
        return "strict_finish_pdf"
    if re.search(
        r"interior design|interiors permit|interior build.?out|interior scope|"
        r"interior work|interior repairs|interiors_",
        n,
    ):
        return "interior_set_pdf"
    if re.search(
        r"arch|floor|plan|drawing|dwg|cd set|construction doc|layout|elevation|"
        r"permit set|issued for|\ba[-.]?\d",
        n,
    ):
        return "plan_like_arch_pdf"
    if re.search(r"mep|mech|elect|plumb|fire|hvac|sprinkler|technology|low voltage", n):
        return "mep_fire_pdf"
    if re.search(r"struct|foundation|framing|civil|site|survey", n):
        return "struct_civil_site_pdf"
    return "other_pdf"


def priority(row: dict) -> int:
    t = row["doc_type"]
    if t == "strict_finish_pdf":
        return 1
    if t == "interior_set_pdf":
        return 2
    if t == "plan_like_arch_pdf":
        return 3
    if t == "other_pdf" and re.search(r"finish|interior|floor|plan", row["description"], re.I):
        return 4
    return 9


def write_candidate_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "priority",
        "doc_type",
        "doc_id",
        "permit_num",
        "code",
        "cost",
        "sqft",
        "issue_date",
        "name",
        "description",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def table(lines: list[str], headers: list[str], rows: list[list]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")


def write_report(
    path: Path,
    docs: list[dict],
    downloaded: dict[int, dict],
    working_downloads: dict[int, dict],
    r2_doc_ids: set[int],
    known_downloaded: set[int],
    candidates: list[dict],
) -> None:
    raw_doc_ids = {d["doc_id"] for d in docs}
    ok_downloaded = {i for i, r in downloaded.items() if r["status"] == "ok"}
    non_ok_download = {i for i, r in downloaded.items() if r["status"] != "ok"}
    working_ready = {
        i for i, r in working_downloads.items()
        if r.get("status") in {"downloaded", "rendered"}
    }
    undownloaded = [d for d in docs if d["doc_id"] not in known_downloaded]
    never_queued = [
        d for d in docs
        if d["doc_id"] not in downloaded and d["doc_id"] not in working_downloads
    ]
    docs_by_permit = defaultdict(list)
    for d in docs:
        docs_by_permit[d["permit_num"]].append(d)
    permit_status = Counter()
    permit_status_by_code = defaultdict(Counter)
    for permit, permit_docs in docs_by_permit.items():
        n_total = len(permit_docs)
        n_downloaded = sum(1 for d in permit_docs if d["doc_id"] in known_downloaded)
        code = permit_docs[0]["code"]
        if n_downloaded == 0:
            status = "not_started"
        elif n_downloaded == n_total:
            status = "fully_downloaded"
        else:
            status = "partially_downloaded"
        permit_status[status] += 1
        permit_status_by_code[code][status] += 1

    by_type = Counter(d["doc_type"] for d in undownloaded)
    by_type_permits = defaultdict(set)
    for d in undownloaded:
        by_type_permits[d["doc_type"]].add(d["permit_num"])

    by_code = Counter(d["code"] for d in undownloaded)
    by_code_permits = defaultdict(set)
    for d in undownloaded:
        by_code_permits[d["code"]].add(d["permit_num"])

    lines = [
        "# Undownloaded Neon Document Inventory",
        "",
        "Source of truth: Neon `estimate.documents` joined to `estimate.permits`.",
        "Downloaded reference: R2 `docs/<doc_id>.pdf` object existence.",
        "Local `data/download_run.csv` and Neon `estimate.document` are included",
        "only as diagnostics.",
        "",
        "## Headline",
        "",
        f"- Raw Neon documents: {len(docs)}",
        f"- Raw Neon permits represented by documents: {len({d['permit_num'] for d in docs})}",
        f"- Download-run rows: {len(downloaded)}",
        f"- Downloaded OK doc_ids in download_run: {len(ok_downloaded & raw_doc_ids)}",
        f"- Working pipeline downloaded/rendered doc_ids in estimate.document: {len(working_ready & raw_doc_ids)}",
        f"- R2 docs/<doc_id>.pdf objects matching raw Neon docs: {len(r2_doc_ids & raw_doc_ids)}",
        f"- Known downloaded/rendered union used for this report: {len(known_downloaded & raw_doc_ids)}",
        f"- Non-OK/failed queued doc_ids in download_run: {len(non_ok_download & raw_doc_ids)}",
        f"- Not downloaded OK yet: {len(undownloaded)} documents across {len({d['permit_num'] for d in undownloaded})} permits",
        f"- Never queued in download_run: {len(never_queued)} documents across {len({d['permit_num'] for d in never_queued})} permits",
        "",
        "## Permit-Level Download Status",
        "",
        f"- Permits with at least one document in Neon: {len(docs_by_permit)}",
        f"- Permits with at least one known downloaded/rendered doc: {permit_status['fully_downloaded'] + permit_status['partially_downloaded']}",
        f"- Fully downloaded permits: {permit_status['fully_downloaded']}",
        f"- Partially downloaded permits: {permit_status['partially_downloaded']}",
        f"- Not-started permits: {permit_status['not_started']}",
        "",
        "| permit_type | fully_downloaded | partially_downloaded | not_started | total_with_docs |",
        "|---|---:|---:|---:|---:|",
    ]
    for code in sorted(permit_status_by_code):
        c = permit_status_by_code[code]
        total = c["fully_downloaded"] + c["partially_downloaded"] + c["not_started"]
        lines.append(
            f"| {code} | {c['fully_downloaded']} | {c['partially_downloaded']} | "
            f"{c['not_started']} | {total} |"
        )
    lines.extend([
        "",
        "## Undownloaded By Filename Type",
        "",
    ])
    table(
        lines,
        ["doc_type", "docs", "permits"],
        [[t, by_type[t], len(by_type_permits[t])] for t, _ in by_type.most_common()],
    )
    lines.extend(["", "## Undownloaded By Permit Type", ""])
    table(
        lines,
        ["permit_type", "docs", "permits"],
        [[c, by_code[c], len(by_code_permits[c])] for c, _ in by_code.most_common()],
    )

    cand_by_type = Counter(d["doc_type"] for d in candidates)
    cand_by_type_permits = defaultdict(set)
    for d in candidates:
        cand_by_type_permits[d["doc_type"]].add(d["permit_num"])
    lines.extend(["", "## High-Priority Undownloaded Candidates", ""])
    table(
        lines,
        ["doc_type", "docs", "permits"],
        [[t, cand_by_type[t], len(cand_by_type_permits[t])] for t, _ in cand_by_type.most_common()],
    )
    lines.extend(
        [
            "",
            "Priority definition:",
            "- 1: strict finish PDF filename",
            "- 2: interior set PDF filename",
            "- 3: broad architectural/plan-like PDF filename",
            "- 4: other PDF with finish/interior/floor/plan terms in permit description",
            "",
            "## Top Candidate Permits",
            "",
            "| permit | type | candidate_docs | examples |",
            "|---|---|---:|---|",
        ]
    )
    per_permit = defaultdict(list)
    for d in candidates:
        per_permit[d["permit_num"]].append(d)
    top = sorted(per_permit.items(), key=lambda kv: (min(d["priority"] for d in kv[1]), -len(kv[1]), kv[0]))[:40]
    for permit, rows in top:
        rows = sorted(rows, key=lambda r: (r["priority"], r["doc_id"]))
        examples = " / ".join(f"{r['doc_id']}:{r['name'][:70]}" for r in rows[:3])
        if len(rows) > 3:
            examples += f" / +{len(rows)-3} more"
        lines.append(f"| {permit} | {rows[0]['code']} | {len(rows)} | {examples} |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database-url", default=None)
    p.add_argument("--download-run", default=str(ROOT / "data" / "download_run.csv"))
    p.add_argument("--report", default=str(OUT_DIR / "undownloaded_inventory.md"))
    p.add_argument("--candidates", default=str(OUT_DIR / "undownloaded_candidates.csv"))
    p.add_argument(
        "--skip-r2",
        action="store_true",
        help="do not list R2; use download_run + estimate.document fallback only",
    )
    args = p.parse_args()

    env = load_env()
    database_url = args.database_url or env.get("NEON_DATABASE_URL")
    if not database_url:
        raise SystemExit("NEON_DATABASE_URL missing")

    downloaded = load_download_run(Path(args.download_run))
    docs = fetch_docs(database_url)
    working_downloads = fetch_working_downloads(database_url)
    r2_doc_ids = set() if args.skip_r2 else list_r2_doc_ids(env)
    ok_downloaded = {i for i, r in downloaded.items() if r["status"] == "ok"}
    working_ready = {
        i for i, r in working_downloads.items()
        if r.get("status") in {"downloaded", "rendered"}
    }
    known_downloaded = r2_doc_ids | ok_downloaded | working_ready

    for d in docs:
        d["doc_type"] = doc_type(d["name"])
        d["priority"] = priority(d)

    undownloaded = [d for d in docs if d["doc_id"] not in known_downloaded]
    candidates = [d for d in undownloaded if d["priority"] <= 4]
    candidates.sort(key=lambda r: (r["priority"], r["permit_num"], r["doc_id"]))

    write_candidate_csv(Path(args.candidates), candidates)
    write_report(
        Path(args.report),
        docs,
        downloaded,
        working_downloads,
        r2_doc_ids,
        known_downloaded,
        candidates,
    )

    print(f"raw_docs={len(docs)} undownloaded={len(undownloaded)} candidates={len(candidates)}")
    print(f"wrote {args.report}")
    print(f"wrote {args.candidates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
