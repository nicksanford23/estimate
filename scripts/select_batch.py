#!/usr/bin/env python3
"""Select a "go-wider" batch of architectural plan PDFs from the undownloaded
candidates CSV, per the mission rules in the 2026-07-09 go-wider task:

  - Take ALL priority 1 (strict_finish_pdf) and priority 2 (interior_set_pdf)
    rows first.
  - Fill the rest with priority 3 (plan_like_arch_pdf), spread wide:
      * max 3 docs per permit
      * prefer descriptions matching interior/tenant/renovation/build-out/
        office/retail/restaurant/medical/bank/clinic patterns
      * prefer 2015+ issue dates
      * skip obvious non-arch filenames (civil/structural/site/plumbing/
        electrical/mechanical/survey/elevation certificate/stormwater/
        SWMP/landscape/etc.)

Outputs a ranked, permit-capped candidate pool (NOT truncated to ~300 --
the download script consumes it in rank order and can top up from the tail
if early rows turn out to be dead/duplicate/non-PDF). Priority 1/2 rows are
always first regardless of rank score.

No network calls here -- pure CSV in, CSV out.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "codex_work" / "outputs" / "undownloaded_candidates.csv"
OUT = ROOT / "data" / "triage" / "download_batch_2026-07-09_candidates.csv"
MAX_PER_PERMIT = 3

JUNK_RE = re.compile(
    r"(?i)(civil|struct(ural)?\b|site\s*plan|site\s*work|plot\s*plan|benchmark|"
    r"plumbing|\belec(trical|\.|\s*dwg)|mechanical|\bmech\b|survey|"
    r"elevation\s*cert|stormwater|\bswmp\b|landscape|city\s*planning|"
    r"arch\s*cert|certificate\s*of\s*completion|shop\s*drawing|\bhvac\b|"
    r"fire\s*(protection|sprinkler)|energy\s*code|comcheck|backflow|"
    r"riser\s*diagram|geotech|soil\s*(report|boring)|asbestos|demolition\s*cert|"
    r"planting|\bnofd\b|roof\s*drain)"
)

PREFER_RE = re.compile(
    r"(?i)(interior|tenant|renovat|build[- ]?out|\boffice\b|retail|restaurant|"
    r"medical|\bbank\b|clinic)"
)


def year_of(issue_date: str) -> int | None:
    if not issue_date or len(issue_date) < 4:
        return None
    try:
        return int(issue_date[:4])
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-cap", action="store_true",
                    help="drain-the-well mode: no per-permit cap; keep every "
                         "junk-filtered priority 1/2/3 row")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out_path = Path(args.out)
    cap = 10**9 if args.no_cap else MAX_PER_PERMIT

    with SRC.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    p1 = [r for r in rows if r["priority"] == "1"]
    p2 = [r for r in rows if r["priority"] == "2"]
    p3_all = [r for r in rows if r["priority"] == "3"]

    junk_filtered = [r for r in p3_all if JUNK_RE.search(r.get("name", "") or "")]
    p3 = [r for r in p3_all if not JUNK_RE.search(r.get("name", "") or "")]

    def score(r: dict) -> tuple:
        desc = r.get("description", "") or ""
        desc_match = 1 if PREFER_RE.search(desc) else 0
        yr = year_of(r.get("issue_date", ""))
        year_ok = 1 if (yr is not None and yr >= 2015) else 0
        # rank: desc match first, then recency flag, then newer year, then doc_id
        return (-desc_match, -year_ok, -(yr or 0), int(r["doc_id"]))

    p3_sorted = sorted(p3, key=score)

    per_permit: dict[str, int] = {}
    p3_capped = []
    p3_dropped_cap = []
    for r in p3_sorted:
        permit = r["permit_num"]
        n = per_permit.get(permit, 0)
        if n >= cap:
            p3_dropped_cap.append(r)
            continue
        per_permit[permit] = n + 1
        p3_capped.append(r)

    ordered = p1 + p2 + p3_capped

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["rank", "priority", "doc_type", "doc_id", "permit_num", "code",
              "cost", "sqft", "issue_date", "name", "description"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(ordered, 1):
            row = {k: r.get(k, "") for k in fields if k != "rank"}
            row["rank"] = i
            w.writerow(row)

    distinct_permits = len({r["permit_num"] for r in ordered})
    print(f"priority1={len(p1)} priority2={len(p2)}")
    print(f"priority3_total={len(p3_all)} junk_filtered_out={len(junk_filtered)} "
          f"after_junk_filter={len(p3)}")
    print(f"priority3_dropped_by_permit_cap={len(p3_dropped_cap)} "
          f"priority3_kept={len(p3_capped)}")
    print(f"TOTAL candidate pool={len(ordered)}  distinct permits={distinct_permits}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
