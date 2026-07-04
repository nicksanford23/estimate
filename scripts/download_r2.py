#!/usr/bin/env python3
"""Download plan-like NOLA permit PDFs into the shared R2 bucket.

Queue = Neon `documents` filenames that pass the plan-like screen (NEWC+RNVS).
For each doc_id:  HEAD R2 -> skip if present;  GET from One Stop;  validate
%PDF magic;  PUT to R2 docs/{doc_id}.pdf;  keep a local copy for rendering.
Resumable by design: the bucket is the downloaded flag.
"""
import csv
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {}
with open(os.path.join(ROOT, ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            ENV[k] = v

BUCKET_URL = f"{ENV['R2_ENDPOINT']}/{ENV['R2_BUCKET']}"
AWS_USER = f"{ENV['R2_ACCESS_KEY_ID']}:{ENV['R2_SECRET_ACCESS_KEY']}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
LOCAL_DIR = os.path.join(ROOT, "data", "pdfs_r2")
LOG_PATH = os.path.join(ROOT, "data", "download_run.csv")
WORKERS = 3

PLAN = r"(arch|floor ?plan|plans|drawing|dwg|cd set|construction doc|layout|elevation|interior|permit set|pricing set|issued for|bid set|\mA[-. ]?\d{3})"
JUNK = (r"(\.msg|\.doc|\.jpg|\.jpeg|\.png|\.xls|\.zip|\.heic|struct|mep\M|mech|elec|plumb"
        r"|civil|fire|sprink|survey|receipt|invoice|contract|license|letter|approval"
        r"|extension|permit card|inspection|asbestos|riser|framing|elev_|elevator|hvac"
        r"|energy|comcheck|certificate|backflow|swmp|foundation|shop drawing)")


def curl(args, timeout):
    return subprocess.run(["curl", "-s", "-m", str(timeout)] + args,
                          capture_output=True, timeout=timeout + 30)


def head_r2(doc_id):
    r = curl(["-o", "/dev/null", "-w", "%{http_code}", "-I",
              "--aws-sigv4", "aws:amz:auto:s3", "--user", AWS_USER,
              f"{BUCKET_URL}/docs/{doc_id}.pdf"], 60)
    return r.stdout.decode().strip() == "200"


def fetch(doc_id, dest):
    for attempt in range(3):
        r = curl(["-L", "-A", UA, "-o", dest, "-w", "%{http_code}",
                  "--connect-timeout", "60",
                  f"https://onestopapp.nola.gov/GetDocument.aspx?DocID={doc_id}"], 1800)
        code = r.stdout.decode().strip()
        if code == "200" and os.path.exists(dest) and os.path.getsize(dest) > 10240:
            with open(dest, "rb") as f:
                if f.read(4) == b"%PDF":
                    return "ok"
            return "not_pdf"
        time.sleep(15 * (attempt + 1))
    return f"http_{code}"


def put_r2(doc_id, path):
    r = curl(["-o", "/dev/null", "-w", "%{http_code}", "-X", "PUT",
              "--aws-sigv4", "aws:amz:auto:s3", "--user", AWS_USER,
              "--data-binary", f"@{path}", "-H", "Content-Type: application/pdf",
              f"{BUCKET_URL}/docs/{doc_id}.pdf"], 1800)
    return r.stdout.decode().strip() == "200"


def process(item):
    doc_id, name = item
    dest = os.path.join(LOCAL_DIR, f"{doc_id}.pdf")
    try:
        if head_r2(doc_id):
            return (doc_id, "already_in_r2", 0, name)
        status = fetch(doc_id, dest)
        if status != "ok":
            if os.path.exists(dest):
                os.remove(dest)
            return (doc_id, status, 0, name)
        size = os.path.getsize(dest)
        if not put_r2(doc_id, dest):
            return (doc_id, "r2_put_failed", size, name)
        return (doc_id, "ok", size, name)
    except Exception as e:  # noqa: BLE001 - log and continue the run
        return (doc_id, f"exc_{type(e).__name__}", 0, name)


def main():
    os.makedirs(LOCAL_DIR, exist_ok=True)
    done = set()
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            for row in csv.reader(f):
                if row and row[1] in ("ok", "already_in_r2", "not_pdf"):
                    done.add(row[0])

    conn = psycopg2.connect(ENV["NEON_DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """SELECT d.doc_id, d.name FROM documents d JOIN permits p USING (permit_num)
           WHERE p.code IN ('NEWC','RNVS') AND d.name ~* %s AND d.name !~* %s
           ORDER BY d.doc_id""", (PLAN, JUNK))
    queue = [(str(r[0]), r[1]) for r in cur.fetchall() if str(r[0]) not in done]
    conn.close()
    print(f"queue: {len(queue)} docs ({len(done)} already logged)", flush=True)

    log = open(LOG_PATH, "a", newline="")
    writer = csv.writer(log)
    counts = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i, res in enumerate(pool.map(process, queue), 1):
            writer.writerow(res)
            log.flush()
            counts[res[1]] = counts.get(res[1], 0) + 1
            if i % 25 == 0:
                print(f"{i}/{len(queue)} {counts}", flush=True)
    print(f"DONE {counts}", flush=True)


if __name__ == "__main__":
    main()
