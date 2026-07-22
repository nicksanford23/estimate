#!/usr/bin/env python3
"""Backup / restore the gitignored pipeline data to R2 (migration + insurance).

  backup  : tar the irreplaceable-or-slow-to-regenerate data dirs -> R2
  restore : pull the latest backup tar from R2 and extract into data/

Covers: sam_smoke (measurements, proofs, crops), geometry_annotations (TRUTH),
training (manifests/runbook), triage/truth_area (answer keys), telegram state,
pilot_projects packets. Excludes render_cache (PDFs re-pullable from R2 docs/).
"""
import os
import subprocess
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ["data/sam_smoke", "data/geometry_annotations", "data/training",
        "data/triage/truth_area", "data/telegram", "data/pilot_projects"]
KEY = "claude-repo/backups/data_backup_latest.tar.gz"
TAR = "/tmp/estimate_data_backup.tar.gz"


def env():
    out = {}
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
    return out


def s3():
    import boto3
    e = env()
    return boto3.client("s3", endpoint_url=e["R2_ENDPOINT"],
                        aws_access_key_id=e["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=e["R2_SECRET_ACCESS_KEY"],
                        region_name="auto"), e


def backup():
    with tarfile.open(TAR, "w:gz") as t:
        for d in DIRS:
            p = os.path.join(ROOT, d)
            if os.path.exists(p):
                t.add(p, arcname=d)
                print("added", d)
    c, e = s3()
    size = os.path.getsize(TAR) // (1 << 20)
    c.upload_file(TAR, e["R2_BUCKET"], KEY)
    print(f"uploaded {size} MB -> r2:{KEY}")


def restore():
    c, e = s3()
    c.download_file(e["R2_BUCKET"], KEY, TAR)
    with tarfile.open(TAR) as t:
        t.extractall(ROOT)
    print("restored into", ROOT)


if __name__ == "__main__":
    (restore if "restore" in sys.argv else backup)()
