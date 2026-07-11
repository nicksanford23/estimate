#!/usr/bin/env python3
"""Import one completed dual-page artifact as V2 machine observations.

No human decisions or eligibility approvals are created. Re-importing the same
run is idempotent. The artifact must target `v2-page:<id>` and its source image
must resolve inside the repository.
"""

import argparse
import json
import os
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]


def load_env():
    for raw in (ROOT / ".env").read_text().splitlines():
        raw = raw.strip()
        if raw and not raw.startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact")
    args = parser.parse_args()
    artifact_path = (ROOT / args.artifact).resolve()
    if ROOT not in artifact_path.parents:
        raise SystemExit("artifact must be inside the repository")
    artifact = json.loads(artifact_path.read_text())

    if artifact.get("task") != "dual_page_label":
        raise SystemExit("not a dual_page_label artifact")
    if artifact.get("database_writes") is not False or artifact.get("trusted_semantic_truth") is not False:
        raise SystemExit("artifact violates the machine-only truth boundary")
    page_ref = artifact.get("page_ref", "")
    if not page_ref.startswith("v2-page:"):
        raise SystemExit("page_ref must be v2-page:<id>")
    page_id = int(page_ref.split(":", 1)[1])
    run_id = artifact["run_id"]
    rubric = artifact["rubric_version"]
    comparison = artifact.get("comparison", {})

    load_env()
    conn = psycopg2.connect(os.environ["NEON_DATABASE_URL"])
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM v2.page WHERE id=%s", (page_id,))
                if not cur.fetchone():
                    raise SystemExit(f"unknown v2 page {page_id}")
                inserted = 0
                for vendor in ("claude", "codex"):
                    output = artifact.get("outputs", {}).get(vendor, {})
                    if not output.get("ok"):
                        continue
                    label = output["response"]
                    common = {
                        "run_id": run_id,
                        "rubric_version": rubric,
                        "vendor": vendor,
                        "model": output.get("model"),
                        "reasoning_effort": output.get("reasoning_effort"),
                        "confidence": label["confidence"],
                        "evidence": label["evidence"],
                        "uncertainty": label["uncertainty"],
                        "image_sha256": artifact["image"]["sha256"],
                        "comparison_state": comparison.get("state"),
                    }
                    values = {
                        "page_category": {**common, "category": label["category"]},
                        "page_flags": {**common, "flags": label["flags"]},
                        "sheet_number": {**common, "sheet_number": label["sheet_number"]},
                        "sheet_title": {**common, "title": label["sheet_title"]},
                    }
                    for claim, value in values.items():
                        cur.execute(
                            """SELECT 1 FROM v2.machine_observation
                               WHERE target_type='page' AND target_id=%s AND claim=%s
                                 AND source=%s AND source_version=%s""",
                            (page_id, claim, f"agent_bridge:{vendor}", run_id),
                        )
                        if cur.fetchone():
                            continue
                        cur.execute(
                            """INSERT INTO v2.machine_observation
                               (target_type,target_id,claim,value_json,source,source_version,
                                score_raw,score_type,calibration_version)
                               VALUES ('page',%s,%s,%s::jsonb,%s,%s,%s,'self_reported',%s)""",
                            (page_id, claim, json.dumps(value), f"agent_bridge:{vendor}",
                             run_id, label["confidence"], rubric),
                        )
                        inserted += 1
        print(json.dumps({"run_id": run_id, "page_id": page_id,
                          "machine_observations_inserted": inserted,
                          "human_decisions_inserted": 0,
                          "eligibility_events_inserted": 0}))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
